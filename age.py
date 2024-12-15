import os
import json
import logging

import pwnagotchi
import pwnagotchi.plugins as plugins
import pwnagotchi.ui.faces as faces
import pwnagotchi.ui.fonts as fonts
from pwnagotchi.ui.components import LabeledValue
from pwnagotchi.ui.view import BLACK

class Age(plugins.Plugin):
    __author__ = 'AlienMajik'
    __version__ = '1.0.4'
    __license__ = 'MIT'
    __description__ = 'A plugin that adds age, strength, and network points stats with a dedicated log of point increments.'

    def __init__(self):
        self.epochs = 0
        self.train_epochs = 0
        self.network_points = 0  # Stat to track points from network encounters
        self.data_path = '/root/age_strength.json'
        self.log_path = '/root/network_points.log'  # Dedicated log file

    def on_loaded(self):
        # Load stored data from file if available
        self.load_data()

    def on_ui_setup(self, ui):
        ui.add_element('Age', LabeledValue(
            color=BLACK,
            label='♥ Age',
            value=0,
            position=(int(self.options["age_x_coord"]), int(self.options["age_y_coord"])),
            label_font=fonts.Bold,
            text_font=fonts.Medium
        ))
        ui.add_element('Strength', LabeledValue(
            color=BLACK,
            label='Str',
            value=0,
            position=(int(self.options["str_x_coord"]), int(self.options["str_y_coord"])),
            label_font=fonts.Bold,
            text_font=fonts.Medium
        ))
        # Using a simpler label instead of an emoji for points
        points_x = int(self.options.get("points_x_coord", 10))
        points_y = int(self.options.get("points_y_coord", 100))
        ui.add_element('Points', LabeledValue(
            color=BLACK,
            label='★ Pts',  # ASCII-friendly label
            value=0,
            position=(points_x, points_y),
            label_font=fonts.Bold,
            text_font=fonts.Medium
        ))

    def on_unload(self, ui):
        with ui._lock:
            ui.remove_element('Age')
            ui.remove_element('Strength')
            ui.remove_element('Points')
        # Save data on unload
        self.save_data()

    def on_ui_update(self, ui):
        ui.set('Age', str(self.abrev_number(self.epochs)))
        ui.set('Strength', str(self.abrev_number(self.train_epochs)))
        ui.set('Points', str(self.abrev_number(self.network_points)))

    def on_epoch(self, agent, epoch, epoch_data):
        self.epochs += 1
        # Example: Increase strength every 10 epochs
        if self.epochs % 10 == 0:
            self.train_epochs += 1

        # Checkpoints
        if self.epochs % 100 == 0:
            self.age_checkpoint(agent)
        if self.train_epochs != 0 and self.train_epochs % 10 == 0:
            self.strength_checkpoint(agent)

        # Save data each epoch
        self.save_data()

    def on_handshake(self, agent, filename, access_point, client):
        # Determine encryption type and award points
        enc = access_point.get('encryption', '').lower()
        essid = access_point.get('essid', 'unknown')
        old_points = self.network_points

        if 'wpa3' in enc:
            increment = 10
            desc = "WPA3"
        elif 'wpa2' in enc:
            increment = 5
            desc = "WPA2"
        elif 'wep' in enc or 'wpa' in enc:
            increment = 2
            desc = "WEP/WPA"
        else:
            increment = 1
            desc = "Open/Unknown"

        self.network_points += increment
        self.display_encounter(agent, f"{desc} network discovered! +{increment} pts")

        # Log the event to a dedicated file
        with open(self.log_path, 'a') as f:
            f.write(f"ESSID: {essid}, ENC: {enc}, Points Gained: {increment}, Total Points: {self.network_points}\n")

        self.save_data()

    def abrev_number(self, num):
        if num < 100000:
            return str(num)
        else:
            magnitude = 0
            while abs(num) >= 1000:
                magnitude += 1
                num /= 1000.0
            abbr = ['', 'K', 'M', 'B', 'T', 'P'][magnitude]
            return '{}{}'.format('{:.2f}'.format(num).rstrip('0').rstrip('.'), abbr)

    def age_checkpoint(self, agent):
        view = agent.view()
        view.set('face', faces.HAPPY)
        view.set('status', f"Living for them {self.abrev_number(self.epochs)} epochs!")
        view.update(force=True)

    def strength_checkpoint(self, agent):
        view = agent.view()
        view.set('face', faces.MOTIVATED)
        view.set('status', f"Getting them Gains Sucka!\nThey Drew First {self.abrev_number(self.train_epochs)} Epochs!")
        view.update(force=True)

    def display_encounter(self, agent, message):
        # A helper method to display a quick status update when points are awarded
        view = agent.view()
        view.set('face', faces.EXCITED)
        view.set('status', message)
        view.update(force=True)

    def load_data(self):
        if os.path.exists(self.data_path):
            with open(self.data_path, 'r') as f:
                data = json.load(f)
                self.epochs = data.get('epochs_lived', 0)
                self.train_epochs = data.get('epochs_trained', 0)
                self.network_points = data.get('network_points', 0)

    def save_data(self):
        data = {
            'epochs_lived': self.epochs,
            'epochs_trained': self.train_epochs,
            'network_points': self.network_points
        }
        with open(self.data_path, 'w') as f:
            json.dump(data, f)
