import logging
import struct
import time
import os
import RPi.GPIO as GPIO
import pwnagotchi
import pwnagotchi.plugins as plugins
import pwnagotchi.ui.fonts as fonts
from pwnagotchi.ui.components import LabeledValue
from pwnagotchi.ui.view import BLACK

# Known I2C addresses
KNOWN_I2C_ADDRESSES = {
    'max170xx': 0x36,
    'ina219': [0x40, 0x41, 0x42, 0x43],
    'pisugar': 0x75,
    'ip5310': 0x75,
}

# Registers
MAX_REG_VCELL = 0x02
MAX_REG_SOC = 0x04
MAX_REG_MODE = 0x06
MAX_REG_CONFIG = 0x0C
MAX_REG_MODEL = 0x08

INA_REG_CONFIG = 0x00
INA_REG_BUS_V = 0x02
INA_REG_CURRENT = 0x04

PISUGAR_REG_BATTERY = 0x2A
PISUGAR_REG_CHARGING = 0x02

# Default charging GPIO for MAX170xx boards
DEFAULT_CHARGING_GPIOS = {
    'x1200': 6,
    'ups_lite': 16,
}

class MadHatterUPS:
    def __init__(self, charging_gpio=None, alert_threshold=10, ups_type='auto'):
        import smbus
        self._bus = smbus.SMBus(1)
        self._ina_addr = None
        self._charging_gpio = None

        # State tracking
        self._last_capacity = 0.0
        self._last_voltage = 0.0
        self._last_charging = '-'
        self._error_count = 0
        self._success_count = 0
        self._cycle_count = 0
        self._was_full = False

        # Detect type
        self._type = self._detect_type() if ups_type == 'auto' else ups_type
        logging.info(f"[MadHatterUPS] Detected/Selected type: {self._type}")

        # GPIO handling
        if charging_gpio is not None and isinstance(charging_gpio, int):
            GPIO.setwarnings(False)
            GPIO.setmode(GPIO.BCM)
            GPIO.setup(charging_gpio, GPIO.IN)
            self._charging_gpio = charging_gpio
        elif charging_gpio is None:
            default_gpio = DEFAULT_CHARGING_GPIOS.get(self._type)
            if default_gpio is not None:
                GPIO.setwarnings(False)
                GPIO.setmode(GPIO.BCM)
                GPIO.setup(default_gpio, GPIO.IN)
                self._charging_gpio = default_gpio
                logging.info(f"[MadHatterUPS] Using default charging GPIO {default_gpio} for {self._type}")

        # Type-specific init
        self._init_specific(alert_threshold)

    def _detect_type(self):
        known_addrs = set()
        for val in KNOWN_I2C_ADDRESSES.values():
            if isinstance(val, list):
                known_addrs.update(val)
            else:
                known_addrs.add(val)

        devices = set()
        for addr in known_addrs:
            try:
                self._bus.read_byte(addr)
                devices.add(addr)
            except:
                pass

        if KNOWN_I2C_ADDRESSES['max170xx'] in devices:
            try:
                model = self._bus.read_word_data(KNOWN_I2C_ADDRESSES['max170xx'], MAX_REG_MODEL)
                return 'x1200' if model == 0x0044 else 'ups_lite'
            except:
                logging.debug("[MadHatterUPS] MAX170xx model check failed, assuming x1200")
                return 'x1200'

        ina_addrs = [a for a in KNOWN_I2C_ADDRESSES['ina219'] if a in devices]
        if ina_addrs:
            self._ina_addr = ina_addrs[0]
            return 'ina219_generic'

        if KNOWN_I2C_ADDRESSES['pisugar'] in devices:
            return 'pisugar'

        if KNOWN_I2C_ADDRESSES['ip5310'] in devices:
            return 'x750'

        logging.warning("[MadHatterUPS] No known UPS detected")
        return 'ina219_generic'

    def _init_specific(self, alert_threshold):
        if self._type in ['x1200', 'ups_lite']:
            self.voltage = self._max_voltage
            self.capacity = self._max_capacity
            self.charging = self._gpio_charging if self._charging_gpio else self._dummy_charging
            self.current = lambda: 0.0

        elif self._type == 'ina219_generic':
            if not self._ina_addr:
                raise RuntimeError("INA219 address not detected")
            self.voltage = self._ina_voltage
            self.capacity = self._ina_capacity
            self.charging = self._ina_charging
            self.current = self._ina_current
            try:
                self._bus.write_word_data(self._ina_addr, INA_REG_CONFIG, 0x399F)
                logging.info("[MadHatterUPS] INA219 configured")
            except Exception as e:
                logging.warning(f"[MadHatterUPS] INA219 config failed: {e}")

        elif self._type == 'pisugar':
            self.voltage = self._pisugar_voltage
            self.capacity = self._pisugar_capacity
            self.charging = self._pisugar_charging
            self.current = lambda: 0.0

        elif self._type == 'x750':
            self.voltage = self._pisugar_voltage
            self.capacity = self._pisugar_capacity
            self.charging = self._pisugar_charging
            self.current = lambda: 0.0

        else:
            raise ValueError(f"Unsupported UPS type: {self._type}")

        # MAX170xx initialization (quick-start + alert threshold)
        if self._type in ['x1200', 'ups_lite']:
            try:
                self._bus.write_word_data(KNOWN_I2C_ADDRESSES['max170xx'], MAX_REG_MODE, 0x4000)
                time.sleep(0.1)
                logging.info("[MadHatterUPS] MAX170xx quick start performed")
            except Exception as e:
                logging.error(f"[MadHatterUPS] QuickStart failed: {e}")

            try:
                alert_value = 32 - alert_threshold
                config = self._bus.read_word_data(KNOWN_I2C_ADDRESSES['max170xx'], MAX_REG_CONFIG) & 0xFFE0
                config |= alert_value
                self._bus.write_word_data(KNOWN_I2C_ADDRESSES['max170xx'], MAX_REG_CONFIG, config)
                logging.debug(f"[MadHatterUPS] Alert threshold set to {alert_threshold}%")
            except Exception as e:
                logging.error(f"[MadHatterUPS] Alert threshold failed: {e}")

    # MAX170xx methods
    def _max_voltage(self):
        def read_func():
            read = self._bus.read_word_data(KNOWN_I2C_ADDRESSES['max170xx'], MAX_REG_VCELL)
            swapped = struct.unpack("<H", struct.pack(">H", read))[0]
            return (swapped >> 4) * 1.25 / 1000
        try:
            voltage = self._read_with_retry(read_func)
            self._last_voltage = voltage
            return voltage
        except:
            return self._last_voltage

    def _max_capacity(self):
        def read_func():
            read = self._bus.read_word_data(KNOWN_I2C_ADDRESSES['max170xx'], MAX_REG_SOC)
            swapped = struct.unpack("<H", struct.pack(">H", read))[0]
            return swapped / 256.0
        try:
            capacity = self._read_with_retry(read_func)
            if capacity >= 99.0 and not self._was_full:
                self._cycle_count += 1
                self._was_full = True
            elif capacity < 99.0:
                self._was_full = False
            self._last_capacity = capacity
            return capacity
        except:
            return self._last_capacity

    # INA219 methods
    def _ina_voltage(self):
        def read_func():
            read = self._bus.read_word_data(self._ina_addr, INA_REG_BUS_V)
            return (read >> 3) * 0.004
        try:
            voltage = self._read_with_retry(read_func)
            self._last_voltage = voltage
            return voltage
        except:
            return self._last_voltage

    def _ina_current(self):
        def read_func():
            read = self._bus.read_word_data(self._ina_addr, INA_REG_CURRENT)
            if read > 32767:
                read -= 65536
            return read * 0.001
        try:
            return self._read_with_retry(read_func)
        except:
            return 0.0

    def _ina_capacity(self):
        voltage = self.voltage()
        current = self.current()

        soc_table = [
            (4.20, 100.0), (4.15, 95.0), (4.10, 90.0), (4.05, 80.0),
            (4.00, 70.0), (3.95, 60.0), (3.90, 50.0), (3.85, 40.0),
            (3.80, 30.0), (3.75, 20.0), (3.70, 10.0), (3.60, 0.0),
        ]

        if voltage >= soc_table[0][0]:
            soc = 100.0
        elif voltage <= soc_table[-1][0]:
            soc = 0.0
        else:
            for i in range(len(soc_table) - 1):
                v_high, s_high = soc_table[i]
                v_low, s_low = soc_table[i + 1]
                if v_low <= voltage < v_high:
                    frac = (voltage - v_low) / (v_high - v_low)
                    soc = s_low + frac * (s_high - s_low)
                    break
            else:
                soc = 0.0

        if voltage > 4.15 and abs(current) < 0.01 and not self._was_full:
            self._cycle_count += 1
            self._was_full = True
        elif voltage < 4.00:
            self._was_full = False

        self._last_capacity = soc
        return soc

    def _ina_charging(self):
        current = self.current()
        return '+' if current > 0 else '-'

    # PiSugar / X750
    def _pisugar_voltage(self):
        def read_func():
            high = self._bus.read_byte_data(KNOWN_I2C_ADDRESSES['pisugar'], 0x22)
            low = self._bus.read_byte_data(KNOWN_I2C_ADDRESSES['pisugar'], 0x23)
            return ((high << 8) | low) / 1000.0
        try:
            voltage = self._read_with_retry(read_func)
            self._last_voltage = voltage
            return voltage
        except:
            return self._last_voltage

    def _pisugar_capacity(self):
        def read_func():
            return self._bus.read_byte_data(KNOWN_I2C_ADDRESSES['pisugar'], PISUGAR_REG_BATTERY)
        try:
            capacity = self._read_with_retry(read_func)
            voltage = self.voltage()
            if voltage > 4.15 and not self._was_full:
                self._cycle_count += 1
                self._was_full = True
            elif voltage < 4.00:
                self._was_full = False
            self._last_capacity = capacity
            return capacity
        except:
            return self._last_capacity

    def _pisugar_charging(self):
        def read_func():
            status = self._bus.read_byte_data(KNOWN_I2C_ADDRESSES['pisugar'], PISUGAR_REG_CHARGING)
            return '+' if (status & 0x40) else '-'
        try:
            return self._read_with_retry(read_func)
        except:
            return self._last_charging

    # Helpers
    def _gpio_charging(self):
        try:
            status = '+' if GPIO.input(self._charging_gpio) == GPIO.HIGH else '-'
            self._last_charging = status
            return status
        except:
            return self._last_charging

    def _dummy_charging(self):
        return '-'

    def _read_with_retry(self, func, max_retries=3):
        for attempt in range(max_retries):
            try:
                value = func()
                self._success_count += 1
                if self._success_count >= 10:
                    self._error_count = 0
                    self._success_count = 0
                return value
            except Exception as e:
                time.sleep(0.1)
                if attempt == max_retries - 1:
                    self._error_count += 1
                    logging.debug(f"[MadHatterUPS] Read failed ({self._error_count}): {e}")
                    raise
        return None

    def get_cycle_count(self):
        return self._cycle_count

