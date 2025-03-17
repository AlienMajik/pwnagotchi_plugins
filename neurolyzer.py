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
    __version__ = '1.5.2'
    __license__ = 'GPL3'
    __description__ = "Advanced WIDS/WIPS evasion system with hardware-aware adaptive countermeasures"

    DEFAULT_OUI = [
        '00:14:22', '34:AB:95', 'DC:A6:32',
        '00:1A:11', '08:74:02', '50:32:37'
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
            'iproute2': True
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
            'channel': (0, 30)
        }

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
            new_mac = self._generate_valid_mac()
            
            # Use alternate method if primary fails
            sequence = [
                ['ip', 'link', 'set', 'dev', self.wifi_interface, 'down'],
                ['ip', 'link', 'set', 'dev', self.wifi_interface, 'address', new_mac],
                ['ip', 'link', 'set', 'dev', self.wifi_interface, 'up'],
                ['ifconfig', self.wifi_interface, 'down'],
                ['ifconfig', self.wifi_interface, 'hw', 'ether', new_mac],
                ['ifconfig', self.wifi_interface, 'up']
            ]
            
            for cmd in sequence[:3] if self.hw_caps['iproute2'] else sequence[3:]:
                if not self._execute(cmd):
                    break
            else:
                verified_mac = self._get_current_mac()
                if verified_mac.lower() != new_mac.lower():  # Case-insensitive comparison
                    logging.error(f"[Neurolyzer] MAC verification failed (expected: {new_mac.lower()}, got: {verified_mac.lower()})")
                    self._release_lock()
                    return
                
                self.last_operations['mac_change'] = time.time()
                self.current_mac = new_mac
                logging.info(f"[Neurolyzer] MAC rotated to {new_mac.lower()}")  # Log in lowercase for consistency

        except Exception as e:
            logging.error(f"[Neurolyzer] MAC rotation failed: {str(e)}")
        finally:
            self._release_lock()

    def _adjust_tx_power(self):
        """Hardware-adaptive TX power control"""
        if not self.hw_caps['tx_power']['supported']:
            return

        try:
            current_power = self._current_tx_power()
            valid_powers = [p for p in self.options.get('tx_power_levels', [])
                            if self.hw_caps['tx_power']['min'] <= p <= self.hw_caps['tx_power']['max']]
            
            if valid_powers:
                new_power = random.choice(valid_powers)
                if new_power != current_power:
                    # Try multiple control methods
                    self._execute(['iw', 'dev', self.wifi_interface, 'set', 'txpower', 'fixed', str(new_power)]) or \
                    self._execute(['iwconfig', self.wifi_interface, 'txpower', str(new_power)])
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
        self.enabled = self.options.get('enabled', True)

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
            ('neuro_chan', 'CH:', 'channel', str(self.current_channel))
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

    def on_wifi_update(self, agent, access_points):
        if self.enabled:
            if self.operation_mode == 'noided':
                # Keep existing behavior for noided mode
                self._safe_mac_change()
                self._channel_hop()
                self._adjust_tx_power()
                self._sanitize_probes()
                self._throttle_traffic()
            elif self.operation_mode == 'stealth':
                # Only perform MAC randomization in stealth mode
                self._safe_mac_change()

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
                
            safe_channels = [c for c in self.SAFE_CHANNELS if c in self.hw_caps['supported_channels']]
            valid_channels = safe_channels or self.hw_caps['supported_channels'][-3:]
            
            if valid_channels:
                new_channel = random.choice(valid_channels)
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


