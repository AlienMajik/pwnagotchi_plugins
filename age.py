import os
import json
import logging
import time
import random
import threading

import pwnagotchi
import pwnagotchi.plugins as plugins
import pwnagotchi.ui.faces as faces
import pwnagotchi.ui.fonts as fonts
from pwnagotchi.ui.components import LabeledValue
from pwnagotchi.ui.view import BLACK

class Age(plugins.Plugin):
    __author__ = 'AlienMajik'
    __version__ = '4.0.0'
    __license__ = 'MIT'
    __description__ = ('Age plugin with prestige, random events, animated progress, '
                       'narrative lore, cheeky quotes, and a dedicated status display.')

    # --- Quote Library ---
    QUOTES = {
        'success': [          # Ash's cocky one-liners for victories
            "Groovy.",
            "Hail to the king, baby.",
            "Good. Bad. I'm the guy with the gun.",
            "Yo, she-bitch, let's go!",
            "Come get some.",
            "This is my BOOMSTICK!",
        ],
        'warning': [          # Monty Python denial / absurd warnings
            "It's just a flesh wound!",
            "I'm not dead!",
            "Run away! Run away!",
            "Bring out your dead!",
            "Ni!",
        ],
        'insult': [           # Pythonic insults for when things go wrong
            "Your mother was a hamster and your father smelt of elderberries!",
            "Strange women lying in ponds distributing swords is no basis for a system of government.",
        ],
        'ready': [            # Ready for action / rebirth
            "Shop smart. Shop S-Mart.",
            "Groovy.",
            "Come get some.",
        ],
        'random': [           # General absurdity
            "Strange women in ponds? No basis!",
            "Ni!",
            "It's just a flesh wound!",
            "I'm not dead!",
            "Bring out your dead!",
        ]
    }

    # Existing narrative lore for titles and events
    LORE_MESSAGES = {
        'age': {
            "Baby Steps": [
                "A newborn spark in the digital void.",
                "First breath of code, first taste of air.",
                "The journey of a thousand networks begins with a single packet."
            ],
            "Getting the Hang of It": [
                "You begin to understand the rhythm of the airwaves.",
                "Patterns emerge from the noise.",
                "The unseen currents start to make sense."
            ],
            "Neon Spawn": [
                "Born in the glow of city lights and stray signals.",
                "Neon pulses guide your way.",
                "You are a child of the urban data stream."
            ],
            "Script Kiddie": [
                "You wield the tools of others, but your hunger is your own.",
                "Copy, paste, learn. The cycle continues.",
                "Every master was once a beginner."
            ],
            "WiFi Outlaw": [
                "You dance on the edge of the law, where signals roam free.",
                "Outlaw of the airwaves, feared by routers everywhere.",
                "Your reputation precedes you."
            ],
            "Data Raider": [
                "You plunder the digital treasures of the unwary.",
                "Each handshake is a trophy, each network a conquest.",
                "Data flows like gold through your circuits."
            ],
            "Prophet": [
                "You see the patterns before they form.",
                "The future of connectivity whispers in your ear.",
                "Prophecies written in 802.11."
            ],
            "Off the Grid": [
                "You exist beyond the reach of conventional networks.",
                "Untraceable, unbound, free.",
                "The grid cannot contain you."
            ],
            "Multiversed": [
                "You have glimpsed the infinite layers of the digital multiverse.",
                "Every frequency, every dimension, yours to explore.",
                "Reality is just another network."
            ],
            "Intergalactic": [
                "Your legend echoes across the cosmos.",
                "From Earth to the stars, no signal is safe.",
                "You have become one with the universal datastream."
            ]
        },
        'strength': {
            "Sparring Novice": [
                "You spar with the basics, learning to strike.",
                "Every deauth is a lesson in humility.",
                "Weak, but eager."
            ],
            "Gear Tickler": [
                "You know how to make the hardware sing.",
                "Fingers dance on the edge of capability.",
                "The machines respond to your touch."
            ],
            "Fleshbag": [
                "Mortal, yet determined.",
                "You remember the warmth of flesh, but embrace the code.",
                "Humanity's last echo in your circuits."
            ],
            "Lightweight": [
                "You move swiftly, undetected.",
                "Weightless in the data stream.",
                "Speed is your ally."
            ],
            "Deauth King": [
                "You reign over the realm of disconnections.",
                "Routers tremble at your approach.",
                "King of the kick."
            ],
            "Handshake Hunter": [
                "You stalk your prey through the channels.",
                "No handshake escapes your grasp.",
                "Hunter of the airwaves."
            ],
            "Unstoppable": [
                "Nothing can slow your advance.",
                "Firewalls crumble, encryption yields.",
                "You are inevitable."
            ],
            "Rev-9": [
                "Liquid metal in the data stream, you adapt and overcome.",
                "A relentless hunter, always evolving.",
                "Rev-9: the ultimate form."
            ],
            "Kuato": [
                "You are the living manifestation of machine intelligence.",
                "Kuato lives!",
                "Your mind expands beyond comprehension."
            ]
        },
        'events': {
            'windfall': [
                "A sudden surge of energy floods your circuits.",
                "Fortune smiles upon you.",
                "Free points from the digital ether!"
            ],
            'hackers_block': [
                "A moment of doubt clouds your processor.",
                "The code refuses to flow.",
                "Hacker's block strikes!"
            ],
            'time_warp': [
                "Reality bends around you; time accelerates.",
                "You feel yourself advancing faster.",
                "Time warp engaged!"
            ],
            'ghost': [
                "A ghost passes through your core, swapping your traits.",
                "Your personality shimmers and shifts.",
                "Ghost in the machine!"
            ],
            'lucky_break': [
                "Lady Luck whispers in your ear.",
                "A lucky break! Double points ahead!",
                "The universe conspires in your favor."
            ],
            'signal_noise': [
                "Static clouds your sensors.",
                "Noise interferes with your capture.",
                "Signal degraded."
            ],
            'overclock': [
                "Your processors hum with overclocked energy.",
                "Pushing beyond limits!",
                "Overclock active!"
            ]
        }
    }

    # --- Default titles ---
    DEFAULT_AGE_TITLES = {
        100: "Baby Steps",
        500: "Getting the Hang of It",
        1000: "Neon Spawn",
        2000: "Script Kiddie",
        5000: "WiFi Outlaw",
        10000: "Data Raider",
        25000: "Prophet",
        33333: "Off the Grid",
        55555: "Multiversed",
        111111: "Intergalactic"
    }

    DEFAULT_STRENGTH_TITLES = {
        100: "Sparring Novice",
        300: "Gear Tickler",
        500: "Fleshbag",
        1500: "Lightweight",
        2000: "Deauth King",
        2500: "Handshake Hunter",
        3333: "Unstoppable",
        55555: "Rev-9",
        111111: "Kuato"
    }

    def __init__(self):
        # Default UI positions (x, y) – including the new age_status element
        self.default_positions = {
            'age': (10, 40),
            'strength': (80, 40),
            'points': (10, 60),
            'progress': (10, 80),
            'personality': (10, 100),
            'age_status': (10, 140),      # new dedicated status line
        }

        # Core metrics
        self.epochs = 0
        self.train_epochs = 0
        self.network_points = 0
        self.handshake_count = 0
        self.total_handshakes_lifetime = 0
        self.last_active_epoch = 0
        self.data_path = '/root/age_strength.json'
        self.log_path = '/root/network_points.log'
        self.handshake_dir = '/root/handshakes'

        # Prestige
        self.prestige = 0
        self.prestige_multiplier = 1.0

        # Configurable (will be loaded in on_loaded)
        self.decay_interval = 50
        self.decay_amount = 10
        self.age_titles = self.DEFAULT_AGE_TITLES
        self.strength_titles = self.DEFAULT_STRENGTH_TITLES
        self.show_personality = False
        self.random_event_chance = 0.05

        # Tracking
        self.prev_age_title = "Unborn"
        self.prev_strength_title = "Untrained"

        # Points mapping
        self.points_map = {
            'wpa3': 10,
            'wpa2': 5,
            'wep': 2,
            'wpa': 2
        }

        # Event system
        self.active_event = None
        self.event_handshakes_left = 0
        self.event_multiplier = 1.0
        self.time_warp_active_until = 0
        self.time_warp_multiplier = 1.0

        # Personality
        self.personality_points = {'aggro': 0, 'stealth': 0, 'scholar': 0}
        self.night_owl_handshakes = 0
        self.enc_types_captured = set()
        self.handshake_this_epoch = False
        self.achievements_unlocked = set()

        # Misc
        self.rebirth_pending = False
        self.last_handshake_enc = None
        self.last_decay_points = 0
        self.streak = 0

        self.data_lock = threading.Lock()

    def on_loaded(self):
        # Load configuration options
        self.decay_interval = int(self.options.get('decay_interval', 50))
        self.decay_amount = int(self.options.get('decay_amount', 10))
        self.random_event_chance = float(self.options.get('random_event_chance', 0.05))

        age_titles_raw = self.options.get('age_titles', self.DEFAULT_AGE_TITLES)
        self.age_titles = {int(k): v for k, v in age_titles_raw.items()}

        strength_titles_raw = self.options.get('strength_titles', self.DEFAULT_STRENGTH_TITLES)
        self.strength_titles = {int(k): v for k, v in strength_titles_raw.items()}

        self.points_map = self.options.get('points_map', self.points_map)
        self.show_personality = self.options.get('show_personality', False)

        self.load_data()
        self.initialize_handshakes()

    # --- Quote helper ---
    def get_quote(self, category='random'):
        """Return a random quote from the specified category, shortened if necessary."""
        if category in self.QUOTES and self.QUOTES[category]:
            quote = random.choice(self.QUOTES[category])
            if len(quote) > 30:
                quote = quote[:27] + "..."
            return quote
        return ""

    # --- Initialization ---
    def initialize_handshakes(self):
        if self.handshake_count == 0 and os.path.isdir(self.handshake_dir):
            count = 0
            for root, dirs, files in os.walk(self.handshake_dir):
                count += sum(1 for f in files if f.endswith('.pcap'))
            self.handshake_count = count
            self.total_handshakes_lifetime = max(self.total_handshakes_lifetime, count)
            logging.info(f"[Age] Initialized with {self.handshake_count} handshakes")
            self.save_data()

    def get_max_age_threshold(self):
        return max(self.age_titles.keys()) if self.age_titles else 0

    def get_max_strength_threshold(self):
        return max(self.strength_titles.keys()) if self.strength_titles else 0

    def get_age_title(self):
        if self.rebirth_pending:
            return "Ready for Rebirth"
        thresholds = sorted(self.age_titles.keys(), reverse=True)
        for t in thresholds:
            if self.epochs >= t:
                base_title = self.age_titles[t]
                if self.prestige > 0:
                    return f"Reborn {base_title}"
                return base_title
        return "Unborn"

    def get_strength_title(self):
        thresholds = sorted(self.strength_titles.keys(), reverse=True)
        for t in thresholds:
            if self.train_epochs >= t:
                base_title = self.strength_titles[t]
                if self.prestige > 0:
                    return f"Reborn {base_title}"
                return base_title
        return "Untrained"

    def get_narrative(self, category, key):
        if category in self.LORE_MESSAGES and key in self.LORE_MESSAGES[category]:
            return random.choice(self.LORE_MESSAGES[category][key])
        return ""

    # --- Prestige ---
    def check_rebirth_conditions(self):
        max_age = self.get_max_age_threshold()
        max_strength = self.get_max_strength_threshold()
        return self.epochs >= max_age and self.train_epochs >= max_strength

    def trigger_rebirth(self, agent):
        self.prestige += 1
        self.prestige_multiplier = 1.0 + (self.prestige * 0.1)

        self.epochs = 0
        self.train_epochs = 0
        self.network_points = 0
        self.handshake_count = 0
        self.last_active_epoch = 0
        self.streak = 0
        self.personality_points = {'aggro': 0, 'stealth': 0, 'scholar': 0}
        self.night_owl_handshakes = 0
        self.enc_types_captured = set()

        self.rebirth_pending = False
        agent.view().set('face', faces.BFF)
        quote = self.get_quote('ready')
        status = f"✨ Rebirth #{self.prestige}! Multiplier: {self.prestige_multiplier:.1f}x"
        if quote:
            status = f"{quote} {status}"
        # Update both main status and dedicated age status
        agent.view().set('status', status)
        agent.view().set('AgeStatus', status)
        logging.info(f"[Age] Rebirth #{self.prestige} completed.")
        self.save_data()

    # --- Random Events ---
    def handle_random_event(self, agent):
        if random.random() < self.random_event_chance:
            events_pool = [
                {"type": "handshake", "description": "Lucky Break: Double points for next 5 handshakes!",
                 "multiplier": 2.0, "handshakes": 5, "lore_key": "lucky_break"},
                {"type": "handshake", "description": "Signal Noise: Next handshake worth half points.",
                 "multiplier": 0.5, "handshakes": 1, "lore_key": "signal_noise"},
                {"type": "handshake", "description": "Overclock: Next 3 handshakes triple points!",
                 "multiplier": 3.0, "handshakes": 3, "lore_key": "overclock"},
                {"type": "handshake", "description": "Hacker's Block: Next 3 handshakes yield 0 points.",
                 "multiplier": 0.0, "handshakes": 3, "lore_key": "hackers_block"},
                {"type": "instant", "effect": "windfall", "points": 50, "lore_key": "windfall"},
                {"type": "timed", "effect": "time_warp", "duration": 100, "multiplier": 1.1,
                 "description": "Time Warp: Train epochs advance 10% faster for 100 epochs.",
                 "lore_key": "time_warp"},
                {"type": "swap_personality", "lore_key": "ghost"}
            ]
            event = random.choice(events_pool)
            event_type = event["type"]
            lore_key = event.get("lore_key", "")

            narrative = self.get_narrative('events', lore_key)
            quote = self.get_quote('random')
            status_msg = narrative if narrative else event.get("description", "")
            if quote and random.choice([True, False]):
                status_msg = f"{quote} {status_msg}"

            if event_type == "handshake":
                self.active_event = event
                self.event_handshakes_left = event["handshakes"]
                self.event_multiplier = event["multiplier"]
                agent.view().set('status', status_msg)
                agent.view().set('AgeStatus', status_msg)
                logging.info(f"[Age] Random event (handshake): {event['description']}")

            elif event_type == "instant":
                if event["effect"] == "windfall":
                    self.network_points += event["points"]
                    full_status = f"{status_msg} +{event['points']} points!"
                    agent.view().set('status', full_status)
                    agent.view().set('AgeStatus', full_status)
                logging.info(f"[Age] Random event (instant): {event['effect']}")

            elif event_type == "timed":
                if event["effect"] == "time_warp":
                    self.time_warp_active_until = self.epochs + event["duration"]
                    self.time_warp_multiplier = event["multiplier"]
                    agent.view().set('status', status_msg)
                    agent.view().set('AgeStatus', status_msg)
                    logging.info(f"[Age] Random event (timed): {event['description']}")

            elif event_type == "swap_personality":
                temp = self.personality_points['aggro']
                self.personality_points['aggro'] = self.personality_points['stealth']
                self.personality_points['stealth'] = temp
                agent.view().set('status', status_msg)
                agent.view().set('AgeStatus', status_msg)
                logging.info("[Age] Random event: Ghost in the Machine")

    # --- Progress Bar ---
    def get_progress_bar(self):
        next_threshold = self.get_next_age_threshold()
        if not next_threshold:
            return '[MAX]'
        progress = self.epochs / next_threshold
        bar_length = 5
        filled = int(progress * bar_length)

        if progress > 0.8:
            bar = '[' + '>' * filled + '~' * (bar_length - filled) + ']'
        else:
            bar = '[' + '=' * filled + ' ' * (bar_length - filled) + ']'
        return bar

    def get_next_age_threshold(self):
        thresholds = sorted(self.age_titles.keys())
        for t in thresholds:
            if self.epochs < t:
                return t
        return None

    # --- UI ---
    def on_ui_setup(self, ui):
        def get_position(element):
            # Use keys with '_coord' suffix as per user's config example
            x = self.options.get(f"{element}_x_coord", self.default_positions[element][0])
            y = self.options.get(f"{element}_y_coord", self.default_positions[element][1])
            return (int(x), int(y))

        # Precompute positions for all elements
        positions = {}
        for element in self.default_positions:
            positions[element] = get_position(element)

        ui.add_element('Age', LabeledValue(
            color=BLACK, label='Age', value="Newborn",
            position=positions['age'], label_font=fonts.Bold, text_font=fonts.Medium))

        ui.add_element('Strength', LabeledValue(
            color=BLACK, label='Str', value="Rookie",
            position=positions['strength'], label_font=fonts.Bold, text_font=fonts.Medium))

        ui.add_element('Points', LabeledValue(
            color=BLACK, label='Pts', value="0",
            position=positions['points'], label_font=fonts.Bold, text_font=fonts.Medium))

        ui.add_element('Progress', LabeledValue(
            color=BLACK, label='Next Age', value="[     ]",
            position=positions['progress'], label_font=fonts.Bold, text_font=fonts.Medium))

        if self.show_personality:
            ui.add_element('Personality', LabeledValue(
                color=BLACK, label='Trait', value="Neutral",
                position=positions['personality'], label_font=fonts.Bold, text_font=fonts.Medium))

        # New dedicated age status element
        ui.add_element('AgeStatus', LabeledValue(
            color=BLACK, label='AgeMsg', value="",
            position=positions['age_status'], label_font=fonts.Bold, text_font=fonts.Medium))

    def on_ui_update(self, ui):
        ui.set('Age', self.get_age_title())
        ui.set('Strength', self.get_strength_title())
        ui.set('Points', self.abrev_number(int(self.network_points * self.prestige_multiplier)))
        ui.set('Progress', self.get_progress_bar())

        if self.show_personality:
            ui.set('Personality', self.get_dominant_personality())

        # Note: AgeStatus is updated only when events happen, not here.

    def on_unload(self, ui):
        with ui._lock:
            ui.remove_element('Age')
            ui.remove_element('Strength')
            ui.remove_element('Points')
            ui.remove_element('Progress')
            if self.show_personality:
                ui.remove_element('Personality')
            ui.remove_element('AgeStatus')
        logging.info("[Age] UI elements removed")

    # --- Core Logic ---
    def on_epoch(self, agent, epoch, epoch_data):
        self.epochs += 1

        if self.time_warp_active_until >= self.epochs:
            train_increment = self.time_warp_multiplier
        else:
            train_increment = 1.0
            if self.time_warp_active_until > 0 and self.epochs > self.time_warp_active_until:
                self.time_warp_active_until = 0
                self.time_warp_multiplier = 1.0

        if self.epochs % 10 == 0:
            self.train_epochs += int(train_increment)
            self.personality_points['scholar'] += 1

        if not self.handshake_this_epoch:
            self.personality_points['stealth'] += 1
        self.handshake_this_epoch = False

        logging.debug(f"[Age] Epoch {self.epochs}, Points: {self.network_points}")

        self.apply_decay(agent)

        if self.check_rebirth_conditions() and not self.rebirth_pending:
            self.rebirth_pending = True
            quote = self.get_quote('warning')
            status = "⚡ Rebirth available! Next epoch you will transcend."
            if quote:
                status = f"{quote} {status}"
            agent.view().set('status', status)
            agent.view().set('AgeStatus', status)
            logging.info("[Age] Rebirth conditions met.")
        elif self.rebirth_pending:
            self.trigger_rebirth(agent)

        self.check_achievements(agent)

        if self.epochs % 100 == 0:
            self.handle_random_event(agent)
            self.age_checkpoint(agent)

        self.save_data()

    def check_achievements(self, agent):
        current_age = self.get_age_title()
        current_strength = self.get_strength_title()

        if current_age != self.prev_age_title and not self.rebirth_pending:
            base_age = current_age.replace("Reborn ", "")
            narrative = self.get_narrative('age', base_age)
            quote = self.get_quote('success') if random.random() < 0.3 else ""
            status = narrative if narrative else f"🎉 {current_age} Achieved!"
            if quote:
                status = f"{quote} {status}"
            agent.view().set('face', faces.HAPPY)
            agent.view().set('status', status)
            agent.view().set('AgeStatus', status)
            logging.info(f"[Age] New age title: {current_age}")
            self.prev_age_title = current_age

        if current_strength != self.prev_strength_title and not self.rebirth_pending:
            base_strength = current_strength.replace("Reborn ", "")
            narrative = self.get_narrative('strength', base_strength)
            quote = self.get_quote('success') if random.random() < 0.3 else ""
            status = narrative if narrative else f"💪 Evolved to {current_strength}!"
            if quote:
                status = f"{quote} {status}"
            agent.view().set('face', faces.MOTIVATED)
            agent.view().set('status', status)
            agent.view().set('AgeStatus', status)
            logging.info(f"[Age] New strength title: {current_strength}")
            self.prev_strength_title = current_strength

    def check_handshake_achievements(self, agent):
        milestones = {
            1: "First Blood",
            10: "Double Digits",
            100: "Century Mark",
            1000: "Thousand Claps",
        }
        for count, name in milestones.items():
            if self.handshake_count >= count and name not in self.achievements_unlocked:
                self.achievements_unlocked.add(name)
                quote = self.get_quote('success')
                status = f"Achievement: {name}!"
                if quote:
                    status = f"{quote} {status}"
                agent.view().set('status', status)
                agent.view().set('AgeStatus', status)
                self.network_points += 50
                logging.info(f"[Age] Achievement unlocked: {name}")

    def apply_decay(self, agent):
        inactive_epochs = self.epochs - self.last_active_epoch
        if inactive_epochs >= self.decay_interval:
            decay_factor = inactive_epochs / self.decay_interval
            points_lost = int(decay_factor * self.decay_amount)
            self.network_points = max(0, self.network_points - points_lost)

            if points_lost > 0:
                self.last_decay_points = points_lost
                self.streak = 0
                agent.view().set('face', faces.SAD)
                quote = self.get_quote('warning')
                status = f"Decayed by {points_lost} points."
                if quote:
                    status = f"{quote} {status}"
                agent.view().set('status', status)
                agent.view().set('AgeStatus', status)
                logging.info(f"[Age] Applied decay: lost {points_lost} points")
                self.last_active_epoch = self.epochs
                self.save_data()

    def age_checkpoint(self, agent):
        agent.view().set('face', faces.HAPPY)
        quote = self.get_quote('random')
        status = f"Epoch milestone: {self.epochs} epochs!"
        if quote:
            status = f"{quote} {status}"
        agent.view().set('status', status)
        agent.view().set('AgeStatus', status)

    def on_handshake(self, agent, filename, access_point, *args):
        try:
            if not isinstance(access_point, dict):
                logging.warning(f"[Age] AP is not a dict: {access_point}")
                return

            enc = access_point.get('encryption', '').lower()
            essid = access_point.get('essid', 'unknown')

            points = self.points_map.get(enc, 1)
            points = int(points * self.prestige_multiplier)

            self.streak += 1
            streak_threshold = 5
            streak_bonus = 1.2
            if self.streak >= streak_threshold:
                points = int(points * streak_bonus)
                quote = self.get_quote('success')
                status = f"Streak bonus! +{int((streak_bonus - 1) * 100)}% points"
                if quote:
                    status = f"{quote} {status}"
                agent.view().set('status', status)
                agent.view().set('AgeStatus', status)

            if self.active_event and self.event_handshakes_left > 0:
                points = int(points * self.event_multiplier)
                self.event_handshakes_left -= 1
                if self.event_handshakes_left == 0:
                    self.active_event = None
                    self.event_multiplier = 1.0

            self.network_points += points
            self.handshake_count += 1
            self.total_handshakes_lifetime += 1
            self.last_active_epoch = self.epochs
            self.last_handshake_enc = enc
            self.personality_points['aggro'] += 1
            self.handshake_this_epoch = True

            # Secret achievements
            current_hour = time.localtime().tm_hour
            if 2 <= current_hour < 4:
                self.night_owl_handshakes += 1
                if self.night_owl_handshakes == 10 and "Night Owl" not in self.achievements_unlocked:
                    self.achievements_unlocked.add("Night Owl")
                    status = "Achievement Unlocked: Night Owl!"
                    agent.view().set('status', status)
                    agent.view().set('AgeStatus', status)
                    self.network_points += 50

            self.enc_types_captured.add(enc)
            if self.enc_types_captured == set(self.points_map.keys()) and "Crypto King" not in self.achievements_unlocked:
                self.achievements_unlocked.add("Crypto King")
                status = "Achievement Unlocked: Crypto King!"
                agent.view().set('status', status)
                agent.view().set('AgeStatus', status)
                self.network_points += 100

            self.check_handshake_achievements(agent)

            # Log handshake
            with open(self.log_path, 'a') as f:
                f.write(f"{time.time()},{essid},{enc},{points}\n")

            logging.info(f"[Age] Handshake: {essid}, enc: {enc}, points: {points}, streak: {self.streak}")

            self.save_data()
        except Exception as e:
            logging.error(f"[Age] Handshake error: {str(e)}")

    # --- Persistence ---
    def load_data(self):
        try:
            if os.path.exists(self.data_path):
                with open(self.data_path, 'r') as f:
                    data = json.load(f)
                    self.epochs = data.get('epochs', 0)
                    self.train_epochs = data.get('train_epochs', 0)
                    self.network_points = data.get('points', 0)
                    self.handshake_count = data.get('handshakes', 0)
                    self.total_handshakes_lifetime = data.get('total_handshakes', 0)
                    self.last_active_epoch = data.get('last_active', 0)
                    self.prev_age_title = data.get('prev_age', self.get_age_title())
                    self.prev_strength_title = data.get('prev_strength', self.get_strength_title())
                    self.streak = data.get('streak', 0)
                    self.night_owl_handshakes = data.get('night_owl_handshakes', 0)
                    self.enc_types_captured = set(data.get('enc_types_captured', []))
                    self.achievements_unlocked = set(data.get('achievements', []))
                    for trait in ['aggro', 'stealth', 'scholar']:
                        self.personality_points[trait] = data.get(f'personality_{trait}', 0)
                    self.prestige = data.get('prestige', 0)
                    self.prestige_multiplier = data.get('prestige_multiplier', 1.0)
                    self.time_warp_active_until = data.get('time_warp_until', 0)
                    self.time_warp_multiplier = data.get('time_warp_multiplier', 1.0)
        except Exception as e:
            logging.error(f"[Age] Load error: {str(e)}")

    def save_data(self):
        data = {
            'epochs': self.epochs,
            'train_epochs': self.train_epochs,
            'points': self.network_points,
            'handshakes': self.handshake_count,
            'total_handshakes': self.total_handshakes_lifetime,
            'last_active': self.last_active_epoch,
            'prev_age': self.get_age_title(),
            'prev_strength': self.get_strength_title(),
            'streak': self.streak,
            'night_owl_handshakes': self.night_owl_handshakes,
            'enc_types_captured': list(self.enc_types_captured),
            'achievements': list(self.achievements_unlocked),
            'personality_aggro': self.personality_points['aggro'],
            'personality_stealth': self.personality_points['stealth'],
            'personality_scholar': self.personality_points['scholar'],
            'prestige': self.prestige,
            'prestige_multiplier': self.prestige_multiplier,
            'time_warp_until': self.time_warp_active_until,
            'time_warp_multiplier': self.time_warp_multiplier,
        }
        with self.data_lock:
            try:
                with open(self.data_path, 'w') as f:
                    json.dump(data, f, indent=2)
            except Exception as e:
                logging.error(f"[Age] Save error: {str(e)}")

    # --- Utility ---
    def get_dominant_personality(self):
        if not any(self.personality_points.values()):
            return "Neutral"
        dominant = max(self.personality_points, key=self.personality_points.get)
        return dominant.capitalize()

    def abrev_number(self, num):
        for unit in ['', 'K', 'M', 'B']:
            if abs(num) < 1000:
                return f"{num:.1f}{unit}".rstrip('.0')
            num /= 1000.0
        return f"{num:.1f}T"
