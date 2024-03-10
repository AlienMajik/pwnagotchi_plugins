import logging
import subprocess
import time

import pwnagotchi.plugins as plugins
from pwnagotchi.ui.components import LabeledValue
from pwnagotchi.ui.view import BLACK
import pwnagotchi.ui.fonts as fonts

class Neurolyzer(plugins.Plugin):
    __author__ = 'AlienMajik'
    __version__ = '1.1.1'
    __license__ = 'GPL3'
    __description__ = "A plugin for enhanced stealth and privacy."

    def __init__(self):
        self.enabled = False
        self.wifi_interface = 'wlan0'
        self.operation_mode = 'stealth'  # 'normal' or 'stealth'
        self.mac_change_interval = 3600  # Interval in seconds
        self.last_mac_change_time = time.time()
        # UI custom positions
        self.mode_label_position = (0, 0)
        self.next_mac_change_label_position = (0, 0)

    def on_loaded(self):
        self.enabled = self.options.get('enabled', False)
        self.wifi_interface = self.options.get('wifi_interface', 'wlan0')
        self.operation_mode = self.options.get('operation_mode', 'stealth')
        self.mac_change_interval = self.options.get('mac_change_interval', 3600)
        # UI positions from config
        self.mode_label_position = (self.options.get('mode_label_x', 0), self.options.get('mode_label_y', 0))
        self.next_mac_change_label_position = (self.options.get('next_mac_change_label_x', 0), self.options.get('next_mac_change_label_y', 10))

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

        remaining_time = self.mac_change_interval - (time.time() - self.last_mac_change_time)
        self.next_mac_change_label.set(
            "%dm" % (remaining_time // 60)
        )
        self.mode_label.set(self.operation_mode.capitalize())

    def randomize_mac(self):
        if self.operation_mode != 'stealth' or not self.enabled:
            return

        try:
            subprocess.run(['macchanger', '-r', self.wifi_interface], check=True)
            self.last_mac_change_time = time.time()
            logging.info(f"[Neurolyzer] MAC address randomized for {self.wifi_interface}.")
        except subprocess.CalledProcessError as e:
            logging.error(f"[Neurolyzer] MAC randomization failed: {e}")

    def on_unload(self):
        if not self.enabled:
            return
        logging.info("[Neurolyzer] Plugin unloaded.")
