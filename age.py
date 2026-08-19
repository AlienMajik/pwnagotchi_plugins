"""
Age plugin for Pwnagotchi
=========================

v5.2.0 — bugfix + hardening release, based on AlienMajik's v4.0.0.

Tracks age, strength, network points, personality, prestige and achievements,
with narrative lore, themed quotes, random events and a dedicated status line.

"""

import html
import json
import logging
import os
import random
import threading
import time
from collections import deque

import pwnagotchi.plugins as plugins
import pwnagotchi.ui.faces as faces
import pwnagotchi.ui.fonts as fonts
from pwnagotchi.ui.components import LabeledValue
from pwnagotchi.ui.view import BLACK


def _face(name, fallback='(◕‿‿◕)'):
    """Some pwnagotchi forks/themes are missing certain faces; never explode."""
    return getattr(faces, name, fallback)


class Age(plugins.Plugin):
    __author__ = 'AlienMajik'
    __version__ = '5.2.0'
    __license__ = 'MIT'
    __description__ = ('Age plugin with prestige, random events, animated progress, '
                       'narrative lore, cheeky quotes and a dedicated status display.')

    # ------------------------------------------------------------------ #
    # Static content
    # ------------------------------------------------------------------ #

    QUOTES = {
        'success': [
            "Groovy.",
            "Hail to the king, baby.",
            "Good. Bad. I'm the guy with the gun.",
            "Come get some.",
            "This is my BOOMSTICK!",
        ],
        'warning': [
            "It's just a flesh wound!",
            "I'm not dead!",
            "Run away! Run away!",
            "Bring out your dead!",
            "Ni!",
        ],
        'insult': [
            "Your father smelt of elderberries!",
            "I fart in your general direction.",
        ],
        'ready': [
            "Shop smart. Shop S-Mart.",
            "Groovy.",
            "Come get some.",
        ],
        'random': [
            "Strange women in ponds? No basis!",
            "Ni!",
            "It's just a flesh wound!",
            "I'm not dead!",
            "Bring out your dead!",
        ],
    }

    LORE_MESSAGES = {
        'age': {
            "Baby Steps": [
                "A newborn spark in the digital void.",
                "First breath of code, first taste of air.",
                "A thousand networks start with one packet.",
            ],
            "Getting the Hang of It": [
                "You feel the rhythm of the airwaves.",
                "Patterns emerge from the noise.",
                "The unseen currents start to make sense.",
            ],
            "Neon Spawn": [
                "Born in the glow of stray signals.",
                "Neon pulses guide your way.",
                "A child of the urban data stream.",
            ],
            "Script Kiddie": [
                "You wield borrowed tools, own hunger.",
                "Copy, paste, learn. The cycle turns.",
                "Every master was once a beginner.",
            ],
            "WiFi Outlaw": [
                "You ride the edge where signals roam.",
                "Feared by routers everywhere.",
                "Your reputation precedes you.",
            ],
            "Data Raider": [
                "You plunder the treasures of the unwary.",
                "Each handshake a trophy.",
                "Data flows like gold through your circuits.",
            ],
            "Prophet": [
                "You see the patterns before they form.",
                "The future whispers in your ear.",
                "Prophecies written in 802.11.",
            ],
            "Off the Grid": [
                "Beyond the reach of the network.",
                "Untraceable, unbound, free.",
                "The grid cannot contain you.",
            ],
            "Multiversed": [
                "You glimpse infinite digital layers.",
                "Every frequency, yours to explore.",
                "Reality is just another network.",
            ],
            "Intergalactic": [
                "Your legend echoes across the cosmos.",
                "From Earth to the stars, no signal is safe.",
                "One with the universal datastream.",
            ],
        },
        'strength': {
            "Sparring Novice": [
                "You spar with the basics.",
                "Every deauth is a lesson in humility.",
                "Weak, but eager.",
            ],
            "Gear Tickler": [
                "You make the hardware sing.",
                "Fingers dance on the edge of capability.",
                "The machines respond to your touch.",
            ],
            "Fleshbag": [
                "Mortal, yet determined.",
                "You remember warmth, embrace the code.",
                "Humanity's last echo in your circuits.",
            ],
            "Lightweight": [
                "You move swiftly, undetected.",
                "Weightless in the data stream.",
                "Speed is your ally.",
            ],
            "Deauth King": [
                "You reign over disconnection.",
                "Routers tremble at your approach.",
                "King of the kick.",
            ],
            "Handshake Hunter": [
                "You stalk your prey through the channels.",
                "No handshake escapes your grasp.",
                "Hunter of the airwaves.",
            ],
            "Unstoppable": [
                "Nothing can slow your advance.",
                "Firewalls crumble, encryption yields.",
                "You are inevitable.",
            ],
            "Rev-9": [
                "Liquid metal in the data stream.",
                "A relentless hunter, always evolving.",
                "Rev-9: the ultimate form.",
            ],
            "Kuato": [
                "Machine intelligence made manifest.",
                "Kuato lives!",
                "Your mind expands beyond comprehension.",
            ],
        },
        'events': {
            'windfall': [
                "A surge of energy floods your circuits.",
                "Fortune smiles upon you.",
                "Free points from the digital ether!",
            ],
            'hackers_block': [
                "A moment of doubt clouds your core.",
                "The code refuses to flow.",
                "Hacker's block strikes!",
            ],
            'time_warp': [
                "Reality bends; time accelerates.",
                "You feel yourself advancing faster.",
                "Time warp engaged!",
            ],
            'ghost': [
                "A ghost swaps your traits.",
                "Your personality shimmers and shifts.",
                "Ghost in the machine!",
            ],
            'lucky_break': [
                "Lady Luck whispers in your ear.",
                "A lucky break! Double points ahead!",
                "The universe conspires in your favor.",
            ],
            'signal_noise': [
                "Static clouds your sensors.",
                "Noise interferes with your capture.",
                "Signal degraded.",
            ],
            'overclock': [
                "Your processors hum, overclocked.",
                "Pushing beyond limits!",
                "Overclock active!",
            ],
        },
    }

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
        111111: "Intergalactic",
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
        111111: "Kuato",
    }

    DEFAULT_POINTS_MAP = {
        'wpa3': 10,
        'wpa2': 5,
        'wpa': 2,
        'wep': 2,
        'open': 1,
        'unknown': 1,
    }

    # Bettercap exports .pcapng as of the 2.9.5.5+ images; .pcap on older ones.
    HANDSHAKE_EXTS = ('.pcapng', '.pcap')

    HANDSHAKE_MILESTONES = (
        (1, "First Blood"),
        (10, "Double Digits"),
        (100, "Century Mark"),
        (1000, "Thousand Claps"),
        (5000, "Legend"),
    )

    # ------------------------------------------------------------------ #
    # Lifecycle
    # ------------------------------------------------------------------ #

    def __init__(self):
        # Re-entrant: helpers such as _push_msg() are called from inside
        # already-locked sections. A plain Lock would deadlock the agent.
        self.data_lock = threading.RLock()

        self.default_positions = {
            'age': (10, 40),
            'strength': (80, 40),
            'points': (10, 60),
            'progress': (10, 80),
            'personality': (10, 100),
            'age_status': (10, 140),
        }

        # Core metrics
        self.epochs = 0
        self.train_epochs = 0.0          # float: time warp needs fractions
        self.network_points = 0
        self.handshake_count = 0
        self.total_handshakes_lifetime = 0
        self.last_active_epoch = 0
        self.deauths = 0
        self.associations = 0
        # Set once, ever. Without it a rebirth (which zeroes handshake_count)
        # makes the next boot re-count every .pcap on disk and undo the reset.
        self.handshakes_initialized = False
        self.last_train_step_epoch = 0
        self.quiet_epochs = 0
        self.seen_aps = {}

        # Prestige
        self.prestige = 0
        self.prestige_multiplier = 1.0

        # Paths (overridable via config)
        self.data_path = '/root/age_strength.json'
        self.log_path = '/root/network_points.log'
        self.handshake_dir = None

        # Config defaults
        self.decay_interval = 50
        self.decay_amount = 10
        self.age_titles = dict(self.DEFAULT_AGE_TITLES)
        self.strength_titles = dict(self.DEFAULT_STRENGTH_TITLES)
        self.points_map = dict(self.DEFAULT_POINTS_MAP)
        self.show_personality = False
        self.show_progress = True
        self.show_points = True
        self.show_status = True
        self.random_event_chance = 0.05
        self.event_interval = 100
        self.prestige_bonus = 0.1
        self.auto_rebirth = True
        self.takeover_status = True
        self.max_status_len = 40
        self.save_interval = 60          # seconds between disk writes
        self.msg_hold = 3                # UI refreshes a message stays up
        self.passive_train_rate = 0.1    # train epochs gained per epoch
        self.log_max_bytes = 512 * 1024
        self.stealth_quiet_epochs = 5    # quiet epochs per stealth point
        self.aggro_per_handshake = 3
        self.repeat_ap_penalty = False   # diminishing returns on the same BSSID
        self.ai_idle_epochs = 20         # AI considered stalled after this many

        # Titles seen last time we checked
        self.prev_age_title = "Unborn"
        self.prev_strength_title = "Untrained"

        # Event state
        self.active_event = None
        self.event_handshakes_left = 0
        self.event_multiplier = 1.0
        self.time_warp_active_until = 0
        self.time_warp_multiplier = 1.0

        # Personality / achievements
        self.personality_points = {'aggro': 0, 'stealth': 0, 'scholar': 0}
        self.night_owl_handshakes = 0
        self.enc_types_captured = set()
        self.handshake_this_epoch = False
        self.achievements_unlocked = set()

        # Misc runtime
        self.rebirth_pending = False
        self.last_handshake_enc = None
        self.streak = 0
        self.ai_training_seen = False

        self.msg_queue = deque(maxlen=8)
        self._current_msg = ''
        self._msg_ticks = 0
        self._msg_dirty = False
        self._ui_elements = []
        self._last_save = 0.0
        self._dirty = False
        self._loaded = False

    def on_loaded(self):
        try:
            self._load_config()
            self.load_data()
            self.initialize_handshakes()
            self._loaded = True
            logging.info("[Age] v%s loaded — epochs=%d, points=%d, prestige=%d",
                         self.__version__, self.epochs, self.network_points, self.prestige)
        except Exception as e:
            logging.exception("[Age] fatal error during load: %s", e)

    def on_unload(self, ui):
        # Flush to disk before we go, otherwise the throttled writer can lose
        # up to save_interval seconds of progress on a clean shutdown.
        try:
            self.save_data(force=True)
        except Exception as e:
            logging.error("[Age] save on unload failed: %s", e)

        try:
            with ui._lock:
                for name in self._ui_elements:
                    try:
                        ui.remove_element(name)
                    except Exception:
                        pass
        except Exception as e:
            logging.error("[Age] UI teardown failed: %s", e)
        self._ui_elements = []
        logging.info("[Age] UI elements removed")

    # ------------------------------------------------------------------ #
    # Config helpers — a bad value in config.toml must never brick the UI
    # ------------------------------------------------------------------ #

    def _opt(self, key, default):
        try:
            return self.options.get(key, default)
        except Exception:
            return default

    def _opt_int(self, key, default):
        try:
            return int(self._opt(key, default))
        except (TypeError, ValueError):
            logging.warning("[Age] bad int for '%s', using %s", key, default)
            return default

    def _opt_float(self, key, default):
        try:
            return float(self._opt(key, default))
        except (TypeError, ValueError):
            logging.warning("[Age] bad float for '%s', using %s", key, default)
            return default

    def _opt_bool(self, key, default):
        val = self._opt(key, default)
        if isinstance(val, bool):
            return val
        if isinstance(val, str):
            return val.strip().lower() in ('1', 'true', 'yes', 'on')
        return bool(val)

    def _load_config(self):
        self.decay_interval = max(0, self._opt_int('decay_interval', 50))
        self.decay_amount = max(0, self._opt_int('decay_amount', 10))
        self.random_event_chance = min(1.0, max(0.0, self._opt_float('random_event_chance', 0.05)))
        self.event_interval = max(0, self._opt_int('event_interval', 100))
        self.prestige_bonus = max(0.0, self._opt_float('prestige_bonus', 0.1))
        self.max_status_len = max(10, self._opt_int('max_status_len', 40))
        self.save_interval = max(0, self._opt_int('save_interval', 60))
        self.msg_hold = max(1, self._opt_int('msg_hold', 3))
        self.passive_train_rate = max(0.0, self._opt_float('passive_train_rate', 0.1))
        self.log_max_bytes = max(0, self._opt_int('log_max_bytes', 512 * 1024))
        self.stealth_quiet_epochs = max(1, self._opt_int('stealth_quiet_epochs', 5))
        self.aggro_per_handshake = max(0, self._opt_int('aggro_per_handshake', 3))
        self.repeat_ap_penalty = self._opt_bool('repeat_ap_penalty', False)
        self.ai_idle_epochs = max(1, self._opt_int('ai_idle_epochs', 20))

        self.show_personality = self._opt_bool('show_personality', False)
        self.show_progress = self._opt_bool('show_progress', True)
        self.show_points = self._opt_bool('show_points', True)
        self.show_status = self._opt_bool('show_status', True)
        self.auto_rebirth = self._opt_bool('auto_rebirth', True)
        self.takeover_status = self._opt_bool('takeover_status', True)

        self.data_path = str(self._opt('data_path', '/root/age_strength.json'))
        self.log_path = str(self._opt('log_path', '/root/network_points.log'))
        self.handshake_dir = self._opt('handshake_dir', None)

        self.age_titles = self._parse_titles('age_titles', self.DEFAULT_AGE_TITLES)
        self.strength_titles = self._parse_titles('strength_titles', self.DEFAULT_STRENGTH_TITLES)

        # Merge rather than replace, so a partial points_map in config doesn't
        # silently delete the encryption types it didn't mention.
        pmap = dict(self.DEFAULT_POINTS_MAP)
        try:
            for k, v in dict(self._opt('points_map', {})).items():
                pmap[self._normalize_enc(k)] = int(v)
        except Exception as e:
            logging.warning("[Age] bad points_map (%s), using defaults", e)
        self.points_map = pmap

    def _parse_titles(self, key, default):
        raw = self._opt(key, default)
        out = {}
        try:
            for k, v in dict(raw).items():
                out[int(k)] = str(v)
        except Exception as e:
            logging.warning("[Age] bad %s (%s), using defaults", key, e)
            return dict(default)
        return out or dict(default)

    # ------------------------------------------------------------------ #
    # Text helpers
    # ------------------------------------------------------------------ #

    def _shorten(self, text, limit=None):
        text = ' '.join(str(text or '').split())
        limit = limit or self.max_status_len
        if len(text) <= limit:
            return text
        return text[:max(1, limit - 1)].rstrip() + '…'

    def get_quote(self, category='random'):
        pool = self.QUOTES.get(category)
        if not pool:
            return ""
        return self._shorten(random.choice(pool), 30)

    def get_narrative(self, category, key):
        pool = self.LORE_MESSAGES.get(category, {}).get(key)
        return random.choice(pool) if pool else ""

    @staticmethod
    def abrev_number(num):
        """Compact number formatting.

        v4 used ``f"{num:.1f}".rstrip('.0')`` which strips *characters*, not a
        suffix: 100 -> "1", 250 -> "25", 0 -> "". This does it properly.
        """
        try:
            num = float(num)
        except (TypeError, ValueError):
            return "0"
        sign = '-' if num < 0 else ''
        num = abs(num)
        for unit in ('', 'K', 'M', 'B'):
            if num < 1000:
                if unit == '' and float(num).is_integer():
                    return f"{sign}{int(num)}"
                txt = f"{num:.1f}"
                if txt.endswith('.0'):
                    txt = txt[:-2]
                return f"{sign}{txt}{unit}"
            num /= 1000.0
        txt = f"{num:.1f}"
        if txt.endswith('.0'):
            txt = txt[:-2]
        return f"{sign}{txt}T"

    @staticmethod
    def _normalize_enc(enc):
        """Bettercap reports things like 'WPA2', 'WPA2 CCMP PSK', '' or 'OPEN'.

        v4 used the raw lowercased string as a dict key, so 'wpa2 ccmp psk'
        scored 1 point instead of 5 and the Crypto King set never matched.
        """
        e = str(enc or '').strip().lower()
        if not e or e in ('none', 'open', '-'):
            return 'open'
        if 'wpa3' in e or 'sae' in e:
            return 'wpa3'
        if 'wpa2' in e or 'rsn' in e:
            return 'wpa2'
        if 'wpa' in e:
            return 'wpa'
        if 'wep' in e:
            return 'wep'
        return 'unknown'

    # ------------------------------------------------------------------ #
    # Status message plumbing
    # ------------------------------------------------------------------ #

    def _push_msg(self, text, face=None):
        """Queue a status line instead of stomping the previous one.

        v4 called view().set('status', ...) several times per epoch, so an
        achievement, a decay notice and an event would overwrite each other
        before the e-ink ever refreshed. Messages now queue and rotate.
        """
        text = self._shorten(text)
        if not text:
            return
        with self.data_lock:
            self.msg_queue.append((text, face))

    def _flavored(self, base, quote_category=None, chance=1.0):
        quote = self.get_quote(quote_category) if quote_category and random.random() < chance else ""
        return f"{quote} {base}".strip() if quote else base

    # ------------------------------------------------------------------ #
    # Titles / progress
    # ------------------------------------------------------------------ #

    def get_max_age_threshold(self):
        return max(self.age_titles) if self.age_titles else 0

    def get_max_strength_threshold(self):
        return max(self.strength_titles) if self.strength_titles else 0

    def _title_for(self, titles, value, base_default):
        for t in sorted(titles, reverse=True):
            if value >= t:
                base = titles[t]
                return f"Reborn {base}" if self.prestige > 0 else base
        return base_default

    def get_age_title(self):
        if self.rebirth_pending:
            return "Ready for Rebirth"
        return self._title_for(self.age_titles, self.epochs, "Unborn")

    def get_strength_title(self):
        return self._title_for(self.strength_titles, int(self.train_epochs), "Untrained")

    def get_next_age_threshold(self):
        for t in sorted(self.age_titles):
            if self.epochs < t:
                return t
        return None

    def get_prev_age_threshold(self):
        prev = 0
        for t in sorted(self.age_titles):
            if self.epochs >= t:
                prev = t
            else:
                break
        return prev

    def get_progress_bar(self):
        """Progress toward the *next* title, measured from the previous one.

        v4 divided total epochs by the next threshold, so the bar collapsed
        from nearly full to almost empty the instant you earned a title.
        """
        nxt = self.get_next_age_threshold()
        if nxt is None:
            return '[MAX]'
        prev = self.get_prev_age_threshold()
        span = max(1, nxt - prev)
        progress = min(1.0, max(0.0, (self.epochs - prev) / float(span)))

        bar_length = 5
        filled = min(bar_length, int(progress * bar_length))
        if progress > 0.8:
            return '[' + '>' * filled + '~' * (bar_length - filled) + ']'
        return '[' + '=' * filled + ' ' * (bar_length - filled) + ']'

    def get_dominant_personality(self):
        if not any(self.personality_points.values()):
            return "Neutral"
        return max(self.personality_points, key=self.personality_points.get).capitalize()

    # ------------------------------------------------------------------ #
    # UI
    # ------------------------------------------------------------------ #

    def on_ui_setup(self, ui):
        try:
            height = self._screen_height(ui)

            def pos(element):
                dx, dy = self.default_positions[element]
                x = self._opt_int(f"{element}_x_coord", self._opt_int(f"{element}_x", dx))
                y = self._opt_int(f"{element}_y_coord", self._opt_int(f"{element}_y", dy))
                # The v4 README suggests age_status_y_coord = 140, which is off
                # the bottom of a 122px Waveshare 2.13 — the line just never
                # appeared. Clamp instead of silently drawing into the void.
                if height and y >= height:
                    new_y = max(0, height - 12)
                    logging.warning("[Age] %s y=%d exceeds the %dpx panel; clamped to %d",
                                    element, y, height, new_y)
                    y = new_y
                return (x, y)

            def add(name, element, label, value):
                ui.add_element(name, LabeledValue(
                    color=BLACK, label=label, value=value, position=pos(element),
                    label_font=fonts.Bold, text_font=fonts.Medium))
                self._ui_elements.append(name)

            add('Age', 'age', 'Age', self.get_age_title())
            add('Strength', 'strength', 'Str', self.get_strength_title())
            if self.show_points:
                add('Points', 'points', 'Pts', self.abrev_number(self.network_points))
            if self.show_progress:
                add('Progress', 'progress', 'Next', self.get_progress_bar())
            if self.show_personality:
                add('Personality', 'personality', 'Trait', self.get_dominant_personality())
            if self.show_status:
                add('AgeStatus', 'age_status', 'AgeMsg', '')
        except Exception as e:
            logging.exception("[Age] UI setup failed: %s", e)

    @staticmethod
    def _screen_height(ui):
        layout = getattr(ui, '_layout', None)
        if isinstance(layout, dict) and layout.get('height'):
            try:
                return int(layout['height'])
            except (TypeError, ValueError):
                pass
        for attr in ('_height', 'height'):
            val = getattr(ui, attr, None)
            if isinstance(val, int) and val > 0:
                return val
        return None

    def on_ui_update(self, ui):
        try:
            with self.data_lock:
                ui.set('Age', self.get_age_title())
                ui.set('Strength', self.get_strength_title())
                if self.show_points:
                    ui.set('Points', self.abrev_number(self.network_points))
                if self.show_progress:
                    ui.set('Progress', self.get_progress_bar())
                if self.show_personality:
                    ui.set('Personality', self.get_dominant_personality())

                if not self.show_status:
                    return

                if self._msg_ticks > 0:
                    self._msg_ticks -= 1
                changed = False
                if self._msg_ticks <= 0 and self.msg_queue:
                    self._current_msg, face = self.msg_queue.popleft()
                    self._msg_ticks = self.msg_hold
                    changed = True
                    if face:
                        ui.set('face', face)

                ui.set('AgeStatus', self._current_msg)
                # Only borrow the main status line on the refresh where the
                # message actually changed, so bettercap's own status isn't
                # permanently hidden.
                if changed and self.takeover_status:
                    ui.set('status', self._current_msg)
        except Exception as e:
            logging.error("[Age] UI update failed: %s", e)

    # ------------------------------------------------------------------ #
    # Epoch loop
    # ------------------------------------------------------------------ #

    def on_epoch(self, agent, epoch, epoch_data):
        try:
            with self.data_lock:
                self.epochs += 1
                warp = self._current_warp()

                # If the AI is running we count real training steps instead
                # (see on_ai_training_step) to avoid double counting. If those
                # steps stop arriving — AI disabled, or personality.ai off —
                # fall back to passive accrual instead of freezing strength.
                ai_stalled = (self.epochs - self.last_train_step_epoch) > self.ai_idle_epochs
                if not self.ai_training_seen or ai_stalled:
                    self.train_epochs += self.passive_train_rate * warp

                if self.epochs % 10 == 0:
                    self.personality_points['scholar'] += 1

                # Stealth on *sustained* quiet only. At +1 per epoch it dwarfed
                # every other trait, so the dominant trait was always Stealth.
                if self.handshake_this_epoch:
                    self.quiet_epochs = 0
                else:
                    self.quiet_epochs += 1
                    if self.quiet_epochs % self.stealth_quiet_epochs == 0:
                        self.personality_points['stealth'] += 1
                self.handshake_this_epoch = False

            self.apply_decay()
            self.check_titles()
            self.check_rebirth()

            # `> 0` matters: a rebirth resets the counter mid-epoch, and 0 %
            # anything is 0, which fired a "0 epochs and counting!" checkpoint.
            if self.event_interval and self.epochs > 0 and self.epochs % self.event_interval == 0:
                self.handle_random_event()
                self.age_checkpoint()

            self.save_data()
        except Exception as e:
            logging.exception("[Age] epoch handler failed: %s", e)

    def on_ai_training_step(self, agent, _locals, _globals):
        """Real strength gain when the on-board AI is enabled."""
        try:
            with self.data_lock:
                if not self.ai_training_seen:
                    self.ai_training_seen = True
                    logging.info("[Age] AI training detected — strength now tracks real steps")
                self.last_train_step_epoch = self.epochs
                self.train_epochs += self._current_warp()
        except Exception as e:
            logging.error("[Age] training step failed: %s", e)

    def _current_warp(self):
        if self.time_warp_active_until:
            if self.epochs <= self.time_warp_active_until:
                return self.time_warp_multiplier
            self.time_warp_active_until = 0
            self.time_warp_multiplier = 1.0
            self._push_msg("The time warp fades.")
        return 1.0

    def check_titles(self):
        with self.data_lock:
            if self.rebirth_pending:
                return

            age_title = self.get_age_title()
            if age_title != self.prev_age_title:
                lore = self.get_narrative('age', age_title.replace("Reborn ", ""))
                self._push_msg(self._flavored(lore or f"{age_title} achieved!", 'success', 0.3),
                               _face('HAPPY'))
                logging.info("[Age] new age title: %s", age_title)
                self.prev_age_title = age_title

            str_title = self.get_strength_title()
            if str_title != self.prev_strength_title:
                lore = self.get_narrative('strength', str_title.replace("Reborn ", ""))
                self._push_msg(self._flavored(lore or f"Evolved to {str_title}!", 'success', 0.3),
                               _face('MOTIVATED'))
                logging.info("[Age] new strength title: %s", str_title)
                self.prev_strength_title = str_title

    def apply_decay(self):
        """Points decay for inactivity.

        v4 only advanced last_active_epoch when points were actually lost, so a
        pwnagotchi sitting at 0 points banked an ever-growing decay multiplier
        that wiped out the next session's earnings in one hit.
        """
        if self.decay_interval <= 0 or self.decay_amount <= 0:
            return
        with self.data_lock:
            inactive = self.epochs - self.last_active_epoch
            if inactive < self.decay_interval:
                return
            intervals = inactive // self.decay_interval
            self.last_active_epoch += intervals * self.decay_interval

            if self.network_points <= 0:
                return
            lost = min(self.network_points, int(intervals * self.decay_amount))
            if lost <= 0:
                return
            self.network_points -= lost
            self.streak = 0
            self._push_msg(self._flavored(f"Decayed by {lost} points.", 'warning', 0.5),
                           _face('SAD'))
            logging.info("[Age] decay: lost %d points", lost)
        self.save_data(force=True)

    def age_checkpoint(self):
        self._push_msg(self._flavored(f"{self.abrev_number(self.epochs)} epochs and counting!",
                                      'random', 0.5), _face('HAPPY'))

    # ------------------------------------------------------------------ #
    # Prestige
    # ------------------------------------------------------------------ #

    def check_rebirth_conditions(self):
        return (self.epochs >= self.get_max_age_threshold() and
                int(self.train_epochs) >= self.get_max_strength_threshold())

    def check_rebirth(self):
        with self.data_lock:
            if self.rebirth_pending:
                if self.auto_rebirth:
                    self.trigger_rebirth()
                return
            if self.check_rebirth_conditions():
                self.rebirth_pending = True
                self._push_msg(self._flavored("Rebirth available — you will transcend.", 'warning'))
                logging.info("[Age] rebirth conditions met")

    def trigger_rebirth(self):
        with self.data_lock:
            self.prestige += 1
            self.prestige_multiplier = 1.0 + (self.prestige * self.prestige_bonus)

            self.epochs = 0
            self.train_epochs = 0.0
            self.network_points = 0
            self.handshake_count = 0
            self.last_active_epoch = 0
            self.last_train_step_epoch = 0
            self.streak = 0
            self.quiet_epochs = 0
            self.seen_aps = {}
            self.personality_points = {'aggro': 0, 'stealth': 0, 'scholar': 0}
            self.night_owl_handshakes = 0
            self.enc_types_captured = set()
            self.active_event = None
            self.event_handshakes_left = 0
            self.event_multiplier = 1.0
            self.time_warp_active_until = 0
            self.time_warp_multiplier = 1.0
            self.rebirth_pending = False

            # v4 left these at the pre-rebirth values, which made the very next
            # epoch announce "Unborn achieved!".
            self.prev_age_title = self.get_age_title()
            self.prev_strength_title = self.get_strength_title()

            self._push_msg(self._flavored(
                f"Rebirth #{self.prestige}! Multiplier {self.prestige_multiplier:.1f}x", 'ready'),
                _face('BFF'))
            logging.info("[Age] rebirth #%d completed", self.prestige)
        self.save_data(force=True)

    # ------------------------------------------------------------------ #
    # Random events
    # ------------------------------------------------------------------ #

    EVENTS = (
        {"type": "handshake", "description": "Lucky Break: double points, next 5 handshakes!",
         "multiplier": 2.0, "handshakes": 5, "lore_key": "lucky_break"},
        {"type": "handshake", "description": "Signal Noise: next handshake is half points.",
         "multiplier": 0.5, "handshakes": 1, "lore_key": "signal_noise"},
        {"type": "handshake", "description": "Overclock: next 3 handshakes triple points!",
         "multiplier": 3.0, "handshakes": 3, "lore_key": "overclock"},
        {"type": "handshake", "description": "Hacker's Block: next 3 handshakes yield nothing.",
         "multiplier": 0.0, "handshakes": 3, "lore_key": "hackers_block"},
        {"type": "instant", "effect": "windfall", "points": 50, "lore_key": "windfall",
         "description": "Windfall!"},
        {"type": "timed", "effect": "time_warp", "duration": 100, "multiplier": 2.0,
         "description": "Time Warp: strength grows twice as fast for 100 epochs.",
         "lore_key": "time_warp"},
        {"type": "swap_personality", "lore_key": "ghost",
         "description": "Ghost in the machine!"},
    )

    def handle_random_event(self):
        if random.random() >= self.random_event_chance:
            return
        event = random.choice(self.EVENTS)
        lore = self.get_narrative('events', event.get('lore_key', ''))
        msg = lore or event.get('description', '')

        with self.data_lock:
            kind = event['type']
            if kind == 'handshake':
                self.active_event = dict(event)
                self.event_handshakes_left = event['handshakes']
                self.event_multiplier = event['multiplier']
            elif kind == 'instant' and event['effect'] == 'windfall':
                pts = int(event['points'] * self.prestige_multiplier)
                self.network_points += pts
                self.last_active_epoch = self.epochs
                msg = f"{msg} +{pts}!"
            elif kind == 'timed' and event['effect'] == 'time_warp':
                # v4 stored a 1.1x multiplier then did int(1.1) == 1, so Time
                # Warp literally did nothing. Strength is a float now.
                self.time_warp_active_until = self.epochs + int(event['duration'])
                self.time_warp_multiplier = float(event['multiplier'])
            elif kind == 'swap_personality':
                p = self.personality_points
                p['aggro'], p['stealth'] = p['stealth'], p['aggro']

            self._push_msg(self._flavored(msg, 'random', 0.5))
        logging.info("[Age] random event: %s", event.get('description', event['type']))

    # ------------------------------------------------------------------ #
    # Handshakes
    # ------------------------------------------------------------------ #

    def on_handshake(self, agent, filename, access_point, *args):
        try:
            if isinstance(access_point, dict):
                raw_enc = access_point.get('encryption', '')
                essid = access_point.get('essid') or 'unknown'
                bssid = str(access_point.get('mac') or access_point.get('bssid') or '').lower()
            else:
                logging.debug("[Age] AP was %s, not a dict", type(access_point).__name__)
                raw_enc, essid, bssid = '', 'unknown', ''

            enc = self._normalize_enc(raw_enc)

            with self.data_lock:
                base = self.points_map.get(enc, 1)
                points = base * self.prestige_multiplier * self._repeat_factor(bssid)

                self.streak += 1
                streak_threshold = 5
                if self.streak >= streak_threshold:
                    points *= 1.2
                    if self.streak == streak_threshold or self.streak % 10 == 0:
                        self._push_msg(self._flavored(f"Streak x{self.streak}! +20% points",
                                                      'success', 0.5))

                if self.active_event and self.event_handshakes_left > 0:
                    points *= self.event_multiplier
                    self.event_handshakes_left -= 1
                    if self.event_handshakes_left == 0:
                        self.active_event = None
                        self.event_multiplier = 1.0

                points = int(points)
                self.network_points += points
                self.handshake_count += 1
                self.total_handshakes_lifetime += 1
                self.last_active_epoch = self.epochs
                self.last_handshake_enc = enc
                self.personality_points['aggro'] += self.aggro_per_handshake
                self.handshake_this_epoch = True
                self.quiet_epochs = 0
                self.enc_types_captured.add(enc)

                self._check_secret_achievements()
                self._check_handshake_milestones()

            self._log_points(essid, enc, points)
            logging.info("[Age] handshake: %s (%s) +%d pts, streak %d",
                         essid, enc, points, self.streak)
            self.save_data()
        except Exception as e:
            logging.exception("[Age] handshake error: %s", e)

    def _repeat_factor(self, bssid):
        """Optional diminishing returns for re-capturing the same AP.

        Off by default — enable with `repeat_ap_penalty = true` if you'd rather
        not have one chatty router at home out-earn a night of walking.
        """
        if not self.repeat_ap_penalty or not bssid:
            return 1.0
        seen = self.seen_aps.get(bssid, 0)
        self.seen_aps[bssid] = seen + 1
        if len(self.seen_aps) > 4000:          # keep the stats file bounded
            self.seen_aps = dict(list(self.seen_aps.items())[-2000:])
        return max(0.25, 1.0 / (1 + seen))

    def on_deauthentication(self, agent, access_point, client_station):
        with self.data_lock:
            self.deauths += 1
            if self.deauths % 10 == 0:
                self.personality_points['aggro'] += 1

    def on_association(self, agent, access_point):
        with self.data_lock:
            self.associations += 1

    def _check_secret_achievements(self):
        hour = time.localtime().tm_hour
        if 2 <= hour < 4:
            self.night_owl_handshakes += 1
            # v4 tested == 10, so a reboot past the threshold locked it forever.
            if self.night_owl_handshakes >= 10 and "Night Owl" not in self.achievements_unlocked:
                self._unlock("Night Owl", 50)

        # v4 required exact set equality against points_map keys, which could
        # never match once an open/unknown network was captured.
        required = {'wpa3', 'wpa2', 'wpa', 'wep'}
        if required.issubset(self.enc_types_captured) and "Crypto King" not in self.achievements_unlocked:
            self._unlock("Crypto King", 100)

    def _check_handshake_milestones(self):
        for count, name in self.HANDSHAKE_MILESTONES:
            if self.total_handshakes_lifetime >= count and name not in self.achievements_unlocked:
                self._unlock(name, 50)

    def _unlock(self, name, points):
        self.achievements_unlocked.add(name)
        bonus = int(points * self.prestige_multiplier)
        self.network_points += bonus
        self._push_msg(self._flavored(f"Achievement: {name}! +{bonus}", 'success'),
                       _face('EXCITED'))
        logging.info("[Age] achievement unlocked: %s (+%d)", name, bonus)

    def _log_points(self, essid, enc, points):
        try:
            if self.log_max_bytes and os.path.exists(self.log_path):
                if os.path.getsize(self.log_path) > self.log_max_bytes:
                    os.replace(self.log_path, self.log_path + '.1')
            # ESSIDs can contain commas; quote them so the CSV stays parseable.
            safe_essid = str(essid).replace('"', "'").replace('\n', ' ')
            with open(self.log_path, 'a') as f:
                f.write(f'{int(time.time())},"{safe_essid}",{enc},{points}\n')
        except Exception as e:
            logging.error("[Age] points log write failed: %s", e)

    def initialize_handshakes(self):
        # `handshake_count` is zero both on a fresh install *and* on the first
        # boot after a rebirth. Only the former should re-scan the pcap dir.
        if self.handshakes_initialized or self.handshake_count:
            self.handshakes_initialized = True
            return
        self.handshakes_initialized = True
        candidates = [self.handshake_dir] if self.handshake_dir else []
        # /home/pi/handshakes since 2.9.3; /root/handshakes on older images.
        candidates += ['/home/pi/handshakes', '/root/handshakes',
                       '/var/lib/pwnagotchi/handshakes']
        for path in candidates:
            if path and os.path.isdir(path):
                count = 0
                for _root, _dirs, files in os.walk(path):
                    # Bettercap writes .pcapng on 2.9.5.5+; older images wrote
                    # .pcap. Count both so upgraders don't reset to zero.
                    count += sum(1 for f in files if f.endswith(self.HANDSHAKE_EXTS))
                if count:
                    self.handshake_count = count
                    self.total_handshakes_lifetime = max(self.total_handshakes_lifetime, count)
                    self.handshake_dir = path
                    logging.info("[Age] initialized with %d handshakes from %s", count, path)
                    self.save_data(force=True)
                    return

    # ------------------------------------------------------------------ #
    # Persistence
    # ------------------------------------------------------------------ #

    def load_data(self):
        if not os.path.exists(self.data_path):
            return
        try:
            with open(self.data_path, 'r') as f:
                data = json.load(f)
        except (ValueError, OSError) as e:
            # Don't silently start from zero: keep the broken file for forensics.
            logging.error("[Age] stats file unreadable (%s) — starting fresh", e)
            try:
                os.replace(self.data_path, self.data_path + '.corrupt')
            except OSError:
                pass
            return

        with self.data_lock:
            self.epochs = int(data.get('epochs', 0))
            self.train_epochs = float(data.get('train_epochs', 0))
            self.network_points = int(data.get('points', 0))
            self.handshake_count = int(data.get('handshakes', 0))
            self.total_handshakes_lifetime = int(data.get('total_handshakes', self.handshake_count))
            self.last_active_epoch = int(data.get('last_active', 0))
            self.streak = int(data.get('streak', 0))
            self.night_owl_handshakes = int(data.get('night_owl_handshakes', 0))
            self.enc_types_captured = {self._normalize_enc(e)
                                       for e in data.get('enc_types_captured', [])}
            self.achievements_unlocked = set(data.get('achievements', []))
            for trait in ('aggro', 'stealth', 'scholar'):
                self.personality_points[trait] = int(data.get(f'personality_{trait}', 0))
            self.prestige = int(data.get('prestige', 0))
            self.prestige_multiplier = float(
                data.get('prestige_multiplier', 1.0 + self.prestige * self.prestige_bonus))
            self.time_warp_active_until = int(data.get('time_warp_until', 0))
            self.time_warp_multiplier = float(data.get('time_warp_multiplier', 1.0))
            self.deauths = int(data.get('deauths', 0))
            self.associations = int(data.get('associations', 0))
            self.ai_training_seen = bool(data.get('ai_training_seen', False))
            self.last_train_step_epoch = int(data.get('last_train_step_epoch', 0))
            self.rebirth_pending = bool(data.get('rebirth_pending', False))
            self.quiet_epochs = int(data.get('quiet_epochs', 0))
            # Older stats files predate this flag; if they already have a
            # handshake count, treat the initial scan as done.
            self.handshakes_initialized = bool(
                data.get('handshakes_initialized', self.handshake_count > 0))
            self.seen_aps = {str(k): int(v)
                             for k, v in (data.get('seen_aps') or {}).items()}

            # Derive from current state rather than trusting stale strings.
            self.prev_age_title = data.get('prev_age') or self.get_age_title()
            self.prev_strength_title = data.get('prev_strength') or self.get_strength_title()

            # A handshake event mid-save shouldn't survive a reboot half-applied.
            self.active_event = None
            self.event_handshakes_left = int(data.get('event_handshakes_left', 0))
            self.event_multiplier = float(data.get('event_multiplier', 1.0))
            if self.event_handshakes_left > 0:
                self.active_event = {'type': 'handshake', 'restored': True}
            else:
                self.event_multiplier = 1.0

    def save_data(self, force=False):
        """Throttled, atomic save.

        v4 rewrote the JSON file on every epoch and every handshake with a
        plain open('w'), which is both hard on the SD card and a guaranteed
        way to end up with a truncated file if power drops mid-write.
        """
        now = time.time()
        with self.data_lock:
            self._dirty = True
            if not force and self.save_interval and (now - self._last_save) < self.save_interval:
                return
            self._last_save = now
            data = {
                'epochs': self.epochs,
                'train_epochs': round(self.train_epochs, 3),
                'points': self.network_points,
                'handshakes': self.handshake_count,
                'total_handshakes': self.total_handshakes_lifetime,
                'last_active': self.last_active_epoch,
                'prev_age': self.prev_age_title,
                'prev_strength': self.prev_strength_title,
                'streak': self.streak,
                'night_owl_handshakes': self.night_owl_handshakes,
                'enc_types_captured': sorted(self.enc_types_captured),
                'achievements': sorted(self.achievements_unlocked),
                'personality_aggro': self.personality_points['aggro'],
                'personality_stealth': self.personality_points['stealth'],
                'personality_scholar': self.personality_points['scholar'],
                'prestige': self.prestige,
                'prestige_multiplier': self.prestige_multiplier,
                'time_warp_until': self.time_warp_active_until,
                'time_warp_multiplier': self.time_warp_multiplier,
                'event_handshakes_left': self.event_handshakes_left,
                'event_multiplier': self.event_multiplier,
                'rebirth_pending': self.rebirth_pending,
                'deauths': self.deauths,
                'associations': self.associations,
                'ai_training_seen': self.ai_training_seen,
                'last_train_step_epoch': self.last_train_step_epoch,
                'quiet_epochs': self.quiet_epochs,
                'handshakes_initialized': self.handshakes_initialized,
                'seen_aps': self.seen_aps if self.repeat_ap_penalty else {},
                'version': self.__version__,
            }

            tmp = f"{self.data_path}.tmp"
            try:
                with open(tmp, 'w') as f:
                    json.dump(data, f, indent=2)
                    f.flush()
                    os.fsync(f.fileno())
                os.replace(tmp, self.data_path)
                self._dirty = False
            except OSError as e:
                logging.error("[Age] save error: %s", e)
                try:
                    os.remove(tmp)
                except OSError:
                    pass

    # ------------------------------------------------------------------ #
    # Web UI:  http://<pwnagotchi>:8080/plugins/age/
    # ------------------------------------------------------------------ #

    def on_webhook(self, path, request):
        try:
            from flask import abort
        except ImportError:
            return "flask unavailable"

        # With auto_rebirth = false there was otherwise no way to actually
        # spend a pending rebirth; the UI just read "Ready for Rebirth" forever.
        if path == 'rebirth':
            if not self.rebirth_pending:
                return "<html><body>No rebirth pending.</body></html>"
            self.trigger_rebirth()
            return ("<html><head><meta http-equiv='refresh' content='2;url=/plugins/age/'>"
                    f"</head><body>Rebirth #{self.prestige} triggered.</body></html>")

        if path in (None, '/', 'index'):
            with self.data_lock:
                rows = [
                    ("Age title", self.get_age_title()),
                    ("Epochs", f"{self.epochs:,}"),
                    ("Strength title", self.get_strength_title()),
                    ("Train epochs", f"{int(self.train_epochs):,}"),
                    ("Network points", f"{self.network_points:,}"),
                    ("Prestige", f"{self.prestige} ({self.prestige_multiplier:.1f}x)"),
                    ("Handshakes (cycle)", f"{self.handshake_count:,}"),
                    ("Handshakes (lifetime)", f"{self.total_handshakes_lifetime:,}"),
                    ("Current streak", self.streak),
                    ("Deauths", f"{self.deauths:,}"),
                    ("Dominant trait", self.get_dominant_personality()),
                    ("Aggro / Stealth / Scholar",
                     "{aggro} / {stealth} / {scholar}".format(**self.personality_points)),
                    ("Encryption seen", ", ".join(sorted(self.enc_types_captured)) or "—"),
                    ("Achievements", ", ".join(sorted(self.achievements_unlocked)) or "—"),
                ]
            # Achievement names are internal, but escape anyway — cheap, and
            # this table may grow to include ESSIDs later.
            body = "".join(
                f"<tr><th>{html.escape(str(k))}</th><td>{html.escape(str(v))}</td></tr>"
                for k, v in rows)
            rebirth_link = ("<p><a href='/plugins/age/rebirth'>Trigger rebirth</a></p>"
                            if self.rebirth_pending and not self.auto_rebirth else "")
            return (
                "<html><head><title>Age</title><style>"
                "body{font-family:sans-serif;margin:2em;background:#111;color:#eee}"
                "table{border-collapse:collapse}"
                "th,td{padding:.4em .9em;border-bottom:1px solid #333;text-align:left}"
                "th{color:#8f8;font-weight:600}"
                "a{color:#8f8}"
                "</style></head><body><h1>Age</h1>"
                f"<table>{body}</table>{rebirth_link}</body></html>"
            )
        abort(404)
