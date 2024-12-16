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
    __version__ = '1.0.7'
    __license__ = 'MIT'
    __description__ = 'A plugin that adds age, strength, network points, stat display, and tiered symbols for stars based on handshake counts.'

    def __init__(self):
        self.epochs = 0
        self.train_epochs = 0
        self.network_points = 0
        self.handshake_count = 0
        self.data_path = '/root/age_strength.json'
        self.log_path = '/root/network_points.log'
        self.max_stars = 5
        self.star_interval = 1000  # 1000 handshakes per star
        self.handshake_dir = '/root/handshakes'  # directory containing old handshake files

    def on_loaded(self):
        self.load_data()
        # Initialize handshake_count from existing handshakes if needed
        if self.handshake_count == 0 and os.path.isdir(self.handshake_dir):
            existing_handshakes = [f for f in os.listdir(self.handshake_dir) if os.path.isfile(os.path.join(self.handshake_dir, f))]
            if existing_handshakes:
                self.handshake_count = len(existing_handshakes)
                logging.info(f"[Age plugin] Initialized handshake_count from existing handshakes: {self.handshake_count}")
                self.save_data()

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
        ui.add_element('Points', LabeledValue(
            color=BLACK,
            label='★ Pts',
            value=0,
            position=(int(self.options.get("points_x_coord", 10)), int(self.options.get("points_y_coord", 100))),
            label_font=fonts.Bold,
            text_font=fonts.Medium
        ))
        # Changed from 'Stars' to 'Stat'
        ui.add_element('Stat', LabeledValue(
            color=BLACK,
            label='Stat',
            value=self.get_star_string(),
            position=(int(self.options.get("stars_x_coord", 10)), int(self.options.get("stars_y_coord", 120))),
            label_font=fonts.Bold,
            text_font=fonts.Medium
        ))

    def on_unload(self, ui):
        with ui._lock:
            ui.remove_element('Age')
            ui.remove_element('Strength')
            ui.remove_element('Points')
            ui.remove_element('Stat')  # changed from 'Stars'
        self.save_data()

    def on_ui_update(self, ui):
        ui.set('Age', str(self.abrev_number(self.epochs)))
        ui.set('Strength', str(self.abrev_number(self.train_epochs)))
        ui.set('Points', str(self.abrev_number(self.network_points)))
        ui.set('Stat', self.get_star_string())  # changed from 'Stars'

    def on_epoch(self, agent, epoch, epoch_data):
        self.epochs += 1
        if self.epochs % 10 == 0:
            self.train_epochs += 1

        if self.epochs % 100 == 0:
            self.age_checkpoint(agent)
        if self.train_epochs != 0 and self.train_epochs % 10 == 0:
            self.strength_checkpoint(agent)

        self.save_data()

    def on_handshake(self, agent, filename, access_point, client):
        enc = access_point.get('encryption', '').lower()
        essid = access_point.get('essid', 'unknown')

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

        old_stars = self.get_stars_count()
        self.handshake_count += 1
        new_stars = self.get_stars_count()
        if new_stars > old_stars:
            self.new_star_checkpoint(agent, new_stars)

        with open(self.log_path, 'a') as f:
            f.write(f"ESSID: {essid}, ENC: {enc}, Points Gained: {increment}, Total Points: {self.network_points}, Handshake Count: {self.handshake_count}\n")

        self.save_data()

    def new_star_checkpoint(self, agent, stars):
        if stars <= self.max_stars:
            symbol = self.get_symbol_for_handshakes()
            star_str = symbol * stars
            view = agent.view()
            view.set('face', faces.HAPPY)
            view.set('status', f"You've earned a new star! Now at {star_str}")
            view.update(force=True)

    def get_stars_count(self):
        stars = self.handshake_count // self.star_interval
        if stars > self.max_stars:
            stars = self.max_stars
        return stars

    def get_symbol_for_handshakes(self):
        if self.handshake_count >= 10000:
            return '♣'
        elif self.handshake_count >= 5000:
            return '♦'
        else:
            return '★'

    def get_star_string(self):
        star_count = self.get_stars_count()
        symbol = self.get_symbol_for_handshakes()
        return symbol * star_count

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
                self.handshake_count = data.get('handshake_count', 0)

    def save_data(self):
        data = {
            'epochs_lived': self.epochs,
            'epochs_trained': self.train_epochs,
            'network_points': self.network_points,
            'handshake_count': self.handshake_count
        }
        with open(self.data_path, 'w') as f:
            json.dump(data, f, indent=2)

