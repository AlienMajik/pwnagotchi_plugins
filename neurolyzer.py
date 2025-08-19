import logging
import subprocess
import time
import random
import os
import re
import fcntl

import pwnagotchi.plugins as plugins
from pwnagotchi.ui.components import LabeledValue
from pwnagotchi.ui.view import BLACK
import pwnagotchi.ui.fonts as fonts

class Neurolyzer(plugins.Plugin):
    __author__ = 'AlienMajik'
    __version__ = '1.6.0'
    __license__ = 'GPL3'
    __description__ = "Advanced WIDS/WIPS evasion system with hardware-aware adaptive countermeasures"

    DEFAULT_OUI = [
        '00:14:22', '34:AB:95', 'DC:A6:32', '00:1A:11', '08:74:02', '50:32:37',  # Existing
        'B8:27:EB', 'DC:A6:32', 'E4:5F:01', 'FC:45:96', '00:E0:4C', '00:1E:06',  # Common Broadcom/RPi-like
        '00:26:BB', '00:50:F2', '00:0C:29', '00:15:5D'  # VMware/Generic for variety
    ]
    DEFAULT_WIDS = ['wids-guardian', 'airdefense', 'cisco-ips', 'cisco-awips', 'fortinet-wids', 'aruba-widp', 'kismet']
    SAFE_CHANNELS = [1, 6, 11]
    MIN_MAC_CHANGE_INTERVAL = 30  # Minimum seconds between MAC changes
    LOCK_FILE = '/tmp/neurolyzer.lock'

    def __init__(self):
        self.enabled = False
        self.wifi_interface = 'wlan0'
        self.operation_mode = 'stealth'
        self.mac_change_interval = 3600  # Default interval
        self.last_operations = {
            'mac_change': 0,
            'wids_check': 0,
            'channel_hop': 0,
            'tx_power_change': 0
        }
        
        # Hardware capabilities cache
        self.hw_caps = {
            'tx_power': {'min': 1, 'max': 20, 'supported': True},
            'supported_channels': self.SAFE_CHANNELS,
            'monitor_mode': True,
            'mac_spoofing': True,
            'iproute2': True,
            'broadcom': False,
            'injection': False
        }
        
        # State tracking
        self.current_channel = 1
        self.current_tx_power = 20
        self.probe_blacklist = []
        self.current_mac = None
        self.lock_fd = None
        
        # UI configuration
        self.ui_config = {
            'mode': (0, 0),
            'mac_timer': (0, 10),
            'tx_power': (0, 20),
            'channel': (0, 30),
            'stealth': (0, 40)
        }

        # New attributes for enhancements
        self.stealth_level = 1  # 1-3: low (aggressive captures), med, high (passive)
        self.deauth_throttle = 0.5  # Fraction of APs to deauth per cycle
        self.whitelist_ssids = []
        self.nexmon_enabled = False
        self.monitor_iface = 'mon0'  # Assume standard Pwnagotchi mon iface

    def _acquire_lock(self):
        """Acquire exclusive lock for atomic operations"""
        try:
            self.lock_fd = open(self.LOCK_FILE, 'w')
            fcntl.flock(self.lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return True
        except (IOError, BlockingIOError):
            return False

    def _release_lock(self):
        """Release exclusive lock"""
        if self.lock_fd:
            try:
                fcntl.flock(self.lock_fd, fcntl.LOCK_UN)
                self.lock_fd.close()
                os.remove(self.LOCK_FILE)
            except:
                pass

    def _execute(self, command, critical=False, retries=2, timeout=8):
        """Robust command execution with retries and alternate methods"""
        methods = [
            command,
            ['iwconfig' if cmd == 'iw' else cmd for cmd in command]  # Fallback to iwconfig
        ]
        
        for attempt in range(retries + 1):
            for method in methods:
                try:
                    result = subprocess.run(
                        ['sudo'] + method,
                        check=True,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                        timeout=timeout
                    )
                    return result
                except subprocess.CalledProcessError as e:
                    error = e.stderr.strip()
                    if attempt == retries:
                        if "Device or resource busy" in error:
                            logging.debug(f"[Neurolyzer] Interface busy, retrying {method[0]}")
                            time.sleep(random.uniform(0.5, 1.5))
                            continue
                        if "Operation not supported" in error:
                            self._update_hw_capability(method[0], False)
                    logging.debug(f"[Neurolyzer] Attempt {attempt+1} failed: {' '.join(method)} - {error}")
                except Exception as e:
                    logging.debug(f"[Neurolyzer] Unexpected error: {str(e)}")
        return None

    def _update_hw_capability(self, feature, supported):
        """Dynamically adjust hardware capabilities"""
        if feature == 'txpower':
            self.hw_caps['tx_power']['supported'] = supported
        elif feature == 'mac':
            self.hw_caps['mac_spoofing'] = supported
        elif feature == 'iproute2':
            self.hw_caps['iproute2'] = supported

    def _current_tx_power(self):
        """Get current TX power level"""
        try:
            result = self._execute(['iw', 'dev', self.wifi_interface, 'get', 'txpower'])
            if result:
                match = re.search(r'txpower (\d+) dBm', result.stdout)
                return int(match.group(1)) if match else self.current_tx_power
            return self.current_tx_power
        except Exception as e:
            logging.debug(f"[Neurolyzer] TX power read failed: {str(e)}")
            return self.current_tx_power

    def _safe_mac_change(self):
        """Atomic MAC rotation with locking"""
        if time.time() - self.last_operations['mac_change'] < self.MIN_MAC_CHANGE_INTERVAL:
            return

        if not self._acquire_lock():
            logging.debug("[Neurolyzer] MAC change skipped - operation in progress")
            return

        try:
            original_mac = self._get_current_mac()
            new_mac = self._generate_valid_mac().lower()  # Normalize to lowercase
            
            # New: Handle monitor interface for Pwnagotchi/Broadcom
            mon_delete = ['iw', 'dev', self.monitor_iface, 'del'] if os.path.exists(f'/sys/class/net/{self.monitor_iface}') else None
            if mon_delete:
                self._execute(mon_delete)
                time.sleep(1)  # Wait for cleanup
        
            # Down physical iface
            self._execute(['ip', 'link', 'set', 'dev', self.wifi_interface, 'down']) or \
            self._execute(['ifconfig', self.wifi_interface, 'down'])
        
            # Change MAC (add macchanger fallback for Broadcom quirks)
            changed = False
            if self._execute(['ip', 'link', 'set', 'dev', self.wifi_interface, 'address', new_mac]):
                changed = True
            elif self._execute(['ifconfig', self.wifi_interface, 'hw', 'ether', new_mac]):
                changed = True
            elif self._execute(['macchanger', '-m', new_mac, self.wifi_interface]):  # Fallback (assume macchanger installed)
                changed = True
        
            if not changed:
                raise RuntimeError("MAC change failed on all methods")
        
            # Up physical iface
            self._execute(['ip', 'link', 'set', 'dev', self.wifi_interface, 'up']) or \
            self._execute(['ifconfig', self.wifi_interface, 'up'])
        
            # Recreate monitor if it existed
            if mon_delete:
                self._execute(['iw', 'dev', self.wifi_interface, 'add', self.monitor_iface, 'type', 'monitor'])
                self._execute(['ip', 'link', 'set', 'dev', self.monitor_iface, 'up'])
        
            # Verify
            verified_mac = self._get_current_mac().lower()
            if verified_mac != new_mac:
                raise RuntimeError(f"MAC verification failed (expected: {new_mac}, got: {verified_mac})")
        
            self.last_operations['mac_change'] = time.time()
            self.current_mac = new_mac
            logging.info(f"[Neurolyzer] MAC rotated to {new_mac}")
    
        except Exception as e:
            logging.error(f"[Neurolyzer] MAC rotation failed: {str(e)}")
            # Restore original if possible
            if original_mac:
                self._execute(['ip', 'link', 'set', 'dev', self.wifi_interface, 'address', original_mac.lower()])
        finally:
            self._release_lock()

    def _adjust_tx_power(self):
        """Hardware-adaptive TX power control"""
        if not self.hw_caps['tx_power']['supported']:
            return

        try:
            min_p, max_p = self.hw_caps['tx_power']['min'], self.hw_caps['tx_power']['max']
            if self.stealth_level == 3:
                new_power = random.randint(min_p, min_p + 5)  # Low power for stealth
            elif self.stealth_level == 2:
                new_power = random.randint(min_p + 5, max_p - 5)
            else:
                new_power = random.randint(max_p - 5, max_p)  # High for better range/captures
            self._execute(['iw', 'dev', self.wifi_interface, 'set', 'txpower', 'fixed', str(new_power)]) or \
            self._execute(['iwconfig', self.wifi_interface, 'txpower', str(new_power)])
            self.current_tx_power = new_power
        except Exception as e:
            logging.debug(f"[Neurolyzer] TX power adjustment skipped: {str(e)}")

    def _throttle_traffic(self):
        """Compatibility-focused traffic shaping"""
        try:
            # Try modern qdisc
            result = self._execute([
                'tc', 'qdisc', 'replace', 'dev', self.wifi_interface,
                'root', 'netem', 'delay', '100ms', '10ms', 'distribution', 'normal'
            ])
            if not result:
                # Fallback to simple shaping
                self._execute([
                    'tc', 'qdisc', 'replace', 'dev', self.wifi_interface,
                    'root', 'pfifo', 'limit', '1000'
                ])
        except Exception as e:
            logging.debug(f"[Neurolyzer] Traffic shaping unavailable: {str(e)}")

    def _validate_interface(self):
        """Ensure interface exists and is ready"""
        retries = 0
        while retries < 3:
            if os.path.exists(f'/sys/class/net/{self.wifi_interface}'):
                return True
            logging.warning(f"[Neurolyzer] Interface missing, retrying... ({retries+1}/3)")
            time.sleep(2 ** retries)
            retries += 1
        return False

    def on_loaded(self):
        if not hasattr(self, 'options'):
            logging.warning("[Neurolyzer] Options not provided by framework, using defaults")
            self.options = {}
        else:
            logging.debug("[Neurolyzer] Options loaded: {}".format(self.options))
        
        valid_modes = ['normal', 'stealth', 'noided']
        self.operation_mode = self.options.get('operation_mode', 'stealth')
        if self.operation_mode not in valid_modes:
            logging.error(f"[Neurolyzer] Invalid mode: {self.operation_mode}")
            self.enabled = False
            return

        self.wifi_interface = self.options.get('wifi_interface', 'wlan0')
        self.mac_change_interval = self.options.get('mac_change_interval', 3600)
        self.whitelist_ssids = self.options.get('whitelist_ssids', [])
        self.enabled = self.options.get('enabled', True)

        # Reworked UI configuration loading
        self.ui_config['mode'] = (
            self.options.get('mode_label_x', self.ui_config['mode'][0]),
            self.options.get('mode_label_y', self.ui_config['mode'][1])
        )
        self.ui_config['mac_timer'] = (
            self.options.get('next_mac_change_label_x', self.ui_config['mac_timer'][0]),
            self.options.get('next_mac_change_label_y', self.ui_config['mac_timer'][1])
        )
        self.ui_config['tx_power'] = (
            self.options.get('tx_power_label_x', self.ui_config['tx_power'][0]),
            self.options.get('tx_power_label_y', self.ui_config['tx_power'][1])
        )
        self.ui_config['channel'] = (
            self.options.get('channel_label_x', self.ui_config['channel'][0]),
            self.options.get('channel_label_y', self.ui_config['channel'][1])
        )
        self.ui_config['stealth'] = (
            self.options.get('stealth_label_x', self.ui_config['stealth'][0]),
            self.options.get('stealth_label_y', self.ui_config['stealth'][1])
        )

        # Enhanced initialization sequence
        try:
            if not self._validate_interface():
                raise RuntimeError("Network interface unavailable")
            
            # Dynamic capability discovery
            self._discover_hardware_capabilities()
            
            # Fallback to sane defaults if detection failed
            if not self.hw_caps['supported_channels']:
                self.hw_caps['supported_channels'] = self.SAFE_CHANNELS
                
            if not self.hw_caps['tx_power']['supported']:
                self.hw_caps['tx_power'] = {'min': 1, 'max': 20, 'supported': False}
            
            if self.nexmon_enabled:
                # Optional: Load Nexmon if not auto-loaded (assume it is)
                self._execute(['modprobe', 'brcmfmac'])  # Reload if needed
            
            self._apply_initial_config()
            logging.info(f"[Neurolyzer] Active in {self.operation_mode} mode")

        except Exception as e:
            logging.error(f"[Neurolyzer] Initialization failed: {str(e)}")
            self.enabled = False

    def _discover_hardware_capabilities(self):
        """Comprehensive hardware capability discovery"""
        try:
            # Get interface info
            info = self._execute(['iw', 'dev', self.wifi_interface, 'info'])
            if not info:
                raise RuntimeError("Interface information unavailable")
                
            # TX power capabilities
            tx_info = self._execute(['iw', 'dev', self.wifi_interface, 'get', 'txpower'])
            if tx_info:
                tx_matches = re.findall(r'(\d+) dBm', tx_info.stdout)
                if tx_matches:
                    self.hw_caps['tx_power']['min'] = min(int(m) for m in tx_matches)
                    self.hw_caps['tx_power']['max'] = max(int(m) for m in tx_matches)
                else:
                    self.hw_caps['tx_power']['supported'] = False
            
            # Supported channels
            phy_match = re.search(r'phy#(\d+)', info.stdout)
            if phy_match:
                phy = phy_match.group(1)
                chan_info = self._execute(['iw', 'phy', phy, 'info'])
                if chan_info:
                    self.hw_caps['supported_channels'] = [
                        int(m) for m in re.findall(r'(\d+) MHz', chan_info.stdout)
                    ]
            
            # Monitor mode support
            self.hw_caps['monitor_mode'] = 'monitor' in info.stdout

            # MAC spoofing test
            self.hw_caps['mac_spoofing'] = self._test_mac_spoofing()

            # Detect driver (Broadcom check)
            try:
                with open(f'/sys/class/net/{self.wifi_interface}/device/driver/module/drivers', 'r') as f:
                    driver_info = f.read()
                    if 'brcmfmac' in driver_info:
                        logging.info("[Neurolyzer] Broadcom chipset detected")
                        self.hw_caps['broadcom'] = True
                        # TX limits for Broadcom (typically lower)
                        self.hw_caps['tx_power'] = {'min': 1, 'max': 15, 'supported': True}
                        
                        # Check for Nexmon (look for patched firmware)
                        nexmon_check = self._execute(['dmesg | grep nexmon'])
                        self.nexmon_enabled = 'nexmon' in nexmon_check.stdout if nexmon_check else False
                        if self.nexmon_enabled:
                            logging.info("[Neurolyzer] Nexmon detected - enabling injection/5GHz")
                            self.hw_caps['monitor_mode'] = True
                            self.hw_caps['injection'] = True
                            self.hw_caps['supported_channels'] += [36, 40, 44, 48]  # Add 5GHz
                        else:
                            logging.warning("[Neurolyzer] No Nexmon - limited to passive captures (no injection)")
                            self.hw_caps['injection'] = False
            except:
                self.hw_caps['broadcom'] = False
                self.nexmon_enabled = False

        except Exception as e:
            logging.error(f"[Neurolyzer] Hardware discovery failed: {str(e)}")
            self.enabled = False

    def _test_mac_spoofing(self):
        """Verify MAC address spoofing capability"""
        try:
            original_mac = self._get_current_mac()
            test_mac = '00:11:22:33:44:55'
            
            # Try to change MAC
            self._execute(['ip', 'link', 'set', 'dev', self.wifi_interface, 'down'])
            self._execute(['ip', 'link', 'set', 'dev', self.wifi_interface, 'address', test_mac])
            self._execute(['ip', 'link', 'set', 'dev', self.wifi_interface, 'up'])
            
            # Verify change
            new_mac = self._get_current_mac()
            
            # Restore original MAC
            self._execute(['ip', 'link', 'set', 'dev', self.wifi_interface, 'down'])
            self._execute(['ip', 'link', 'set', 'dev', self.wifi_interface, 'address', original_mac])
            self._execute(['ip', 'link', 'set', 'dev', self.wifi_interface, 'up'])
            
            return new_mac.lower() == test_mac.lower()
        except:
            return False

    def _get_current_mac(self):
        """Get current MAC address"""
        try:
            with open(f'/sys/class/net/{self.wifi_interface}/address') as f:
                return f.read().strip()
        except:
            return None

    def _apply_initial_config(self):
        """Initial setup with error protection"""
        if not self._validate_interface():
            raise RuntimeError("Network interface not available")
            
        if self.operation_mode == 'noided':
            self._safe_mac_change()
            self._set_interface_mode('monitor')
            self._adjust_tx_power()
            self._channel_hop()
            self._sanitize_probes()
            self._throttle_traffic()

    def on_ui_setup(self, ui):
        if not self.enabled:
            return

        elements = [
            ('neuro_mode', 'Mode:', 'mode', self.operation_mode.capitalize()),
            ('neuro_mac', 'Next MAC:', 'mac_timer', 'Calculating...'),
            ('neuro_tx', 'TX:', 'tx_power', f'{self.current_tx_power}dBm'),
            ('neuro_chan', 'CH:', 'channel', str(self.current_channel)),
            ('neuro_stealth', 'Stealth:', 'stealth', str(self.stealth_level))
        ]
        
        for elem_id, label, pos_key, value in elements:
            if pos_key in self.ui_config:
                ui.add_element(elem_id, LabeledValue(
                    color=BLACK,
                    label=label,
                    value=value,
                    position=self.ui_config[pos_key],
                    label_font=fonts.Small,
                    text_font=fonts.Small
                ))

    def on_ui_update(self, ui):
        if not self.enabled:
            return

        ui.set('neuro_mode', self.operation_mode.capitalize())
        ui.set('neuro_mac', f"{self._next_mac_time()}m")
        ui.set('neuro_tx', f"{self.current_tx_power}dBm")
        ui.set('neuro_chan', str(self.current_channel))
        ui.set('neuro_stealth', str(self.stealth_level))

    def on_wifi_update(self, agent, access_points):
        if self.enabled:
            self._adapt_stealth(access_points)  # New: Adapt based on env
            self._check_wids(access_points)
            
            # Filter whitelisted APs to avoid pwning home nets
            target_aps = [ap for ap in access_points if ap.get('essid', '') not in self.whitelist_ssids]
            
            if self.operation_mode == 'noided' or self.operation_mode == 'stealth':
                self._safe_mac_change()
                if self.hw_caps['injection'] and random.random() < self.deauth_throttle:  # Throttle for stealth, only if injection
                    # Hook into agent for deauth (assume agent has deauth method; customize if needed)
                    for ap in random.sample(target_aps, min(3, len(target_aps))):  # Burst 1-3 randomly
                        agent.deauth(ap['bssid'])  # Or integrate with bettercap API
                self._channel_hop()
                self._adjust_tx_power()
                self._sanitize_probes()
                self._throttle_traffic()

    def _adapt_stealth(self, access_points):
        num_aps = len(access_points)
        if num_aps > 20:  # Crowded area: go stealthier
            self.stealth_level = 3
            self.mac_change_interval = random.randint(300, 600)  # Shorter in crowds to evade
            self.deauth_throttle = 0.2  # Deauth fewer APs
        elif num_aps > 5:
            self.stealth_level = 2
            self.mac_change_interval = random.randint(600, 1800)
            self.deauth_throttle = 0.5
        else:
            self.stealth_level = 1
            self.mac_change_interval = random.randint(1800, 3600)
            self.deauth_throttle = 0.8  # Aggressive captures in quiet areas
        logging.debug(f"[Neurolyzer] Adapted stealth level: {self.stealth_level}, deauth throttle: {self.deauth_throttle}")

    def _check_wids(self, access_points):
        """WIDS detection with multiple fingerprint checks"""
        if time.time() - self.last_operations['wids_check'] < 300:
            return
            
        wids_triggers = set(wids.lower() for wids in self.options.get('wids_ssids', self.DEFAULT_WIDS))
        
        for ap in access_points:
            essid = ap.get('essid', '')
            if essid.lower() in wids_triggers:
                logging.warning(f"[Neurolyzer] WIDS detected: {essid}")
                self._evasion_protocol()
                break

        self.last_operations['wids_check'] = time.time()

    def _evasion_protocol(self):
        """Execute coordinated evasion measures"""
        logging.info("[Neurolyzer] Initiating evasion sequence")
        measures = [
            self._safe_mac_change,
            self._channel_hop,
            self._adjust_tx_power,
            lambda: time.sleep(random.randint(10, 30))
        ]
        
        try:
            for measure in random.sample(measures, k=3):
                measure()
        except Exception as e:
            logging.error(f"[Neurolyzer] Evasion protocol failed: {str(e)}")

    def _generate_valid_mac(self):
        """Create manufacturer-plausible MAC address"""
        try:
            if self.operation_mode == 'noided':
                oui = random.choice(self.DEFAULT_OUI).replace(':', '')
                return f"{oui[:2]}:{oui[2:4]}:{oui[4:6]}:" \
                       f"{random.randint(0,255):02x}:" \
                       f"{random.randint(0,255):02x}:" \
                       f"{random.randint(0,255):02x}"
            return ':'.join(f"{random.randint(0,255):02x}" for _ in range(6))
        except Exception as e:
            logging.error(f"[Neurolyzer] MAC generation failed: {str(e)}")
            return '00:00:00:00:00:00'

    def _channel_hop(self):
        """Channel selection with interference avoidance"""
        try:
            if time.time() - self.last_operations['channel_hop'] < 60:
                return
                
            valid_channels = self.hw_caps['supported_channels']
            if self.stealth_level == 1:  # Aggressive: hop to busy channels for more handshakes
                new_channel = random.choice([1, 6, 11, 36, 40]) if self.nexmon_enabled else random.choice(valid_channels)  # Include 5GHz if Nexmon
            else:  # Stealth: safe channels
                new_channel = random.choice(self.SAFE_CHANNELS)
            if self._execute(['iw', 'dev', self.wifi_interface, 'set', 'channel', str(new_channel)]):
                self.current_channel = new_channel
                self.last_operations['channel_hop'] = time.time()
        except Exception as e:
            logging.error(f"[Neurolyzer] Channel hop failed: {str(e)}")

    def _set_interface_mode(self, mode):
        """Safe mode transition with validation"""
        try:
            if mode not in ['managed', 'monitor'] or not self.hw_caps['monitor_mode']:
                return
                
            current_mode = self._current_interface_mode()
            if current_mode != mode:
                if self._execute(['iw', 'dev', self.wifi_interface, 'set', 'type', mode]):
                    logging.debug(f"[Neurolyzer] Interface mode set to {mode}")
        except Exception as e:
            logging.error(f"[Neurolyzer] Mode change failed: {str(e)}")

    def _current_interface_mode(self):
        """Detect current interface mode safely"""
        try:
            info = self._execute(['iw', 'dev', self.wifi_interface, 'info'])
            return 'monitor' if info and 'monitor' in info.stdout else 'managed'
        except:
            return 'managed'

    def _sanitize_probes(self):
        """Filter sensitive probe requests"""
        try:
            if self.probe_blacklist:
                with open('/tmp/neuro_filter', 'w') as f:
                    f.write('\n'.join(self.probe_blacklist))
                
                self._execute([
                    'hcxdumptool', '-i', self.wifi_interface,
                    '--filterlist=/tmp/neuro_filter', '--filtermode=2'
                ])
        except Exception as e:
            logging.error(f"[Neurolyzer] Probe filtering error: {str(e)}")

    def _throttle_traffic(self):
        """Limit packet rates for stealth"""
        try:
            self._execute([
                'tc', 'qdisc', 'replace',
                'dev', self.wifi_interface, 'root', 'pfifo_fast', 'limit', '100'
            ])
        except Exception as e:
            logging.error(f"[Neurolyzer] Traffic shaping failed: {str(e)}")

    def _random_operation(self):
        """Randomize operational parameters safely"""
        try:
            actions = [
                self._adjust_tx_power,
                self._channel_hop,
                self._safe_mac_change,
                lambda: None
            ]
            random.choice(actions)()
        except Exception as e:
            logging.error(f"[Neurolyzer] Random operation failed: {str(e)}")

    def _next_mac_time(self):
        try:
            return max(0, int((self.last_operations['mac_change'] + self.mac_change_interval - time.time()) // 60))
        except:
            return 0

    def on_unload(self, ui=None):
        """Enhanced cleanup with resource release"""
        try:
            if self.enabled:
                logging.info("[Neurolyzer] Restoring network configurations")
                self._execute(['tc', 'qdisc', 'del', 'dev', self.wifi_interface, 'root'])
                self._set_interface_mode('monitor')
        except Exception as e:
            logging.error(f"[Neurolyzer] Cleanup failed: {str(e)}")
        finally:
            self._release_lock()
