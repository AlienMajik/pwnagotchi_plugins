import logging
import os
import subprocess
import json
import time
from datetime import datetime

import pwnagotchi.plugins as plugins
import pwnagotchi.ui.fonts as fonts
from pwnagotchi.ui.components import LabeledValue
from pwnagotchi.ui.view import BLACK

class ADSBSniffer(plugins.Plugin):
    __author__ = '4li3nMaJ1k'
    __version__ = '0.1.0'
    __license__ = 'GPL3'
    __description__ = 'A plugin that captures ADS-B data from aircraft using RTL-SDR and logs it.'

    def __init__(self):
        self.options = {
            'timer': 60,  # Time interval in seconds for checking for new aircraft
            'aircraft_file': '/root/handshakes/adsb_aircraft.json',  # File to store detected aircraft information
            'adsb_x_coord': 160,
            'adsb_y_coord': 80
        }
        self.last_scan_time = 0
        self.data = {}

    def on_loaded(self):
        logging.info("[ADSB] ADSBSniffer plugin loaded.")
        if not os.path.exists(os.path.dirname(self.options['aircraft_file'])):
            os.makedirs(os.path.dirname(self.options['aircraft_file']))
        if not os.path.exists(self.options['aircraft_file']):
            with open(self.options['aircraft_file'], 'w') as f:
                json.dump({}, f)
        with open(self.options['aircraft_file'], 'r') as f:
            self.data = json.load(f)

    def on_ui_setup(self, ui):
        ui.add_element('ADSB', LabeledValue(color=BLACK,
                                            label='ADSB',
                                            value=" ",
                                            position=(self.options["adsb_x_coord"],
                                                      self.options["adsb_y_coord"]),
                                            label_font=fonts.Small,
                                            text_font=fonts.Small))

    def on_ui_update(self, ui):
        current_time = time.time()
        if current_time - self.last_scan_time >= self.options['timer']:
            self.last_scan_time = current_time
            result = self.scan()
            ui.set('ADSB', result)

    def scan(self):
        logging.info("[ADSB] Scanning for ADS-B signals...")
        cmd = "timeout 10s rtl_adsb"
        try:
            output = subprocess.check_output(cmd, stderr=subprocess.STDOUT, shell=True)
            aircrafts = self.parse_output(output.decode('utf-8'))
            return f"{len(aircrafts)} aircrafts detected"
        except subprocess.CalledProcessError as e:
            if e.returncode == 124:  # Graceful handling of the timeout exit status
                logging.info("[ADSB] Successfully completed ADS-B scan.")
                output = e.output.decode('utf-8')
                aircrafts = self.parse_output(output)
                return f"{len(aircrafts)} aircrafts detected"
            else:
                logging.error("[ADSB] Error running rtl_adsb: %s, output: %s", e, e.output.decode('utf-8'))
                return "Scan error"

    def parse_output(self, raw_data):
        aircrafts = []
        for line in raw_data.split('\n'):
            if line.strip():
                aircraft_data = line.split(',')
                if len(aircraft_data) >= 2:
                    hex_id, signal = aircraft_data[0], aircraft_data[1]
                    aircrafts.append({'hex': hex_id, 'signal_strength': signal})
                    self.data[hex_id] = {'last_seen': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                                         'signal_strength': signal}
        with open(self.options['aircraft_file'], 'w') as f:
            json.dump(self.data, f)
        return aircrafts

    def on_unload(self, ui):
        with ui._lock:
            ui.remove_element('ADSB')
