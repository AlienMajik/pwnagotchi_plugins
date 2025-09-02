import logging
import struct
import time
import RPi.GPIO as GPIO
import pwnagotchi
import pwnagotchi.plugins as plugins
import pwnagotchi.ui.fonts as fonts
from pwnagotchi.ui.components import LabeledValue
from pwnagotchi.ui.view import BLACK

# Known I2C addresses for detection
KNOWN_I2C_ADDRESSES = {
    'max170xx': 0x36,  # MAX17043/44 for X1200, UPS Lite
    'ina219': [0x40, 0x41],  # INA219 default for Waveshare, SB, EP-0136
    'pisugar': 0x75,  # PiSugar custom MCU
    'ip5310': 0x75,  # X750 IP5310 (similar to PiSugar)
}

# Registers for MAX170xx (X1200, UPS Lite)
MAX_REG_VCELL = 0x02
MAX_REG_SOC = 0x04
MAX_REG_MODE = 0x06  # Quick start (write 4000h)
MAX_REG_CONFIG = 0x0C
MAX_REG_MODEL = 0x08  # Model ID for MAX170xx

# Registers for INA219 (Waveshare, etc.)
INA_REG_CONFIG = 0x00
INA_REG_SHUNT_V = 0x01
INA_REG_BUS_V = 0x02
INA_REG_POWER = 0x03
INA_REG_CURRENT = 0x04

# PiSugar specific registers
PISUGAR_REG_BATTERY = 0x2A  # Battery percentage
PISUGAR_REG_CHARGING = 0x02  # Charging status bit

# Default charging GPIO per HAT
DEFAULT_CHARGING_GPIOS = {
    'x1200': 6,  # AC power status (high = AC present)
    'ups_lite': 16,  # Similar
    'waveshare_c': 25,  # Example GPIO for charging LED
    'pisugar': None,  # I2C based
    'sb_ups': None,
    'x750': None,
    'ep0136': None,
}

