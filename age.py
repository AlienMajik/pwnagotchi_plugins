import os
import json
import logging
import time
import random

import pwnagotchi
import pwnagotchi.plugins as plugins
import pwnagotchi.ui.faces as faces
import pwnagotchi.ui.fonts as fonts
from pwnagotchi.ui.components import LabeledValue
from pwnagotchi.ui.view import BLACK

class Age(plugins.Plugin):
    __author__ = 'AlienMajik'
    __version__ = '2.0.2'
    __license__ = 'MIT'
    __description__ = ('Enhanced plugin with achievement tiers, configurable titles, decay mechanics, '
                       'progress tracking, and dynamic status messages.')

    DEFAULT_AGE_TITLES = {
        1000: "Neon Spawn",
        2000: "Script Kiddie",
        5000: "WiFi Outlaw", 
        10000: "Data Raider",
        25000: "Prophet",
        33333: "Off the Grid"
    }

    DEFAULT_STRENGTH_TITLES = {
        500: "Fleshbag",
        1500: "Lightweight",
        2000: "Deauth King",
        2500: "Handshake Hunter",
        3333: "Unstoppable"
    }

    def __init__(self):
        # Default positions (x, y)
        self.default_positions = {
            'age': (10, 40),
            'strength': (80, 40),
            'points': (10, 60),
            'stars': (10, 80),
        }
        
        self.epochs = 0
        self.train_epochs = 0
        self.network_points = 0
        self.handshake_count = 0
        self.last_active_epoch = 0
        self.data_path = '/root/age_strength.json'
        self.log_path = '/root/network_points.log'
        self.handshake_dir = '/home/pi/handshakes'
        
        # Configurable settings with defaults
        self.max_stars = 5
        self.star_interval = 1000
        self.decay_interval = 50
        self.decay_amount = 10
        self.age_titles = self.DEFAULT_AGE_TITLES
        self.strength_titles = self.DEFAULT_STRENGTH_TITLES

    def on_loaded(self):
        # Load configuration with fallbacks
        self.max_stars = self.options.get('max_stars', 5)
        self.star_interval = self.options.get('star_interval', 1000)
        self.decay_interval = self.options.get('decay_interval', 50)
        self.decay_amount = self.options.get('decay_amount', 10)
        self.age_titles = self.options.get('age_titles', self.DEFAULT_AGE_TITLES)
        self.strength_titles = self.options.get('strength_titles', self.DEFAULT_STRENGTH_TITLES)
        
        self.load_data()
        self.initialize_handshakes()

    def initialize_handshakes(self):
        if self.handshake_count == 0 and os.path.isdir(self.handshake_dir):
            existing = [f for f in os.listdir(self.handshake_dir) if f.endswith('.pcap')]
            if existing:
                self.handshake_count = len(existing)
                logging.info(f"[Age] Initialized with {self.handshake_count} handshakes")
                self.save_data()

    def get_age_title(self):
        thresholds = sorted(self.age_titles.keys(), reverse=True)
        for t in thresholds:
            if self.epochs >= t:
                return self.age_titles[t]
        return "Unborn"

    def get_strength_title(self):
        thresholds = sorted(self.strength_titles.keys(), reverse=True)
        for t in thresholds:
            if self.train_epochs >= t:
                return self.strength_titles[t]
        return "Untrained"

    def random_motivational_quote(self):
        quotes = [
            "Keep going, you're crushing it!",
            "You're a WiFi wizard in the making!",
            "More handshakes, more power!",
            "Don't stop now, you're almost there!",
            "Keep evolving, don't let decay catch you!"
        ]
        return random.choice(quotes)

    def random_inactivity_message(self, points_lost):
        messages = [
            "Time to wake up, you're rusting!",
            "Decayed by {points_lost}, keep it active!",
            "Stale, but you can still revive!",
            "Don't let inactivity hold you back!",
            "Keep moving, no room for decay!"
        ]
        return random.choice(messages).format(points_lost=points_lost)

    def check_achievements(self, agent):
        current_age = self.get_age_title()
        current_strength = self.get_strength_title()
        
        if current_age != self.prev_age_title:
            agent.view().set('face', faces.HAPPY)
            agent.view().set('status', f"🎉 {current_age} Achieved! {self.random_motivational_quote()}")
            self.prev_age_title = current_age
            
        if current_strength != self.prev_strength_title:
            agent.view().set('face', faces.MOTIVATED)
            agent.view().set('status', f"💪 Evolved to {current_strength}!")
            self.prev_strength_title = current_strength

    def apply_decay(self, agent):
        inactive_epochs = self.epochs - self.last_active_epoch
        if inactive_epochs >= self.decay_interval:
            decay_cycles = inactive_epochs // self.decay_interval
            points_lost = decay_cycles * self.decay_amount
            self.network_points = max(0, self.network_points - points_lost)
            
            if points_lost > 0:
                agent.view().set('face', faces.SAD)
                agent.view().set('status', self.random_inactivity_message(points_lost))
                self.last_active_epoch = self.epochs
                self.save_data()

    def on_ui_setup(self, ui):
        def get_position(element):
            x = self.options.get(
                f"{element}_x",
                self.options.get(
                    f"{element}_x_coord",  # Backwards compatibility
                    self.default_positions[element][0]
                )
            )
            y = self.options.get(
                f"{element}_y",
                self.options.get(
                    f"{element}_y_coord",  # Backwards compatibility
                    self.default_positions[element][1]
                )
            )
            return (int(x), int(y))

        positions = {
            'age': get_position('age'),
            'strength': get_position('strength'),
            'points': get_position('points'),
            'stars': get_position('stars'),
        }

        ui.add_element('Age', LabeledValue(
            color=BLACK, label='Age', value="Newborn",
            position=positions['age'], label_font=fonts.Bold, text_font=fonts.Medium))

        ui.add_element('Strength', LabeledValue(
            color=BLACK, label='Str', value="Rookie",
            position=positions['strength'], label_font=fonts.Bold, text_font=fonts.Medium))

        ui.add_element('Points', LabeledValue(
            color=BLACK, label='★ Pts', value="0",
            position=positions['points'], label_font=fonts.Bold, text_font=fonts.Medium))

        ui.add_element('ReP', LabeledValue(
            color=BLACK, label='ReP', value="★",
            position=positions['stars'], label_font=fonts.Bold, text_font=fonts.Medium))

    def on_ui_update(self, ui):
        ui.set('Age', self.get_age_title())
        ui.set('Strength', self.get_strength_title())
        ui.set('Points', self.abrev_number(self.network_points))
        ui.set('ReP', self.get_star_string())

    def on_epoch(self, agent, epoch, epoch_data):
        self.epochs += 1
        self.train_epochs += 1 if self.epochs % 10 == 0 else 0
        
        self.apply_decay(agent)
        self.check_achievements(agent)
        
        if self.epochs % 100 == 0:
            self.age_checkpoint(agent)
        
        self.save_data()

    def age_checkpoint(self, agent):
        # Status update at every epoch milestone (e.g., every 100 epochs)
        view = agent.view()
        view.set('face', faces.HAPPY)
        view.set('status', f"Epoch milestone: {self.epochs} epochs!")
        view.update(force=True)

    def on_handshake(self, agent, *args):
        self.last_active_epoch = self.epochs
        enc = args[2].get('encryption', '').lower()
        
        points = {
            'wpa3': 10, 'wpa2': 5, 
            'wep': 2, 'wpa': 2
        }.get(enc, 1)
        
        self.network_points += points
        self.handshake_count += 1
        
        # Log details
        with open(self.log_path, 'a') as f:
            essid = args[2].get('essid', 'unknown')
            f.write(f"{time.time()},{essid},{enc},{points}\n")
        
        self.new_star_checkpoint(agent)
        self.save_data()

    def new_star_checkpoint(self, agent):
        stars = self.get_stars_count()
        if stars > self.prev_stars:
            symbol = self.get_symbol_for_handshakes()
            agent.view().set('face', faces.EXCITED)
            agent.view().set('status', f"New {symbol} Tier Achieved!")
            self.prev_stars = stars

    def load_data(self):
        try:
            if os.path.exists(self.data_path):
                with open(self.data_path, 'r') as f:
                    data = json.load(f)
                    
                    # Handle old format compatibility
                    self.epochs = data.get('epochs', data.get('epochs_lived', 0))
                    self.train_epochs = data.get('train_epochs', data.get('epochs_trained', 0))
                    self.network_points = data.get('points', data.get('network_points', 0))
                    self.handshake_count = data.get('handshakes', data.get('handshake_count', 0))
                    
                    # New fields with defaults
                    self.last_active_epoch = data.get('last_active', 0)
                    self.prev_age_title = data.get('prev_age', self.get_age_title())
                    self.prev_strength_title = data.get('prev_strength', self.get_strength_title())
                    self.prev_stars = data.get('prev_stars', self.get_stars_count())

                # Migrate old format to new format
                if 'epochs_lived' in data:
                    self.save_data()  # Resave in new format
                    logging.info("[Age] Migrated old data format to new format")

        except Exception as e:
            logging.error(f"[Age] Load error: {str(e)}")

    def save_data(self):
        data = {
            'epochs': self.epochs,
            'train_epochs': self.train_epochs,
            'points': self.network_points,
            'handshakes': self.handshake_count,
            'last_active': self.last_active_epoch,
            'prev_age': self.get_age_title(),
            'prev_strength': self.get_strength_title(),
            'prev_stars': self.get_stars_count(),
        }
        try:
            with open(self.data_path, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logging.error(f"[Age] Save error: {str(e)}")

    def get_stars_count(self):
        return min(self.handshake_count // self.star_interval, self.max_stars)

    def get_symbol_for_handshakes(self):
        return '♣' if self.handshake_count >= 10000 else '♦' if self.handshake_count >= 5000 else '★'

    def get_star_string(self):
        return self.get_symbol_for_handshakes() * self.get_stars_count()

    def abrev_number(self, num):
        for unit in ['','K','M','B']:
            if abs(num) < 1000:
                return f"{num:.1f}{unit}".rstrip('.0')
            num /= 1000.0
        return f"{num:.1f}T"




