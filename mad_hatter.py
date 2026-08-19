"""
MadHatter - Universal UPS / battery plugin for Pwnagotchi
=========================================================

Version : 2.0.1
Author  : AlienMajik (original), community enhancements
License : GPL3

Supports MAX17040/17048 fuel gauges (Geekworm X1200, UPS-Lite), all INA219
based HATs (Waveshare, Seengreat, SB Components, EP-0136, ...), and the
PiSugar 2 / 2 Pro / 3 families.

"""

import json
import logging
import os
import tempfile
import threading
import time

import pwnagotchi
import pwnagotchi.plugins as plugins
import pwnagotchi.ui.fonts as fonts
from pwnagotchi.ui.components import LabeledValue
from pwnagotchi.ui.view import BLACK

# ---------------------------------------------------------------------------
# Optional imports - never let a missing library take down the whole daemon.
# ---------------------------------------------------------------------------

SMBus = None
_SMBUS_IMPORT_ERROR = None
try:
    from smbus2 import SMBus  # preferred: pure python, no deprecation issues
except Exception:  # pragma: no cover
    try:
        from smbus import SMBus
    except Exception as exc:  # pragma: no cover
        _SMBUS_IMPORT_ERROR = exc

GPIO = None
try:
    import RPi.GPIO as GPIO  # noqa: N814  (also satisfied by rpi-lgpio on Pi 5)
except Exception:  # pragma: no cover
    GPIO = None

LOG = "[MadHatter]"

# ---------------------------------------------------------------------------
# Register maps
# ---------------------------------------------------------------------------

MAX_ADDR = 0x36
MAX_REG_VCELL = 0x02
MAX_REG_SOC = 0x04
MAX_REG_MODE = 0x06
MAX_REG_VERSION = 0x08
MAX_REG_CONFIG = 0x0C

INA_ADDRS = (0x40, 0x41, 0x42, 0x43, 0x44, 0x45)
INA_REG_CONFIG = 0x00
INA_REG_SHUNT_V = 0x01
INA_REG_BUS_V = 0x02
INA_REG_CURRENT = 0x04
INA_REG_CALIB = 0x05

# 32V bus range, +/-320mV PGA, 12 bit both ADCs, shunt+bus continuous
INA_CONFIG_VALUE = 0x399F

PISUGAR2_ADDR = 0x75   # IP5209 (PiSugar 2) / IP5312 (PiSugar 2 Pro)
PISUGAR3_ADDR = 0x57   # PiSugar 3 / 3 Plus

# Sensible default charging-detect GPIO (BCM numbering) per board family.
DEFAULT_CHARGING_GPIOS = {
    "x1200": 6,
    "ups_lite": 4,
}

# Resting open-circuit-voltage curve for a single Li-ion / LiPo cell.
# (volts, state-of-charge %). Must be ordered high -> low.
LIION_OCV_CURVE = (
    (4.20, 100.0), (4.15, 95.0), (4.11, 90.0), (4.08, 85.0), (4.02, 80.0),
    (3.98, 75.0), (3.95, 70.0), (3.91, 65.0), (3.87, 60.0), (3.85, 55.0),
    (3.84, 50.0), (3.82, 45.0), (3.80, 40.0), (3.79, 35.0), (3.77, 30.0),
    (3.75, 25.0), (3.73, 20.0), (3.71, 15.0), (3.69, 10.0), (3.61, 5.0),
    (3.40, 2.0), (3.00, 0.0),
)

STATE_FILE = "/root/.mad_hatter_state.json"
LEGACY_CYCLE_FILE = "/root/.mad_hatter_cycle_count"


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

def _swap16(value):
    """Convert between the byte order SMBus gives us and the big-endian order
    every one of these chips actually uses on the wire."""
    value &= 0xFFFF
    return ((value & 0xFF) << 8) | (value >> 8)


def _to_signed16(value):
    value &= 0xFFFF
    return value - 0x10000 if value & 0x8000 else value


def _clamp(value, low, high):
    return max(low, min(high, value))


def _as_optional_int(value):
    """TOML has no ``null``. Accept None, -1, '', 'none', 'null', 'auto', 'off'
    as 'not set' so the config can never explode on a literal the user copied
    out of an old README."""
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, str):
        cleaned = value.strip().lower()
        if cleaned in ("", "none", "null", "auto", "off", "-1", "nil"):
            return None
        try:
            value = int(cleaned)
        except ValueError:
            return None
    try:
        value = int(value)
    except (TypeError, ValueError):
        return None
    return None if value < 0 else value