class MadHatterUPS:
    def __init__(self, charging_gpio=None, alert_threshold=10, ups_type='auto'):
        import smbus
        self._bus = smbus.SMBus(1)

        # Suppress GPIO warnings and set mode if GPIO used
        if charging_gpio is not None:
            GPIO.setwarnings(False)
            GPIO.setmode(GPIO.BCM)
            GPIO.setup(charging_gpio, GPIO.IN)
            self._charging_gpio = charging_gpio

        # Track last known values
        self._last_capacity = 0.0
        self._last_voltage = 0.0
        self._last_charging = '-'

        # Error tracking
        self._error_count = 0
        self._success_count = 0  # Track successful reads for error reset

        # Battery health
        self._cycle_count = 0
        self._was_full = False

        # Detect UPS type
        self._type = self._detect_type() if ups_type == 'auto' else ups_type
        logging.info(f"[MadHatterUPS] Detected/Selected type: {self._type}")

        # Initialize based on type
        self._init_specific(alert_threshold)

    def _detect_type(self):
        """Scan I2C bus to detect UPS type."""
        devices = []
        for addr in range(0x03, 0x78):
            try:
                self._bus.read_byte(addr)
                devices.append(addr)
            except:
                pass

        if KNOWN_I2C_ADDRESSES['max170xx'] in devices:
            try:
                model = self._bus.read_word_data(KNOWN_I2C_ADDRESSES['max170xx'], MAX_REG_MODEL)
                return 'x1200' if model == 0x0044 else 'ups_lite'
            except:
                logging.debug("[MadHatterUPS] MAX170xx model check failed, assuming x1200")
                return 'x1200'
        elif any(addr in devices for addr in KNOWN_I2C_ADDRESSES['ina219']):
            return 'waveshare_c'
        elif KNOWN_I2C_ADDRESSES['pisugar'] in devices:
            return 'pisugar'
        elif KNOWN_I2C_ADDRESSES['ip5310'] in devices:
            return 'x750'
        else:
            logging.warning("[MadHatterUPS] No known UPS detected, defaulting to x1200")
            return 'x1200'

    def _init_specific(self, alert_threshold):
        """Type-specific initialization."""
        if self._type in ['x1200', 'ups_lite']:
            self.quick_start = self._max_quick_start
            self.set_alert_threshold = self._max_set_alert_threshold
            self.voltage = self._max_voltage
            self.capacity = self._max_capacity
            self.charging = self._gpio_charging if self._charging_gpio else self._dummy_charging
            self.quick_start()
            self.set_alert_threshold(alert_threshold)
        elif self._type in ['waveshare_c', 'sb_ups', 'ep0136']:
            self.voltage = self._ina_voltage
            self.capacity = self._ina_capacity
            self.charging = self._ina_charging
            self._bus.write_word_data(KNOWN_I2C_ADDRESSES['ina219'][0], INA_REG_CONFIG, 0x399F)
        elif self._type == 'pisugar':
            self.voltage = self._pisugar_voltage
            self.capacity = self._pisugar_capacity
            self.charging = self._pisugar_charging
        elif self._type == 'x750':
            self.voltage = self._ip_voltage
            self.capacity = self._ip_capacity
            self.charging = self._ip_charging
        else:
            raise ValueError(f"Unsupported UPS type: {self._type}")

    # MAX170xx specific methods
    def _max_quick_start(self):
        try:
            self._bus.write_word_data(KNOWN_I2C_ADDRESSES['max170xx'], MAX_REG_MODE, 0x4000)
            time.sleep(0.1)
            logging.info("[MadHatterUPS] Performed quick start calibration")
        except Exception as e:
            logging.error(f"[MadHatterUPS] QuickStart failed: {e}")

    def _max_set_alert_threshold(self, threshold):
        try:
            alert_value = 32 - threshold
            config = self._bus.read_word_data(KNOWN_I2C_ADDRESSES['max170xx'], MAX_REG_CONFIG) & 0xFFE0
            config |= alert_value
            self._bus.write_word_data(KNOWN_I2C_ADDRESSES['max170xx'], MAX_REG_CONFIG, config)
            logging.debug(f"[MadHatterUPS] Set alert threshold to {threshold}%")
        except Exception as e:
            logging.error(f"[MadHatterUPS] Alert threshold set failed: {e}")

    def _max_voltage(self):
        def read_func():
            read = self._bus.read_word_data(KNOWN_I2C_ADDRESSES['max170xx'], MAX_REG_VCELL)
            swapped = struct.unpack("<H", struct.pack(">H", read))[0]
            vcell_value = swapped >> 4
            return vcell_value * 1.25 / 1000
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

    # INA219 specific methods
    def _ina_voltage(self):
        def read_func():
            read = self._bus.read_word_data(KNOWN_I2C_ADDRESSES['ina219'][0], INA_REG_BUS_V)
            return (read >> 3) * 0.004
        try:
            voltage = self._read_with_retry(read_func)
            self._last_voltage = voltage
            return voltage
        except:
            return self._last_voltage

    def _ina_capacity(self):
        voltage = self.voltage()
        # Lookup table for 3.7V LiPo SOC
        soc_table = [
            (4.20, 100), (4.10, 90), (4.00, 80), (3.90, 60), (3.80, 40),
            (3.70, 20), (3.60, 10), (3.50, 5), (3.30, 0)
        ]
        for v, soc in soc_table:
            if voltage >= v:
                if voltage > 4.15 and abs(self._ina_current()) < 10 and not self._was_full:
                    self._cycle_count += 1
                    self._was_full = True
                elif voltage < 4.0:
                    self._was_full = False
                self._last_capacity = soc
                return soc
        self._last_capacity = 0
        return 0

    def _ina_charging(self):
        current = self._ina_current()
        return '+' if current > 0 else '-'

    def _ina_current(self):
        def read_func():
            read = self._bus.read_word_data(KNOWN_I2C_ADDRESSES['ina219'][0], INA_REG_CURRENT)
            if read > 32767:
                read -= 65536
            return read * 0.001
        try:
            return self._read_with_retry(read_func)
        except:
            return 0

    # PiSugar specific
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
            capacity = self._bus.read_byte_data(KNOWN_I2C_ADDRESSES['pisugar'], PISUGAR_REG_BATTERY)
            return capacity
        try:
            capacity = self._read_with_retry(read_func)
            voltage = self.voltage()
            if voltage > 4.15 and not self._was_full:
                self._cycle_count += 1
                self._was_full = True
            elif voltage < 4.0:
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

    # X750 (IP5310)
    def _ip_voltage(self):
        return self._pisugar_voltage()  # Reuse if similar
    def _ip_capacity(self):
        return self._pisugar_capacity()
    def _ip_charging(self):
        return self._pisugar_charging()

    # Generic helpers
    def _gpio_charging(self):
        def read_func():
            return '+' if GPIO.input(self._charging_gpio) == GPIO.HIGH else '-'
        try:
            status = self._read_with_retry(read_func)
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
                if self._success_count >= 10:  # Reset error count after 10 successful reads
                    self._error_count = 0
                    self._success_count = 0
                return value
            except Exception as e:
                time.sleep(0.1)
                if attempt == max_retries - 1:
                    self._error_count += 1
                    logging.error(f"[MadHatterUPS] Read failed after {max_retries} retries: {str(e)}")
                    raise
        return None

    def get_cycle_count(self):
        return self._cycle_count

