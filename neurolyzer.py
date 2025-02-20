import logging
import subprocess
import time
import random

import pwnagotchi.plugins as plugins
from pwnagotchi.ui.components import LabeledValue
from pwnagotchi.ui.view import BLACK
import pwnagotchi.ui.fonts as fonts

class Neurolyzer(plugins.Plugin):
    __author__ = 'AlienMajik'
    __version__ = '1.5.1'
    __license__ = 'GPL3'
    __description__ = "A plugin for enhanced stealth and privacy using realistic OUIs."

    def __init__(self):
        self.enabled = False
        self.wifi_interface = 'wlan0'
        self.operation_mode = 'stealth'  # 'normal' or 'stealth'
        self.mac_change_interval = 3600  # Interval in seconds
        self.last_mac_change_time = time.time()
        self.next_mac_change_time = self.last_mac_change_time + self.mac_change_interval
        self.last_random_mac = None

        # UI custom positions
        self.mode_label_position = (0, 0)
        self.next_mac_change_label_position = (0, 0)

    def on_loaded(self):
        self.enabled = self.options.get('enabled', False)
        self.wifi_interface = self.options.get('wifi_interface', 'wlan0')
        self.operation_mode = self.options.get('operation_mode', 'stealth')
        self.mac_change_interval = self.options.get('mac_change_interval', 3600)
        self.next_mac_change_time = time.time() + self.mac_change_interval

        # UI positions from config
        self.mode_label_position = (
            self.options.get('mode_label_x', 0),
            self.options.get('mode_label_y', 0)
        )
        self.next_mac_change_label_position = (
            self.options.get('next_mac_change_label_x', 0),
            self.options.get('next_mac_change_label_y', 10)
        )

        if self.enabled:
            logging.info("[Neurolyzer] Plugin loaded. Operating in %s mode." % self.operation_mode)
            self.randomize_mac()  # Initial MAC address randomization
        else:
            logging.info("[Neurolyzer] Plugin not enabled.")

    def on_ui_setup(self, ui):
        if not self.enabled:
            return

        self.mode_label = LabeledValue(
            color=BLACK,
            label="Mode:",
            value=self.operation_mode.capitalize(),
            position=self.mode_label_position,
            label_font=fonts.Small,
            text_font=fonts.Small
        )
        ui.add_element('neurolyzer_mode', self.mode_label)

        self.next_mac_change_label = LabeledValue(
            color=BLACK,
            label="Next MAC change:",
            value="Calculating...",
            position=self.next_mac_change_label_position,
            label_font=fonts.Small,
            text_font=fonts.Small
        )
        ui.add_element('neurolyzer_next_mac', self.next_mac_change_label)

    def on_ui_update(self, ui):
        if not self.enabled:
            return

        remaining_time = self.next_mac_change_time - time.time()
        if remaining_time <= 0:
            self.randomize_mac()
            self.next_mac_change_time = time.time() + self.randomize_interval()

        # Update UI labels by directly setting the value attribute.
        self.next_mac_change_label.value = "%dm" % (remaining_time // 60)
        self.mode_label.value = self.operation_mode.capitalize()

    def randomize_mac(self):
        if self.operation_mode != 'stealth' or not self.enabled:
            return

        new_mac = self.generate_realistic_mac()

        if 'mon' in self.wifi_interface.lower():
            # For monitor mode interfaces, switch temporarily to managed mode.
            try:
                subprocess.run(['sudo', 'ip', 'link', 'set', 'dev', self.wifi_interface, 'down'],
                               check=True, stderr=subprocess.DEVNULL)
            except subprocess.CalledProcessError as e:
                logging.warning(f"[Neurolyzer] Failed to bring down interface {self.wifi_interface}: {e}")

            try:
                subprocess.run(['sudo', 'iwconfig', self.wifi_interface, 'mode', 'managed'],
                               check=True, stderr=subprocess.DEVNULL)
            except subprocess.CalledProcessError as e:
                logging.error(f"[Neurolyzer] Failed to set {self.wifi_interface} to managed mode: {e}")
                return

            try:
                subprocess.run(['sudo', 'ip', 'link', 'set', 'dev', self.wifi_interface, 'address', new_mac],
                               check=True, stderr=subprocess.DEVNULL)
            except subprocess.CalledProcessError as e:
                logging.error(f"[Neurolyzer] MAC address change failed: {e}")
                return

            try:
                subprocess.run(['sudo', 'ip', 'link', 'set', 'dev', self.wifi_interface, 'up'],
                               check=True, stderr=subprocess.DEVNULL)
            except subprocess.CalledProcessError as e:
                logging.error(f"[Neurolyzer] Failed to bring up interface {self.wifi_interface}: {e}")
                return

            # Optionally, switch back to monitor mode if needed:
            # try:
            #     subprocess.run(['iwconfig', self.wifi_interface, 'mode', 'monitor'],
            #                    check=True, stderr=subprocess.DEVNULL)
            # except subprocess.CalledProcessError as e:
            #     logging.warning(f"[Neurolyzer] Failed to set {self.wifi_interface} back to monitor mode: {e}")
        else:
            # For non-monitor mode interfaces, use the standard sequence.
            try:
                subprocess.run(['sudo', 'ip', 'link', 'set', 'dev', self.wifi_interface, 'down'],
                               check=True, stderr=subprocess.DEVNULL)
            except subprocess.CalledProcessError as e:
                logging.warning(f"[Neurolyzer] Failed to bring down interface {self.wifi_interface}: {e}")

            try:
                subprocess.run(['sudo', 'ip', 'link', 'set', 'dev', self.wifi_interface, 'address', new_mac],
                               check=True, stderr=subprocess.DEVNULL)
            except subprocess.CalledProcessError as e:
                logging.error(f"[Neurolyzer] MAC address change failed: {e}")
                return

            try:
                subprocess.run(['sudo', 'ip', 'link', 'set', 'dev', self.wifi_interface, 'up'],
                               check=True, stderr=subprocess.DEVNULL)
            except subprocess.CalledProcessError as e:
                logging.error(f"[Neurolyzer] Failed to bring up interface {self.wifi_interface}: {e}")
                return

        self.last_mac_change_time = time.time()
        self.last_random_mac = new_mac
        logging.info(f"[Neurolyzer] MAC address changed to {new_mac} for {self.wifi_interface}.")

    def generate_realistic_mac(self):
        """Generate a stealthy MAC address with a less identifiable OUI."""
        mac = [
            0x00, 0x25, 0x96,
            random.randint(0x00, 0x7F),
            random.randint(0x00, 0x7F),
            random.randint(0x00, 0x7F)
        ]
        mac_address = ':'.join(f"{byte:02x}" for byte in mac)
        return mac_address

    def randomize_interval(self):
        """Return a random interval between 30 minutes and 2 hours."""
        return random.randint(1800, 7200)

    def on_unload(self):
        if not self.enabled:
            return
        logging.info("[Neurolyzer] Plugin unloaded.")