def _fmt_minutes(minutes):
    minutes = int(round(minutes))
    if minutes <= 0:
        return None
    if minutes >= 6000:          # >100h means our estimate is meaningless
        return None
    if minutes < 60:
        return "%dm" % minutes
    return "%dh%02dm" % (minutes // 60, minutes % 60)


def _interpolate_curve(curve, voltage):
    """Piecewise-linear lookup on a (voltage, soc) curve ordered high -> low."""
    if voltage >= curve[0][0]:
        return 100.0
    if voltage <= curve[-1][0]:
        return 0.0
    for i in range(len(curve) - 1):
        v_hi, s_hi = curve[i]
        v_lo, s_lo = curve[i + 1]
        if v_lo <= voltage <= v_hi:
            span = v_hi - v_lo
            if span <= 0:
                return s_lo
            frac = (voltage - v_lo) / span
            return s_lo + frac * (s_hi - s_lo)
    return 0.0


class UPSError(Exception):
    """Raised when a backend cannot talk to its chip."""


# ---------------------------------------------------------------------------
# Backends
# ---------------------------------------------------------------------------

class Backend:
    """Base class. ``sample()`` returns a dict with whatever the chip knows:

        voltage  : pack volts (float)          - always present
        current  : amps, POSITIVE = charging   - None if not measurable
        soc      : 0..100 from a fuel gauge    - None if we must estimate it
        charging : True/False                  - None if not directly known
    """

    name = "generic"
    reports_soc = False
    reports_current = False

    def __init__(self, bus, address, options):
        self.bus = bus
        self.address = address
        self.options = options

    # -- byte-order-correct primitives ------------------------------------
    def _rd_u16(self, reg):
        return _swap16(self.bus.read_word_data(self.address, reg))

    def _wr_u16(self, reg, value):
        self.bus.write_word_data(self.address, reg, _swap16(value))

    def _rd_s16(self, reg):
        return _to_signed16(self._rd_u16(reg))

    def _rd_u8(self, reg):
        return self.bus.read_byte_data(self.address, reg)

    def _wr_u8(self, reg, value):
        self.bus.write_byte_data(self.address, reg, value & 0xFF)

    def setup(self):
        pass

    def sample(self):
        raise NotImplementedError

    def teardown(self):
        pass


class MAX17040Backend(Backend):
    """MAX17040/17041/17048/17049 fuel gauge - Geekworm X1200, UPS-Lite, etc.

    The VCELL LSB is 1.25mV/16 == 78.125uV for the 17040 family and exactly
    78.125uV for the 17048 family, so one formula covers both.
    """

    name = "max170xx"
    reports_soc = True

    def __init__(self, bus, address, options, gpio_pin=None):
        super().__init__(bus, address, options)
        self.gpio_pin = gpio_pin
        self._gpio_active_high = bool(options.get("charging_gpio_active_high", True))

    def setup(self):
        # QuickStart: MODE <- 0x4000. The old code wrote 0x4000 through
        # write_word_data without swapping, which put 0x0040 on the wire and
        # therefore never actually triggered a quick start.
        try:
            self._wr_u16(MAX_REG_MODE, 0x4000)
            time.sleep(0.5)          # datasheet: first valid SOC after ~500ms
            logging.info("%s MAX170xx quick-start issued", LOG)
        except Exception as exc:
            logging.warning("%s MAX170xx quick-start failed: %s", LOG, exc)

        # CONFIG low byte bits 4:0 = ATHD; alert fires at (32 - ATHD) percent.
        try:
            threshold = _clamp(int(self.options.get("alert_threshold", 10)), 1, 31)
            athd = 32 - threshold
            config = self._rd_u16(MAX_REG_CONFIG)
            config = (config & 0xFFE0) | (athd & 0x1F)
            self._wr_u16(MAX_REG_CONFIG, config)
            logging.debug("%s MAX170xx alert threshold set to %d%%", LOG, threshold)
        except Exception as exc:
            logging.warning("%s MAX170xx alert threshold failed: %s", LOG, exc)

        if self.gpio_pin is not None and GPIO is not None:
            try:
                GPIO.setwarnings(False)
                GPIO.setmode(GPIO.BCM)
                GPIO.setup(self.gpio_pin, GPIO.IN)
                logging.info("%s charging detection on BCM GPIO %d", LOG, self.gpio_pin)
            except Exception as exc:
                logging.warning("%s GPIO %s setup failed: %s", LOG, self.gpio_pin, exc)
                self.gpio_pin = None

    def sample(self):
        voltage = self._rd_u16(MAX_REG_VCELL) * 78.125e-6
        soc = _clamp(self._rd_u16(MAX_REG_SOC) / 256.0, 0.0, 100.0)

        charging = None
        if self.gpio_pin is not None and GPIO is not None:
            try:
                level = GPIO.input(self.gpio_pin) == GPIO.HIGH
                charging = level if self._gpio_active_high else (not level)
            except Exception:
                charging = None

        return {"voltage": voltage, "current": None, "soc": soc, "charging": charging}

    def teardown(self):
        if self.gpio_pin is not None and GPIO is not None:
            try:
                GPIO.cleanup(self.gpio_pin)
            except Exception:
                pass


class INA219Backend(Backend):
    """INA219 shunt/bus monitor - Waveshare, Seengreat, SB Components, EP-0136.

    Current is derived from the SHUNT VOLTAGE register rather than the CURRENT
    register. The current register reads zero until the calibration register is
    programmed, and a load spike can silently reset calibration back to zero at
    any time; the shunt register has no such dependency.
    """

    name = "ina219"
    reports_current = True

    def __init__(self, bus, address, options):
        super().__init__(bus, address, options)
        self.shunt_ohms = float(options.get("shunt_ohms", 0.1)) or 0.1
        self.sign = -1.0 if options.get("invert_current", False) else 1.0

    def setup(self):
        self._wr_u16(INA_REG_CONFIG, INA_CONFIG_VALUE)

        # Programme calibration too, so the CURRENT/POWER registers work for
        # anything else on the system that reads this chip.
        current_lsb = 0.0001                       # 100uA per bit
        cal = int(0.04096 / (current_lsb * self.shunt_ohms))
        while cal > 0xFFFE:
            current_lsb *= 2
            cal = int(0.04096 / (current_lsb * self.shunt_ohms))
        try:
            self._wr_u16(INA_REG_CALIB, max(cal, 1))
        except Exception as exc:
            logging.debug("%s INA219 calibration write failed: %s", LOG, exc)

        logging.info("%s INA219 at 0x%02X configured (shunt %.3f ohm)",
                     LOG, self.address, self.shunt_ohms)

    def sample(self):
        raw_bus = self._rd_u16(INA_REG_BUS_V)
        # Bits 15:3 hold the value; bit 1 = CNVR, bit 0 = OVF. LSB is 4mV.
        voltage = (raw_bus >> 3) * 0.004

        # Shunt LSB is 10uV; I = Vshunt / Rshunt.
        shunt_v = self._rd_s16(INA_REG_SHUNT_V) * 1e-5
        current = (shunt_v / self.shunt_ohms) * self.sign

        return {"voltage": voltage, "current": current, "soc": None, "charging": None}


class PiSugar2Backend(Backend):
    """PiSugar 2 (IP5209) at 0x75. Voltage lives at 0xA2/0xA3, NOT 0x22/0x23 -
    those belong to the PiSugar 3, which sits at a completely different
    address."""

    name = "pisugar2"
    VOLT_LOW, VOLT_HIGH = 0xA2, 0xA3
    CHARGE_REG, CHARGE_BIT = 0x55, 0x10

    def sample(self):
        low = self._rd_u8(self.VOLT_LOW)
        high = self._rd_u8(self.VOLT_HIGH)
        if high & 0x20:
            low = (~low) & 0xFF
            high = (~high) & 0x1F
            millivolts = 2600.0 - (((high << 8) + low) + 1) * 0.26855
        else:
            millivolts = 2600.0 + (((high & 0x1F) << 8) + low) * 0.26855

        charging = None
        try:
            charging = bool(self._rd_u8(self.CHARGE_REG) & self.CHARGE_BIT)
        except Exception:
            pass

        return {"voltage": millivolts / 1000.0, "current": None,
                "soc": None, "charging": charging}


class PiSugar2ProBackend(PiSugar2Backend):
    """PiSugar 2 Pro (IP5312), also at 0x75 but with a different register map."""

    name = "pisugar2_pro"
    VOLT_LOW, VOLT_HIGH = 0x64, 0x65
    CHARGE_REG, CHARGE_BIT = 0x58, 0x10

    def sample(self):
        low = self._rd_u8(self.VOLT_LOW)
        high = self._rd_u8(self.VOLT_HIGH)
        millivolts = (((high & 0x1F) << 8) + low) * 0.26855 + 2600.0

        charging = None
        try:
            charging = bool(self._rd_u8(self.CHARGE_REG) & self.CHARGE_BIT)
        except Exception:
            pass

        return {"voltage": millivolts / 1000.0, "current": None,
                "soc": None, "charging": charging}


class PiSugar3Backend(Backend):
    """PiSugar 3 / 3 Plus at 0x57."""

    name = "pisugar3"

    def sample(self):
        high = self._rd_u8(0x22)
        low = self._rd_u8(0x23)
        voltage = ((high << 8) | low) / 1000.0

        charging = None
        try:
            charging = bool(self._rd_u8(0x02) & (1 << 7))
        except Exception:
            pass

        return {"voltage": voltage, "current": None, "soc": None, "charging": charging}


# ---------------------------------------------------------------------------
# Estimation helpers
# ---------------------------------------------------------------------------

class ChargeDetector:
    """Decides charging vs discharging with hysteresis so noise around zero
    cannot make the icon flicker every refresh."""

    def __init__(self, threshold_ma=30.0):
        self.threshold = threshold_ma / 1000.0
        self.state = False
        self._voltage_ema = None
        self._last_trend_check = 0.0
        self._trend_reference = None

    def update(self, voltage, current, hint):
        # A backend that knows for sure always wins.
        if hint is not None:
            self.state = bool(hint)
            return self.state

        if current is not None:
            if current > self.threshold:
                self.state = True
            elif current < -self.threshold:
                self.state = False
            # inside the deadband: keep whatever we had
            return self.state

        # No current sensor and no status pin: fall back to voltage trend.
        now = time.monotonic()
        if self._voltage_ema is None:
            self._voltage_ema = voltage
            self._trend_reference = voltage
            self._last_trend_check = now
        else:
            self._voltage_ema += 0.2 * (voltage - self._voltage_ema)

        if now - self._last_trend_check >= 120:
            delta = self._voltage_ema - self._trend_reference
            if delta > 0.008:
                self.state = True
            elif delta < -0.008:
                self.state = False
            self._trend_reference = self._voltage_ema
            self._last_trend_check = now

        return self.state


class SocEstimator:
    """Voltage-based state of charge with IR compensation and smoothing.

    Terminal voltage sags under load and is inflated while charging, so the raw
    reading is corrected back towards open-circuit voltage before the curve
    lookup. Without this a pack reads ~15% high the moment you plug it in.
    """

    def __init__(self, internal_resistance=0.12, smoothing=0.25):
        self.internal_resistance = max(0.0, float(internal_resistance))
        self.smoothing = _clamp(float(smoothing), 0.01, 1.0)
        self.value = None

    def update(self, cell_voltage, cell_current):
        ocv = cell_voltage
        if cell_current is not None and self.internal_resistance > 0:
            ocv = cell_voltage - (cell_current * self.internal_resistance)

        raw = _interpolate_curve(LIION_OCV_CURVE, ocv)
        if self.value is None:
            self.value = raw
        else:
            self.value += self.smoothing * (raw - self.value)
        return _clamp(self.value, 0.0, 100.0)


class CycleCounter:
    """Counts real charge cycles: one cycle per battery_mah of cumulative
    discharge, rather than counting 'reached 100%' events (which inflates the
    number every time you top the pack up from 90%)."""

    # Ignore gaps longer than this: they mean polling stalled (suspend, a hung
    # bus, a long clock stretch) and integrating across them invents charge
    # that was never actually drawn.
    MAX_GAP_SECONDS = 300.0

    def __init__(self, capacity_mah, discharged_mah=0.0, cycles=0):
        self.capacity_mah = max(1.0, float(capacity_mah))
        self.discharged_mah = float(discharged_mah)
        self.cycles = int(cycles)
        self._last_time = None

    def update(self, current_a):
        now = time.monotonic()
        previous, self._last_time = self._last_time, now
        if previous is None or current_a is None or current_a >= 0:
            return

        elapsed = now - previous
        if elapsed <= 0 or elapsed > self.MAX_GAP_SECONDS:
            return

        self.discharged_mah += abs(current_a) * 1000.0 * (elapsed / 3600.0)
        while self.discharged_mah >= self.capacity_mah:
            self.discharged_mah -= self.capacity_mah
            self.cycles += 1


# ---------------------------------------------------------------------------
# Device manager
# ---------------------------------------------------------------------------

class MadHatterUPS:
    def __init__(self, options):
        if SMBus is None:
            raise UPSError("no smbus library available (%s); "
                           "try: sudo apt install python3-smbus2" % _SMBUS_IMPORT_ERROR)

        self.options = options
        self.bus_number = int(options.get("i2c_bus", 1))
        self.bus = SMBus(self.bus_number)
        self.backend = None

        self.cells = 1
        self._cells_option = options.get("battery_cells", "auto")

        self.charge_detector = ChargeDetector(
            float(options.get("charging_threshold_ma", 30)))
        self.soc_estimator = SocEstimator(
            float(options.get("internal_resistance", 0.12)),
            float(options.get("soc_smoothing", 0.25)))
        self.cycle_counter = CycleCounter(options.get("battery_mah", 2000))

        self.consecutive_errors = 0
        self.total_errors = 0

        self._select_backend()

    # -- detection ---------------------------------------------------------
    def _probe(self, address):
        try:
            self.bus.read_byte(address)
            return True
        except Exception:
            return False

    def _scan(self):
        candidates = [MAX_ADDR, PISUGAR3_ADDR, PISUGAR2_ADDR] + list(INA_ADDRS)
        found = [addr for addr in candidates if self._probe(addr)]
        if found:
            logging.info("%s I2C devices found: %s",
                         LOG, ", ".join("0x%02X" % a for a in found))
        return found

    def _find_ina(self, found):
        configured = _as_optional_int(self.options.get("i2c_address"))
        if configured is not None and configured in found:
            return configured
        for addr in INA_ADDRS:
            if addr in found:
                return addr
        return None

    def _select_backend(self):
        requested = str(self.options.get("ups_type", "auto")).strip().lower()
        found = self._scan()

        aliases = {
            "x1200": "max170xx", "ups_lite": "max170xx", "upslite": "max170xx",
            "max17040": "max170xx", "max17048": "max170xx",
            "ina219_generic": "ina219", "ina": "ina219", "waveshare": "ina219",
            "seengreat": "ina219", "ep-0136": "ina219", "ep0136": "ina219",
            "sbcomponents": "ina219",
            "pisugar": "pisugar2", "pisugar2pro": "pisugar2_pro",
        }
        requested = aliases.get(requested, requested)

        if requested == "x750" or requested == "ip5310":
            logging.warning("%s ups_type 'x750' has no verified register map and "
                            "previously reused PiSugar registers, which is wrong. "
                            "Falling back to auto-detection.", LOG)
            requested = "auto"

        gpio_pin = _as_optional_int(self.options.get("charging_gpio"))

        def build_max():
            pin = gpio_pin
            if pin is None:
                pin = DEFAULT_CHARGING_GPIOS.get(
                    str(self.options.get("ups_type", "")).strip().lower())
                if pin is not None:
                    logging.info("%s using default charging GPIO %d", LOG, pin)
            return MAX17040Backend(self.bus, MAX_ADDR, self.options, pin)

        builders = {
            "max170xx": (MAX_ADDR, build_max),
            "pisugar3": (PISUGAR3_ADDR,
                         lambda: PiSugar3Backend(self.bus, PISUGAR3_ADDR, self.options)),
            "pisugar2": (PISUGAR2_ADDR,
                         lambda: PiSugar2Backend(self.bus, PISUGAR2_ADDR, self.options)),
            "pisugar2_pro": (PISUGAR2_ADDR,
                             lambda: PiSugar2ProBackend(self.bus, PISUGAR2_ADDR, self.options)),
        }

        if requested != "auto":
            if requested == "ina219":
                address = self._find_ina(found)
                if address is None:
                    address = _as_optional_int(self.options.get("i2c_address")) or 0x40
                    logging.warning("%s no INA219 responded; forcing 0x%02X",
                                    LOG, address)
                self.backend = INA219Backend(self.bus, address, self.options)
            elif requested in builders:
                _, builder = builders[requested]
                self.backend = builder()
            else:
                raise UPSError("unsupported ups_type: %s" % requested)
        else:
            if MAX_ADDR in found:
                self.backend = build_max()
            elif PISUGAR3_ADDR in found:
                self.backend = PiSugar3Backend(self.bus, PISUGAR3_ADDR, self.options)
            else:
                ina = self._find_ina(found)
                if ina is not None:
                    self.backend = INA219Backend(self.bus, ina, self.options)
                elif PISUGAR2_ADDR in found:
                    self.backend = PiSugar2Backend(self.bus, PISUGAR2_ADDR, self.options)
                else:
                    raise UPSError("no supported UPS found on i2c-%d" % self.bus_number)

        self.backend.setup()
        logging.info("%s backend '%s' at 0x%02X",
                     LOG, self.backend.name, self.backend.address)

    # -- reading -----------------------------------------------------------
    def _read_raw(self, retries=3):
        last_exc = None
        for attempt in range(retries):
            try:
                data = self.backend.sample()
                self.consecutive_errors = 0
                return data
            except Exception as exc:
                last_exc = exc
                if attempt < retries - 1:
                    time.sleep(0.05)
        self.consecutive_errors += 1
        self.total_errors += 1
        raise UPSError("i2c read failed: %s" % last_exc)

    def _resolve_cells(self, voltage):
        if self.cells != 1:
            return
        option = self._cells_option
        if isinstance(option, int) and option > 0:
            self.cells = option
            return
        if isinstance(option, str) and option.strip().isdigit():
            self.cells = max(1, int(option.strip()))
            return
        # auto: infer series count from the resting pack voltage
        if voltage > 12.6:
            self.cells = 4
        elif voltage > 8.6:
            self.cells = 3
        elif voltage > 4.5:
            self.cells = 2
        else:
            self.cells = 1
        if self.cells > 1:
            logging.info("%s detected %dS pack (%.2fV)", LOG, self.cells, voltage)

    def read(self):
        """Returns a normalised reading dict, or raises UPSError."""
        raw = self._read_raw()
        voltage = float(raw.get("voltage") or 0.0)
        self._resolve_cells(voltage)

        current = raw.get("current")
        charging = self.charge_detector.update(voltage, current, raw.get("charging"))

        if raw.get("soc") is not None:
            soc = _clamp(float(raw["soc"]), 0.0, 100.0)
        else:
            cell_v = voltage / self.cells
            cell_i = current  # series pack: same current through every cell
            soc = self.soc_estimator.update(cell_v, cell_i)

        self.cycle_counter.update(current)

        return {
            "voltage": voltage,
            "current": current,
            "soc": soc,
            "charging": charging,
            "cells": self.cells,
            "backend": self.backend.name,
            "errors": self.total_errors,
            "cycles": self.cycle_counter.cycles,
        }

    def close(self):
        try:
            if self.backend:
                self.backend.teardown()
        except Exception:
            pass
        try:
            self.bus.close()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Plugin
# ---------------------------------------------------------------------------

class MadHatter(plugins.Plugin):
    __name__ = "mad_hatter"
    __author__ = "AlienMajik (with community enhancements)"
    __version__ = "2.0.1"
    __license__ = "GPL3"
    __description__ = ("Universal UPS plugin: MAX170xx / INA219 / PiSugar, "
                       "with real current sensing, IR-compensated SOC, "
                       "background polling and safe shutdown.")

    __defaults__ = {
        "enabled": True,
        # display
        "show_voltage": False,
        "show_time_estimate": True,
        "show_icon": True,
        "use_emoji": False,
        "label": "UPS",
        "ui_position_x": -80,
        "ui_position_y": 0,
        "ui_font": "medium",
        # shutdown
        "shutdown_enabled": False,
        "shutdown_threshold": 5,
        "critical_threshold": 2,
        "warning_threshold": 15,
        "shutdown_grace": 3,
        "shutdown_grace_period": 30,
        # battery / hardware
        "battery_mah": 2000,
        "avg_current_ma": 200,
        "battery_cells": "auto",
        "internal_resistance": 0.12,
        "soc_smoothing": 0.25,
        "shunt_ohms": 0.1,
        "invert_current": False,
        "charging_threshold_ma": 30,
        "charging_gpio": -1,
        "charging_gpio_active_high": True,
        "alert_threshold": 10,
        "ups_type": "auto",
        "i2c_bus": 1,
        "i2c_address": -1,
        # behaviour
        "poll_interval": 10,
        "debug_mode": False,
    }

    def __init__(self):
        self.ups = None
        self.options = dict(self.__defaults__)
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread = None
        self._reading = None
        self._status_text = "..."
        self._init_error = None
        self._next_init_retry = 0.0
        self._low_since = None
        self._low_polls = 0
        self._last_warning_log = 0.0
        self._last_state_save = 0.0
        self._ui_ready = False
        self._ui = None

    # -- option access -----------------------------------------------------
    def _opt(self, key, default=None):
        value = self.options.get(key, self.__defaults__.get(key, default))
        return default if value is None else value

    def _opt_float(self, key, default=0.0):
        try:
            return float(self._opt(key, default))
        except (TypeError, ValueError):
            return float(default)

    def _opt_int(self, key, default=0):
        try:
            return int(float(self._opt(key, default)))
        except (TypeError, ValueError):
            return int(default)

    # -- persistence -------------------------------------------------------
    def _load_state(self):
        state = {}
        try:
            if os.path.exists(STATE_FILE):
                with open(STATE_FILE, "r") as handle:
                    state = json.load(handle) or {}
            elif os.path.exists(LEGACY_CYCLE_FILE):
                with open(LEGACY_CYCLE_FILE, "r") as handle:
                    state = {"cycles": int((handle.read().strip() or "0"))}
                logging.info("%s migrated legacy cycle count", LOG)
        except Exception as exc:
            logging.debug("%s state load failed: %s", LOG, exc)
        return state

    def _save_state(self):
        if not self.ups:
            return
        payload = {
            "cycles": self.ups.cycle_counter.cycles,
            "discharged_mah": round(self.ups.cycle_counter.discharged_mah, 3),
            "saved_at": int(time.time()),
        }
        try:
            directory = os.path.dirname(STATE_FILE) or "."
            handle = tempfile.NamedTemporaryFile(
                "w", dir=directory, prefix=".mad_hatter.", delete=False)
            with handle:
                json.dump(payload, handle)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(handle.name, STATE_FILE)
        except Exception as exc:
            logging.debug("%s state save failed: %s", LOG, exc)

    # -- lifecycle ---------------------------------------------------------
    def on_loaded(self):
        # pwnagotchi 2.9.5.x assigns `plugin.options = config['main']['plugins'][name]`
        # outright - it does NOT merge __defaults__ for you. Any plugin that
        # indexes self.options[...] directly will KeyError on every key the
        # user did not spell out in config.toml. Merge them ourselves.
        user_options = self.options if isinstance(self.options, dict) else {}
        merged = dict(self.__defaults__)
        merged.update(user_options)
        self.options = merged

        self._stop.clear()
        self._thread = threading.Thread(target=self._poll_loop,
                                        name="mad_hatter", daemon=True)
        self._thread.start()
        logging.info("%s plugin v%s loaded", LOG, self.__version__)

    def _try_init(self):
        try:
            self.ups = MadHatterUPS(self.options)
        except Exception as exc:
            self.ups = None
            self._init_error = str(exc)
            self._next_init_retry = time.monotonic() + 60
            with self._lock:
                self._status_text = "NO UPS"
            logging.warning("%s init failed (retry in 60s): %s", LOG, exc)
            return False

        state = self._load_state()
        self.ups.cycle_counter.cycles = int(state.get("cycles", 0) or 0)
        self.ups.cycle_counter.discharged_mah = float(state.get("discharged_mah", 0) or 0)
        self._init_error = None
        return True

    def _publish(self, text):
        """Write straight into the view instead of waiting for on_ui_update.

        pwnagotchi 2.9.5.x ships ui.fps = 0.0 by default, so there is no
        periodic refresh thread and 'ui_update' only fires when some *other*
        element has already changed. Setting the value here means our reading
        is current the moment anything triggers a redraw. State.set() ignores
        writes that do not change the value, so this cannot cause extra
        redraws on its own.
        """
        with self._lock:
            changed = text != self._status_text
            self._status_text = text
            ui = self._ui
        if changed and ui is not None:
            try:
                ui.set("mad_hatter", text)
            except Exception:
                pass

    def _poll_loop(self):
        while not self._stop.is_set():
            interval = max(2, self._opt_int("poll_interval", 10))

            if self.ups is None:
                if time.monotonic() < self._next_init_retry or not self._try_init():
                    self._stop.wait(min(interval, 5))
                    continue
                # Init just succeeded: fall through and take a reading now
                # rather than leaving the placeholder on screen for a whole
                # poll_interval.

            try:
                reading = self.ups.read()
                with self._lock:
                    self._reading = reading
                self._publish(self._render(reading))
                if self._opt("debug_mode"):
                    logging.debug("%s %.2fV %.1f%% %s %s", LOG,
                                  reading["voltage"], reading["soc"],
                                  "chg" if reading["charging"] else "dis",
                                  "%.0fmA" % (reading["current"] * 1000)
                                  if reading["current"] is not None else "n/a")
                self._check_shutdown(reading)
            except UPSError as exc:
                if self.ups and self.ups.consecutive_errors > 5:
                    self._publish("UPS ERR")
                logging.debug("%s poll failed: %s", LOG, exc)
            except Exception as exc:
                logging.error("%s unexpected poll error: %s", LOG, exc)

            now = time.monotonic()
            if now - self._last_state_save > 300:
                self._last_state_save = now
                self._save_state()

            self._stop.wait(interval)

    # -- rendering ---------------------------------------------------------
    def _icons(self, soc, charging):
        if not self._opt("show_icon", True):
            return "", ""
        if self._opt("use_emoji", False):
            # Only enable this if your display font actually has these glyphs;
            # the stock DejaVu fonts on most e-ink screens render them as boxes.
            return ("\U0001FAAB" if soc < 20 else "\U0001F50B",
                    "\u26A1" if charging else "")
        return "", "+" if charging else ""

    def _estimate_minutes(self, reading):
        soc = reading["soc"]
        capacity = self._opt_float("battery_mah", 2000)
        if capacity <= 0 or soc <= 0 or soc >= 100:
            return None

        current_ma = None
        if reading["current"] is not None:
            current_ma = abs(reading["current"]) * 1000.0
            if current_ma < self._opt_float("charging_threshold_ma", 30):
                current_ma = None

        if reading["charging"]:
            if current_ma is None:
                return None                     # no honest guess available
            remaining = (100.0 - soc) / 100.0 * capacity
            # charge acceptance tapers off near the top; rough CV-phase fudge
            taper = 1.0 if soc < 80 else 1.6
            return remaining / current_ma * 60.0 * taper

        draw = current_ma if current_ma else self._opt_float("avg_current_ma", 200)
        if draw <= 0:
            return None
        return soc / 100.0 * capacity / draw * 60.0

    def _render(self, reading):
        soc = reading["soc"]
        charging = reading["charging"]
        battery_icon, charge_icon = self._icons(soc, charging)

        parts = []
        if self._opt("show_voltage", False):
            parts.append("%.2fV" % reading["voltage"])
        parts.append("%s%d%%%s" % (battery_icon, int(round(soc)), charge_icon))

        if self._opt("show_time_estimate", True):
            minutes = self._fmt_estimate(reading)
            if minutes:
                parts.append(minutes)

        if self._opt("debug_mode", False):
            parts.append("C%d" % reading["cycles"])
            if reading["current"] is not None:
                parts.append("%dmA" % int(reading["current"] * 1000))
            if reading["errors"]:
                parts.append("E%d" % reading["errors"])

        return " ".join(parts)

    def _fmt_estimate(self, reading):
        minutes = self._estimate_minutes(reading)
        text = _fmt_minutes(minutes) if minutes else None
        if not text:
            return None
        return ("^" if reading["charging"] else "~") + text

    # -- shutdown ----------------------------------------------------------
    def _check_shutdown(self, reading):
        if not self._opt("shutdown_enabled", False):
            self._low_since = None
            self._low_polls = 0
            return

        soc = reading["soc"]
        discharging = not reading["charging"]
        warning = self._opt_float("warning_threshold", 15)
        threshold = self._opt_float("shutdown_threshold", 5)
        critical = self._opt_float("critical_threshold", 2)

        now = time.monotonic()

        if soc < warning and discharging and now - self._last_warning_log > 60:
            self._last_warning_log = now
            logging.warning("%s low battery: %.1f%% (%.2fV)",
                            LOG, soc, reading["voltage"])

        if not (discharging and soc < threshold):
            self._low_since = None
            self._low_polls = 0
            return

        if soc < critical:
            logging.critical("%s battery critical (%.1f%%) - shutting down now",
                             LOG, soc)
            self._do_shutdown()
            return

        if self._low_since is None:
            self._low_since = now
            self._low_polls = 0
        self._low_polls += 1

        need_polls = max(1, self._opt_int("shutdown_grace", 3))
        need_seconds = max(0, self._opt_int("shutdown_grace_period", 30))

        if self._low_polls >= need_polls and (now - self._low_since) >= need_seconds:
            logging.critical("%s battery at %.1f%% for %ds - safe shutdown",
                             LOG, soc, int(now - self._low_since))
            self._do_shutdown()

    def _do_shutdown(self):
        with self._lock:
            self._status_text = "SHUTDOWN"
        self._save_state()
        try:
            pwnagotchi.shutdown()
        except Exception as exc:
            logging.error("%s pwnagotchi.shutdown() failed: %s", LOG, exc)
            os.system("sync && shutdown -h now")

    # -- UI ----------------------------------------------------------------
    def on_ui_setup(self, ui):
        try:
            configured_x = self._opt_int("ui_position_x", -80)
            # Negative x means "this many pixels in from the right edge", which
            # keeps the element on screen on 128px and 250px displays alike.
            pos_x = ui.width() + configured_x if configured_x < 0 else configured_x
            pos_x = _clamp(pos_x, 0, max(0, ui.width() - 10))
            pos = (pos_x, self._opt_int("ui_position_y", 0))

            font_name = str(self._opt("ui_font", "medium")).lower()
            text_font = {"small": fonts.Small, "medium": fonts.Medium,
                         "bold": fonts.Bold}.get(font_name, fonts.Medium)

            # LabeledValue.draw() only omits the label when it is None; an
            # empty string still costs label_spacing pixels of indent.
            label = str(self._opt("label", "UPS") or "").strip() or None

            # Seed with whatever the poll thread already has. The thread
            # normally produces its first reading before ui_setup arrives, and
            # _publish() only writes on change - so starting from a placeholder
            # would leave "..." on screen until the reading happened to move.
            with self._lock:
                initial = self._status_text

            ui.add_element("mad_hatter", LabeledValue(
                color=BLACK,
                label=label,
                value=initial,
                position=pos,
                label_font=fonts.Bold,
                text_font=text_font,
            ))
            self._ui = ui
            self._ui_ready = True
        except Exception as exc:
            logging.error("%s UI setup failed: %s", LOG, exc)

    def on_ui_update(self, ui):
        # Deliberately does no I/O: the display thread must never block on I2C.
        if not self._ui_ready:
            return
        with self._lock:
            text = self._status_text
        try:
            ui.set("mad_hatter", text)
        except Exception:
            pass

    def on_unload(self, ui):
        self._stop.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)

        self._save_state()

        if self.ups:
            self.ups.close()
            self.ups = None

        if self._ui_ready:
            try:
                with ui._lock:
                    ui.remove_element("mad_hatter")
            except Exception:
                try:
                    ui.remove_element("mad_hatter")
                except Exception:
                    pass
            self._ui_ready = False
        self._ui = None

        logging.info("%s unloaded", LOG)

    # -- web ---------------------------------------------------------------
    def on_webhook(self, path, request):
        from flask import jsonify, abort

        with self._lock:
            reading = dict(self._reading) if self._reading else None
            text = self._status_text

        if path in ("status", "json"):
            return jsonify({
                "ok": reading is not None,
                "display": text,
                "error": self._init_error,
                "reading": reading,
            })
        if path is None or path == "/":
            body = "<h1>MadHatter</h1><pre>%s</pre>" % (
                json.dumps(reading, indent=2) if reading else self._init_error)
            return body
        abort(404)