class MadHatter(plugins.Plugin):
    __name__ = 'mad_hatter'
    __author__ = 'AlienMajik'
    __version__ = '1.2.2'  # Updated version for enhancements
    __license__ = 'GPL3'
    __description__ = 'Universal enhanced plugin for various UPS HATs: Battery indicator, voltage, auto-shutdown, polling, UI customization, error diagnostics, health monitoring, auto-detection, and improved charging detection with calibration.'
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
        self._last_display_str = "?"

    def on_loaded(self):
        self.ups = MadHatterUPS(
            charging_gpio=self.options['charging_gpio'],
            alert_threshold=self.options['alert_threshold'],
            ups_type=self.options['ups_type']
        )
        logging.info("[MadHatter] Plugin loaded with enhancements.")

    def on_ui_setup(self, ui):
        pos_x = self.options['ui_position_x'] if self.options['ui_position_x'] is not None else ui.width() - 50
        pos = (pos_x, self.options['ui_position_y'])
        ui.add_element('mad_hatter', LabeledValue(
            color=BLACK,
            label='UPS',
            value='0%',
            position=pos,
            label_font=fonts.Bold,
            text_font=fonts.Medium
        ))

    def _build_display_str(self, capacity, charging, voltage):
        base_str = f"{int(capacity)}{charging}"
        if self.options['show_voltage']:
            base_str = f"{voltage:.1f}V {base_str}"

        if self.options['show_icon']:
            battery_icon = "🔋"
            charging_icon = "⚡" if charging == '+' else ""
            base_str = f"{battery_icon}{base_str}{charging_icon}"

        if capacity > 0:
            time_remaining = (capacity / 100) * self.options['battery_mah'] / self.options['avg_current_ma']
            mins = int(time_remaining * 60)
            base_str += f" (~{mins}m)"

        if self.options['debug_mode']:
            base_str += f" Err:{self.ups._error_count} Cyc:{self.ups.get_cycle_count()}"

        return base_str

    def on_ui_update(self, ui):
        if not self.ups:
            return

        current_time = time.time()
        fresh_read = False

        if current_time - self._last_poll_time >= self.options['poll_interval']:
            try:
                capacity = self.ups.capacity()
                charging = self.ups.charging()
                voltage = self.ups.voltage()
                fresh_read = True
                self._last_poll_time = current_time
                if self.options['debug_mode']:
                    logging.debug(f"[MadHatter] Polled: {capacity}% {charging} {voltage:.1f}V")
            except Exception as e:
                logging.error(f"[MadHatter] Poll failed: {str(e)}")
                capacity = self.ups._last_capacity
                charging = self.ups._last_charging
                voltage = self.ups._last_voltage
        else:
            capacity = self.ups._last_capacity
            charging = self.ups._last_charging
            voltage = self.ups._last_voltage

        display_str = self._build_display_str(capacity, charging, voltage)

        if capacity == 0 and charging == '-':
            display_str = "?"

        ui.set('mad_hatter', display_str)
        self._last_display_str = display_str

        if self.options['shutdown_enabled']:
            threshold = self.options['shutdown_threshold']
            warning_threshold = self.options['warning_threshold']

            if not fresh_read and capacity < warning_threshold:
                try:
                    capacity = self.ups.capacity()
                    charging = self.ups.charging()
                except Exception as e:
                    logging.error(f"[MadHatter] Low battery re-poll failed: {str(e)}")

            if capacity < warning_threshold and charging == '-':
                logging.warning(f"[MadHatter] Battery low ({capacity}%) - Consider charging!")

            if capacity < threshold and charging == '-':
                if capacity < 2:  # Immediate shutdown for critical levels
                    logging.critical("[MadHatter] Battery critically low (<2%)! Shutting down.")
                    pwnagotchi.shutdown()
                if self.low_battery_count == 0:
                    self._shutdown_start_time = time.time()
                self.low_battery_count += 1
                logging.warning(f"[MadHatter] Low battery ({capacity}%) - count: {self.low_battery_count}/{self.options['shutdown_grace']}")
                if (self.low_battery_count >= self.options['shutdown_grace'] and
                    self._shutdown_start_time and
                    time.time() - self._shutdown_start_time >= self.options['shutdown_grace_period']):
                    logging.critical("[MadHatter] Battery critically low! Shutting down safely.")
                    pwnagotchi.shutdown()
            elif charging == '+' or capacity >= threshold:
                self.low_battery_count = 0
                self._shutdown_start_time = None

    def on_unload(self, ui):
        with ui._lock:
            ui.remove_element('mad_hatter')
        if self.options['charging_gpio'] is not None:
            GPIO.cleanup(self.options['charging_gpio'])
        logging.info("[MadHatter] Plugin unloaded.")