class MadHatter(plugins.Plugin):
    __name__ = 'mad_hatter'
    __author__ = 'AlienMajik'
    __version__ = '1.3.3'
    __license__ = 'GPL3'
    __description__ = 'Universal UPS plugin – supports X1200/UPS Lite, INA219 hats (Waveshare/Seengreat/etc.), PiSugar, with accurate SOC, dynamic runtime, icons, and shutdown.'

    __defaults__ = {
        'enabled': True,
        'show_voltage': False,
        'shutdown_enabled': False,
        'shutdown_threshold': 5,
        'warning_threshold': 15,
        'shutdown_grace': 3,
        'shutdown_grace_period': 30,
        'poll_interval': 10,
        'ui_position_x': None,
        'ui_position_y': 0,
        'show_icon': True,
        'battery_mah': 2000,
        'avg_current_ma': 200,
        'debug_mode': False,
        'charging_gpio': None,
        'alert_threshold': 10,
        'ups_type': 'auto',
    }

    def __init__(self):
        self.ups = None
        self.low_battery_count = 0
        self._shutdown_start_time = None
        self._last_poll_time = 0
        self.cycle_file = '/root/.mad_hatter_cycle_count'

    def on_loaded(self):
        self.ups = MadHatterUPS(
            charging_gpio=self.options.get('charging_gpio'),
            alert_threshold=self.options['alert_threshold'],
            ups_type=self.options['ups_type']
        )

        try:
            if os.path.exists(self.cycle_file):
                with open(self.cycle_file, 'r') as f:
                    self.ups._cycle_count = int(f.read().strip() or 0)
        except Exception as e:
            logging.debug(f"[MadHatter] Cycle count load failed: {e}")

        logging.info("[MadHatter] Plugin v1.3.3 loaded")

    def on_ui_setup(self, ui):
        pos_x = self.options['ui_position_x'] if self.options['ui_position_x'] is not None else ui.width() - 50
        pos = (pos_x, self.options['ui_position_y'])
        ui.add_element('mad_hatter', LabeledValue(
            color=BLACK,
            label='UPS',
            value='?',
            position=pos,
            label_font=fonts.Bold,
            text_font=fonts.Medium
        ))

    def _build_display_str(self, capacity, charging, voltage, current):
        if self.ups._error_count > 10:
            return "UPS ERR"

        battery_icon = "🪫" if capacity < 20 else "🔋"
        charging_icon = "⚡" if charging == '+' else ""
        base = f"{battery_icon}{int(round(capacity))}%{charging_icon}"

        if self.options['show_voltage']:
            base = f"{voltage:.2f}V {base}"

        time_str = ""
        mah = self.options['battery_mah']
        curr_ma = current * 1000.0
        threshold_ma = 30

        if 0 < capacity < 100:
            if charging == '+' and curr_ma > threshold_ma:
                remaining_mah = (100 - capacity) / 100 * mah
                mins = int(remaining_mah / curr_ma * 60 + 0.5)
                if mins > 0:
                    time_str = f" ↑{mins}m"
            else:
                discharge_ma = max(abs(curr_ma), self.options['avg_current_ma']) if charging == '-' else self.options['avg_current_ma']
                remain_mah = capacity / 100 * mah
                mins = int(remain_mah / discharge_ma * 60 + 0.5)
                time_str = f" ~{mins}m"

        base += time_str

        if self.options['debug_mode']:
            base += f" E{self.ups._error_count} C{self.ups.get_cycle_count()}"
            if abs(curr_ma) > threshold_ma:
                base += f" {int(curr_ma)}mA"

        return base

    def on_ui_update(self, ui):
        if not self.ups:
            return

        current_time = time.time()

        # Default to last known values
        capacity = self.ups._last_capacity
        charging = self.ups._last_charging
        voltage = self.ups._last_voltage
        current = 0.0

        if current_time - self._last_poll_time >= self.options['poll_interval']:
            try:
                capacity = self.ups.capacity()
                charging = self.ups.charging()
                voltage = self.ups.voltage()
                if hasattr(self.ups, 'current'):
                    current = self.ups.current()
                self._last_poll_time = current_time
                if self.options['debug_mode']:
                    logging.debug(f"[MadHatter] Fresh read: {capacity:.1f}% {charging} {voltage:.2f}V {current:.3f}A")
            except Exception as e:
                logging.error(f"[MadHatter] Poll failed: {e}")

        display_str = self._build_display_str(capacity, charging, voltage, current)
        ui.set('mad_hatter', display_str)

        # Shutdown logic
        if self.options['shutdown_enabled']:
            threshold = self.options['shutdown_threshold']
            warning = self.options['warning_threshold']

            if capacity < warning and charging == '-':
                logging.warning(f"[MadHatter] Low battery ({capacity:.1f}%)")

            if capacity < threshold and charging == '-':
                if capacity < 2:
                    logging.critical("[MadHatter] Critical battery – shutdown!")
                    pwnagotchi.shutdown()

                if self.low_battery_count == 0:
                    self._shutdown_start_time = time.time()
                self.low_battery_count += 1

                if (self.low_battery_count >= self.options['shutdown_grace'] and
                    time.time() - self._shutdown_start_time >= self.options['shutdown_grace_period']):
                    logging.critical("[MadHatter] Safe shutdown")
                    pwnagotchi.shutdown()
            else:
                self.low_battery_count = 0
                self._shutdown_start_time = None

    def on_unload(self, ui):
        try:
            with open(self.cycle_file, 'w') as f:
                f.write(str(self.ups.get_cycle_count()))
        except Exception as e:
            logging.error(f"[MadHatter] Cycle save failed: {e}")

        with ui._lock:
            ui.remove_element('mad_hatter')

        if self.ups and self.ups._charging_gpio is not None:
            try:
                GPIO.cleanup(self.ups._charging_gpio)
            except:
                pass

        logging.info("[MadHatter] Unloaded.")

