#!/usr/bin/env python3
"""
mad_hatter_doctor.py - hardware diagnostic for the MadHatter pwnagotchi plugin

Runs standalone. It does NOT import pwnagotchi, so it still works when the
daemon refuses to start. It measures what can actually be measured, tells you
plainly what it could not determine, and prints a config.toml block for you to
review before pasting.

    sudo python3 mad_hatter_doctor.py                 # quick scan (~15s)
    sudo python3 mad_hatter_doctor.py --watch 300     # 5 min: polarity + IR
    sudo python3 mad_hatter_doctor.py --interactive   # asks you to plug/unplug
    sudo python3 mad_hatter_doctor.py --json          # machine readable

Nothing is written to your config. The only device writes are the INA219
CONFIG/CALIBRATION registers, which are required to take a reading and are
what the plugin sets anyway. PiSugar devices are treated as strictly
read-only: the vendor warns that stray writes to 0x75 can damage the board.
"""

import argparse
import json
import os
import re
import statistics
import sys
import time

VERSION = "1.3.0"

# --------------------------------------------------------------------------
# Output helpers
# --------------------------------------------------------------------------

_TTY = sys.stdout.isatty()


def _c(code, text):
    return "\033[%sm%s\033[0m" % (code, text) if _TTY else text


def head(text):
    print("\n" + _c("1;36", text))
    print(_c("36", "-" * len(text)))


def ok(text):
    print("  %s %s" % (_c("32", "[ OK ]"), text))


def warn(text):
    print("  %s %s" % (_c("33", "[WARN]"), text))


def bad(text):
    print("  %s %s" % (_c("31", "[FAIL]"), text))


def info(text):
    print("  %s %s" % (_c("34", "[INFO]"), text))


def note(text):
    print("         %s" % text)


FINDINGS = {}
PROBLEMS = []


# --------------------------------------------------------------------------
# Constants (kept in sync with the plugin)
# --------------------------------------------------------------------------

MAX_ADDR = 0x36
INA_ADDRS = (0x40, 0x41, 0x42, 0x43, 0x44, 0x45)
PISUGAR2_ADDR = 0x75
PISUGAR3_ADDR = 0x57

INA_REG_CONFIG, INA_REG_SHUNT, INA_REG_BUS, INA_REG_CALIB = 0x00, 0x01, 0x02, 0x05
INA_CONFIG_VALUE = 0x399F

RESERVED_GPIOS = {
    0: "HAT EEPROM ID_SD", 1: "HAT EEPROM ID_SC", 2: "I2C1 SDA", 3: "I2C1 SCL",
    7: "SPI0 CE1", 8: "SPI0 CE0", 9: "SPI0 MISO", 10: "SPI0 MOSI",
    11: "SPI0 SCLK", 14: "UART TX", 15: "UART RX",
}

DISPLAY_GPIOS = {
    "displayhatmini": {9: "D/C", 13: "backlight", 5: "button A", 6: "button B",
                       16: "button X", 24: "button Y", 17: "LED R", 27: "LED G",
                       22: "LED B"},
    "waveshare27inch": {17: "RST", 25: "DC", 24: "BUSY"},
    "waveshare29inch": {17: "RST", 25: "DC", 24: "BUSY"},
    "inky": {17: "RST", 22: "BUSY", 27: "DC"},
}

# Typical total system draw (mA) with pwnagotchi + a display running.
# Used only to tell a 0.1 ohm shunt from a 0.01 ohm one - they differ by 10x,
# so this does not need to be precise.
PI_DRAW_MA = {
    "zero 2": (150, 600), "zero": (90, 400), "3 model a": (300, 800),
    "3 model b": (350, 900), "4 model b": (450, 1200), "5 model": (600, 1600),
    "compute module": (300, 1000),
}
DEFAULT_DRAW_MA = (80, 1600)

LIION_FULL, LIFEPO4_FULL = 4.20, 3.65


# --------------------------------------------------------------------------
# Low level
# --------------------------------------------------------------------------

def swap16(v):
    v &= 0xFFFF
    return ((v & 0xFF) << 8) | (v >> 8)


def s16(v):
    v &= 0xFFFF
    return v - 0x10000 if v & 0x8000 else v


def open_bus(number):
    try:
        from smbus2 import SMBus
        return SMBus(number), "smbus2"
    except Exception:
        pass
    try:
        from smbus import SMBus
        return SMBus(number), "smbus"
    except Exception as exc:
        raise RuntimeError("no smbus library: %s" % exc)


# --------------------------------------------------------------------------
# Environment
# --------------------------------------------------------------------------

def pi_model():
    try:
        with open("/proc/device-tree/model", "rb") as fh:
            return fh.read().decode("utf-8", "replace").strip("\x00").strip()
    except Exception:
        return "unknown"


def expected_draw(model):
    low = model.lower()
    for key, rng in PI_DRAW_MA.items():
        if key in low:
            return rng
    return DEFAULT_DRAW_MA


def _flatten(node, prefix=""):
    flat = {}
    for key, value in node.items():
        full = prefix + str(key)
        if isinstance(value, dict):
            flat.update(_flatten(value, full + "."))
        else:
            flat[full] = value
    return flat


def _regex_fallback(text):
    """Section-aware scan used only when no TOML parser is available.

    A bare `type = "..."` is NEVER accepted: plenty of plugins define their own
    `type` key, and mistaking one for the display is how this tool previously
    declared a display's own pins free.
    """
    out = {"display": "", "custom_plugins": None, "madhatter": {}}
    section = ""
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1].strip()
            continue
        if "=" not in line:
            continue
        key, value = (p.strip() for p in line.split("=", 1))
        value = value.strip().strip('"').strip("'")
        full = "%s.%s" % (section, key) if section else key

        if full in ("ui.display.type", "main.ui.display.type"):
            out["display"] = value.lower()
        elif full in ("main.custom_plugins", "custom_plugins"):
            out["custom_plugins"] = value
        elif full.startswith("main.plugins.mad_hatter."):
            out["madhatter"][full.split(".")[-1]] = value
    return out


def read_pwn_config(path="/etc/pwnagotchi/config.toml"):
    out = {"path": None, "display": "", "custom_plugins": None,
           "madhatter": {}, "parser": None}
    if not os.path.exists(path):
        return out
    out["path"] = path

    data = None
    for name in ("tomllib", "toml", "tomlkit"):
        try:
            mod = __import__(name)
            if name == "tomllib":
                with open(path, "rb") as fh:
                    data = mod.load(fh)
            else:
                data = mod.load(path)
            out["parser"] = name
            break
        except Exception:
            data = None

    if data is not None:
        flat = _flatten(data)
        out["display"] = str(flat.get("ui.display.type", "")).lower()
        out["custom_plugins"] = flat.get("main.custom_plugins")
        for key, value in flat.items():
            if key.startswith("main.plugins.mad_hatter."):
                out["madhatter"][key.split(".")[-1]] = value
        return out

    try:
        out.update(_regex_fallback(open(path, "r", errors="replace").read()))
        out["parser"] = "regex (degraded)"
    except Exception:
        pass
    return out


def live_gpio_consumers():
    """Which GPIO lines the kernel currently reports as claimed, and by what.

    This is the authoritative check: it does not care whether we recognise the
    display's name. Returns {line: consumer} or None if it could not be read.
    """
    import subprocess
    try:
        out = subprocess.run(["gpioinfo"], capture_output=True, text=True,
                             timeout=8)
        text = out.stdout
    except Exception:
        return None
    if not text.strip():
        return None

    claimed = {}
    chip = ""
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("gpiochip"):
            chip = line
            continue
        # Only the main pinctrl chip carries BCM-numbered header pins.
        if "pinctrl" not in chip and "bcm" not in chip.lower() and chip:
            if "gpiochip0" not in chip and "gpiochip4" not in chip:
                continue
        m = re.search(r'line\s+(\d+):\s+"?([^"\s]+)"?\s+(.*)$', line)
        if not m:
            continue
        num, _name, rest = int(m.group(1)), m.group(2), m.group(3)
        if "unused" in rest:
            continue
        consumer = None
        quoted = re.findall(r'"([^"]*)"', rest)
        if quoted and quoted[0]:
            consumer = quoted[0]
        elif "[used]" in rest or "used" in rest:
            consumer = "(in use)"
        if consumer:
            claimed.setdefault(num, consumer)
    return claimed or None


def check_environment(args):
    head("1. Environment")
    model = pi_model()
    info("Board          : %s" % model)
    info("Python         : %s" % sys.version.split()[0])
    FINDINGS["model"] = model

    if os.geteuid() != 0:
        warn("Not running as root - I2C and GPIO probes may fail. Use sudo.")

    dev = "/dev/i2c-%d" % args.bus
    if os.path.exists(dev):
        ok("I2C bus        : %s present" % dev)
    else:
        bad("I2C bus        : %s missing - enable it with 'sudo raspi-config'" % dev)
        PROBLEMS.append("i2c disabled")

    try:
        _, lib = open_bus(args.bus)
        ok("SMBus library  : %s" % lib)
    except Exception as exc:
        bad("SMBus library  : %s" % exc)
        PROBLEMS.append("no smbus")

    try:
        import RPi.GPIO  # noqa: F401
        path = RPi.GPIO.__file__ or ""
        flavour = "rpi-lgpio shim" if "dist-packages/RPi/GPIO/" in path else "RPi.GPIO"
        ok("GPIO library   : %s" % flavour)
        FINDINGS["gpio_lib"] = flavour
    except Exception as exc:
        warn("GPIO library   : unavailable (%s) - GPIO charge detection unusable" % exc)
        FINDINGS["gpio_lib"] = None

    cfg = read_pwn_config()
    FINDINGS["display"] = cfg["display"]
    if cfg["path"]:
        ok("config.toml    : %s" % cfg["path"])
        note("display type   : %s" % (cfg["display"] or "unknown"))
        note("plugin dir     : %s" % (cfg["custom_plugins"] or "(default)"))
    else:
        warn("config.toml    : not found at /etc/pwnagotchi/config.toml")
    return cfg


# --------------------------------------------------------------------------
# I2C scan
# --------------------------------------------------------------------------

def scan(bus, args):
    head("2. I2C scan")
    candidates = [MAX_ADDR, PISUGAR3_ADDR, PISUGAR2_ADDR] + list(INA_ADDRS)
    found = []
    for addr in candidates:
        try:
            bus.read_byte(addr)
            found.append(addr)
        except Exception:
            pass

    if not found:
        bad("No known UPS chip responded on i2c-%d" % args.bus)
        note("Try 'sudo i2cdetect -y %d' to see the whole bus." % args.bus)
        note("If that is also empty, check the HAT is seated and powered.")
        PROBLEMS.append("no chip found")
        return None

    for addr in found:
        ok("0x%02X responds" % addr)

    if MAX_ADDR in found:
        kind, addr = "max170xx", MAX_ADDR
    elif PISUGAR3_ADDR in found:
        kind, addr = "pisugar3", PISUGAR3_ADDR
    else:
        ina = [a for a in INA_ADDRS if a in found]
        if ina:
            kind, addr = "ina219", ina[0]
            if len(ina) > 1:
                warn("Multiple INA219 addresses: %s - using 0x%02X"
                     % (", ".join("0x%02X" % a for a in ina), addr))
        elif PISUGAR2_ADDR in found:
            kind, addr = "pisugar2", PISUGAR2_ADDR
        else:
            return None

    info("Identified     : %s at 0x%02X" % (kind, addr))
    FINDINGS["chip"], FINDINGS["address"] = kind, addr
    return kind, addr


# --------------------------------------------------------------------------
# Sampling backends (read-only where it matters)
# --------------------------------------------------------------------------

class Sampler:
    def __init__(self, bus, kind, addr, shunt=0.1):
        self.bus, self.kind, self.addr, self.shunt = bus, kind, addr, shunt

    def _u16(self, reg):
        return swap16(self.bus.read_word_data(self.addr, reg))

    def setup(self):
        if self.kind == "ina219":
            self.bus.write_word_data(self.addr, INA_REG_CONFIG,
                                     swap16(INA_CONFIG_VALUE))
            self.bus.write_word_data(self.addr, INA_REG_CALIB, swap16(4096))
            time.sleep(0.05)
        elif self.kind == "max170xx":
            pass  # read-only here; the plugin does quick-start at runtime

    def sample(self):
        """-> (voltage, current_or_None). Current positive = into battery."""
        if self.kind == "ina219":
            v = (self._u16(INA_REG_BUS) >> 3) * 0.004
            i = (s16(self._u16(INA_REG_SHUNT)) * 1e-5) / self.shunt
            return v, i
        if self.kind == "max170xx":
            return self._u16(0x02) * 78.125e-6, None
        if self.kind == "pisugar3":
            hi = self.bus.read_byte_data(self.addr, 0x22)
            lo = self.bus.read_byte_data(self.addr, 0x23)
            return ((hi << 8) | lo) / 1000.0, None
        if self.kind == "pisugar2":
            lo = self.bus.read_byte_data(self.addr, 0xA2)
            hi = self.bus.read_byte_data(self.addr, 0xA3)
            if hi & 0x20:
                lo, hi = (~lo) & 0xFF, (~hi) & 0x1F
                mv = 2600.0 - (((hi << 8) + lo) + 1) * 0.26855
            else:
                mv = 2600.0 + (((hi & 0x1F) << 8) + lo) * 0.26855
            return mv / 1000.0, None
        raise RuntimeError("unknown chip")


# --------------------------------------------------------------------------
# Analysis
# --------------------------------------------------------------------------

def check_byte_order(bus, kind, addr):
    head("3. Byte order")
    if kind == "ina219":
        raw = bus.read_word_data(addr, INA_REG_BUS)
        swapped, plain = (swap16(raw) >> 3) * 0.004, (raw >> 3) * 0.004
    elif kind == "max170xx":
        raw = bus.read_word_data(addr, 0x02)
        swapped, plain = swap16(raw) * 78.125e-6, raw * 78.125e-6
    else:
        info("Not applicable for %s (byte registers)" % kind)
        return True

    info("byte-swapped   : %.3f V" % swapped)
    info("as-read        : %.3f V" % plain)
    if 2.0 < swapped < 17.0:
        ok("Swapped reading is the plausible one - matches the plugin's handling")
        return True
    if 2.0 < plain < 17.0:
        bad("UNSWAPPED looks correct - this board is unusual, please report it")
        PROBLEMS.append("unexpected byte order")
        return False
    bad("Neither interpretation is plausible - is a battery actually attached?")
    PROBLEMS.append("implausible voltage")
    return False


CHEMISTRIES = {
    # name       empty  nominal  full
    "li-ion":   (3.00,  3.70,    4.20),
    "lifepo4":  (2.50,  3.20,    3.65),
}


def analyse_pack(voltage):
    head("4. Battery pack")
    info("Pack voltage   : %.3f V" % voltage)

    # Enumerate every (cells, chemistry) pair this voltage could belong to.
    candidates = []
    for cells in (1, 2, 3, 4):
        for chem, (empty, nominal, full) in CHEMISTRIES.items():
            per_cell = voltage / cells
            if empty * 0.97 <= per_cell <= full * 1.02:
                # Prefer interpretations that put the pack in a normal working
                # band rather than pinned at an extreme.
                candidates.append((abs(per_cell - nominal), cells, chem, per_cell))
    candidates.sort()

    if not candidates:
        warn("%.3f V matches no common Li-ion or LiFePO4 pack." % voltage)
        note("Either the pack is deeply discharged, or this is a chemistry")
        note("the plugin does not model. Do not trust the percentage.")
        return None, None

    _, cells, chem, per_cell = candidates[0]
    FINDINGS["cells"], FINDINGS["chemistry"] = cells, chem

    # Cell count is nearly always unambiguous (the voltage bands have gaps).
    distinct_cells = {c[1] for c in candidates}
    if len(distinct_cells) == 1:
        ok("Series cells   : %dS  (%.3f V per cell)" % (cells, per_cell))
        if cells > 1:
            note("set battery_cells = %d" % cells)
    else:
        warn("Cell count ambiguous: could be %s"
             % " or ".join("%dS" % c for c in sorted(distinct_cells)))
        note("Best guess %dS. Set battery_cells = %d explicitly if you know." % (cells, cells))

    # Chemistry genuinely overlaps in the 3.0-3.65 V/cell region.
    same_cells = [c for c in candidates if c[1] == cells]
    if len({c[2] for c in same_cells}) > 1:
        warn("Chemistry AMBIGUOUS at %.3f V/cell." % per_cell)
        note("%.3f V is both a mid-charge LiFePO4 cell and a nearly-flat" % per_cell)
        note("Li-ion cell. A single reading cannot tell them apart.")
        note("To settle it: charge the pack fully and re-run. If it tops out")
        note("near 3.65 V/cell it is LiFePO4; near 4.20 V/cell it is Li-ion.")
        FINDINGS["chemistry"] = "ambiguous"
    elif chem == "lifepo4":
        bad("Chemistry      : LiFePO4 - the plugin's SOC curve is Li-ion.")
        note("Percentages will be badly wrong (LiFePO4 sits flat at ~3.2 V")
        note("for most of its capacity, where the Li-ion curve reads ~0%).")
        note("Ask and I will add a LiFePO4 curve; do not rely on % until then.")
        PROBLEMS.append("LiFePO4 pack with a Li-ion SOC curve")
    else:
        ok("Chemistry      : Li-ion / LiPo (matches the built-in curve)")
        if per_cell > CHEMISTRIES["li-ion"][2] + 0.05:
            warn("Cell voltage above %.2f V - overcharged, or cell count wrong."
                 % CHEMISTRIES["li-ion"][2])

    return cells, FINDINGS["chemistry"]


def infer_shunt(bus, addr, model):
    head("5. INA219 shunt resistor")

    # A single sample is easily dominated by a Wi-Fi transmit burst, so take a
    # spread and use the median.
    raws = []
    for _ in range(15):
        try:
            raws.append(s16(swap16(bus.read_word_data(addr, INA_REG_SHUNT))))
        except Exception:
            pass
        time.sleep(0.08)
    if not raws:
        bad("Could not read the shunt register.")
        return None

    raw = statistics.median(raws)
    shunt_mv = raw * 0.01
    spread_mv = (max(raws) - min(raws)) * 0.01
    info("Shunt voltage  : %.3f mV median of %d (spread %.2f mV)"
         % (shunt_mv, len(raws), spread_mv))

    if abs(raw) < 3:
        warn("Shunt drop is ~0 - no meaningful current is flowing.")
        note("Most likely the Pi is on USB power with the battery idle, or")
        note("this board senses current somewhere the INA219 cannot see.")
        note("Re-run on battery power. Leaving shunt_ohms at its default.")
        return None

    if spread_mv > abs(shunt_mv):
        warn("Reading is noisier than its own magnitude - treat with suspicion.")

    lo, hi = expected_draw(model)
    info("Expected draw  : %d-%d mA for this board" % (lo, hi))

    fits = []
    for candidate in (0.1, 0.01, 0.05, 0.002):
        ma = abs(shunt_mv / candidate)
        marker = ""
        if lo <= ma <= hi:
            fits.append(candidate)
            marker = "  <-- plausible"
        info("  shunt %.3f ohm -> %7.1f mA%s" % (candidate, ma, marker))

    if len(fits) == 1:
        ok("shunt_ohms = %s" % fits[0])
        note("Confirm with a USB power meter if the runtime estimates look off.")
        FINDINGS["shunt_ohms"] = fits[0]
        return fits[0]
    if not fits:
        warn("No candidate gives a believable current.")
        note("Measure actual draw with a USB meter, then pick the shunt that")
        note("matches. Most UPS HATs use 0.1; a few use 0.01.")
    else:
        warn("Ambiguous between: %s" % ", ".join(str(f) for f in fits))
        note("Compare against a USB power meter to choose.")
    return None


def watch(sampler, seconds, interactive):
    head("6. Polarity and internal resistance (%ds)" % seconds)

    if sampler.sample()[1] is None:
        info("This chip has no current sensor - nothing to measure here.")
        note("invert_current and internal_resistance do not apply.")
        return

    if interactive:
        print()
        input("  Make sure the charger is UNPLUGGED, then press Enter... ")

    samples = []
    start = time.time()
    last_print = 0
    while time.time() - start < seconds:
        try:
            v, i = sampler.sample()
            samples.append((time.time() - start, v, i))
        except Exception:
            pass
        now = time.time() - start
        if now - last_print >= 10:
            last_print = now
            if samples:
                _, v, i = samples[-1]
                sys.stdout.write("\r  %4ds  %.3f V  %+8.1f mA   " % (now, v, i * 1000))
                sys.stdout.flush()
        time.sleep(1.0)
    print()

    if len(samples) < 10:
        warn("Not enough samples collected.")
        return

    ts = [s[0] for s in samples]
    vs = [s[1] for s in samples]
    cs = [s[2] for s in samples]

    slope = _slope(ts, vs) * 3600.0            # V per hour
    mean_i = statistics.fmean(cs) * 1000.0     # mA
    info("Voltage trend  : %+.4f V/hour" % slope)
    info("Mean current   : %+.1f mA" % mean_i)

    # --- polarity -------------------------------------------------------
    if abs(mean_i) < 15:
        warn("Current too close to zero to judge polarity.")
    elif abs(slope) < 0.005:
        warn("Voltage too flat to judge polarity - run --watch longer,")
        note("or use --interactive which plugs/unplugs the charger for a")
        note("definitive answer.")
    else:
        charging_by_voltage = slope > 0
        charging_by_current = mean_i > 0
        if charging_by_voltage == charging_by_current:
            ok("Polarity correct - keep invert_current = false")
            FINDINGS["invert_current"] = False
        else:
            bad("POLARITY INVERTED: voltage is %s while current says %s"
                % ("rising" if charging_by_voltage else "falling",
                   "charging" if charging_by_current else "discharging"))
            note("set invert_current = true")
            FINDINGS["invert_current"] = True

    # --- internal resistance -------------------------------------------
    spread = (max(cs) - min(cs)) * 1000.0
    if spread < 60:
        info("Load varied by only %.0f mA - too steady to fit resistance." % spread)
        note("Keep the default internal_resistance = 0.12")
    else:
        # Current is positive-into-battery, so terminal V = OCV + I*R and the
        # resistance is the POSITIVE slope of V against I.
        r = _slope(cs, vs)
        cells = FINDINGS.get("cells", 1)
        per_cell = r / max(1, cells)
        info("Load swing     : %.0f mA" % spread)
        if 0.01 <= per_cell <= 1.5:
            ok("internal_resistance = %.3f  (per cell, from %d samples)"
               % (per_cell, len(samples)))
            FINDINGS["internal_resistance"] = round(per_cell, 3)
        else:
            warn("Fitted resistance %.3f ohm/cell is out of range - ignoring." % per_cell)
            note("Keep the default internal_resistance = 0.12")


def _slope(xs, ys):
    """Least-squares slope of y against x."""
    n = len(xs)
    mx, my = statistics.fmean(xs), statistics.fmean(ys)
    denom = sum((x - mx) ** 2 for x in xs)
    if denom == 0:
        return 0.0
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / denom


def check_gpio(cfg):
    head("7. GPIO")

    display = cfg.get("display", "")
    known_display = any(name in display for name in DISPLAY_GPIOS) if display else False

    owned = dict(RESERVED_GPIOS)
    for name, pins in DISPLAY_GPIOS.items():
        if display and name in display:
            for pin, what in pins.items():
                owned[pin] = "%s %s" % (name, what)

    if display:
        info("Display        : %s  (from %s)" % (display, cfg.get("parser") or "?"))
    else:
        warn("Display type   : could not be read from config.toml")

    # --- the authoritative check: ask the kernel ------------------------
    live = live_gpio_consumers()
    lgpio_holders = []
    if live:
        header = {p: c for p, c in live.items() if p <= 27}
        internal = {p: c for p, c in live.items() if p > 27}

        ok("Kernel reports %d claimed header lines" % len(header))
        for pin in sorted(header):
            consumer = header[pin]
            tag = ""
            if consumer.strip().lower() in ("lg", "lgpio", "rpi-lgpio"):
                lgpio_holders.append(pin)
                tag = "   <-- held by a running lgpio process"
            note("BCM %-2d claimed by %s%s" % (pin, consumer, tag))
            owned.setdefault(pin, "kernel: %s" % consumer)

        if internal:
            info("%d internal SoC lines also claimed (not 40-pin header):"
                 % len(internal))
            note(", ".join("%d=%s" % (p, internal[p]) for p in sorted(internal)))
            note("On a Pi 5 these live on the same gpiochip as the header but")
            note("are the power button, camera regulators and PHY reset. They")
            note("are not usable pins and are nothing to worry about.")
    else:
        warn("Could not read live GPIO state ('gpioinfo' missing or not root).")
        note("Install gpiod ('sudo apt install gpiod') and re-run with sudo for")
        note("an authoritative answer that does not rely on my display table.")

    if lgpio_holders:
        print()
        warn("Lines %s are held by a process using lgpio."
             % ", ".join("BCM %d" % p for p in lgpio_holders))
        note("On this image that is almost certainly pwnagotchi itself,")
        note("driving the display. If you try to start a SECOND pwnagotchi")
        note("by hand while the service runs, it will fail to claim these and")
        note("die with lgpio.error: 'GPIO not allocated'.")
        note("Check with:  systemctl status pwnagotchi")
        note("Stop it first if you want to run in the foreground.")

    if display and not known_display:
        bad("I do not have a pin table for display '%s'." % display)
        note("I CANNOT tell you which pins are safe. Do not trust any list")
        note("below. Either leave charging_gpio = -1, or check by hand with")
        note("'pinctrl get 0-27' while pwnagotchi is running.")
        PROBLEMS.append("unknown display '%s' - GPIO safety unverified" % display)

    # --- verdict on the configured pin ----------------------------------
    configured = cfg.get("madhatter", {}).get("charging_gpio")
    if configured is not None:
        try:
            pin = int(str(configured).strip())
        except (TypeError, ValueError):
            pin = -1
        if pin >= 0:
            if pin in owned:
                bad("Your charging_gpio = %d is claimed by %s" % (pin, owned[pin]))
                PROBLEMS.append("charging_gpio %d conflict" % pin)
            elif not known_display or not live:
                warn("charging_gpio = %d is not in my tables, but I could not "
                     "verify it independently." % pin)
                note("Verify with 'pinctrl get %d' while pwnagotchi runs." % pin)
            else:
                ok("charging_gpio = %d is free" % pin)

    if known_display and live:
        software_claimed = {p for p in owned if p <= 27}
        wired = set()
        for name, pins in DISPLAY_GPIOS.items():
            if display and name in display:
                wired |= {p for p in pins if p not in live}
        free = [p for p in range(2, 28)
                if p not in software_claimed and p not in wired]

        info("Electrically free: %s" % ", ".join(str(p) for p in free))
        if wired:
            note("Also unclaimed by software, but physically wired to your")
            note("display HAT (its buttons/LEDs): %s"
                 % ", ".join(str(p) for p in sorted(wired)))
            note("Nothing would stop you claiming these, but the HAT's own")
            note("switches drive those lines, so a signal wire there will")
            note("fight the button. Prefer the list above.")
    else:
        info("Not listing 'free' pins - I cannot verify them on this system.")


# --------------------------------------------------------------------------
# Config emission
# --------------------------------------------------------------------------

def emit_config():
    head("8. Suggested config.toml")
    chip = FINDINGS.get("chip")
    if not chip:
        bad("Nothing detected - no config to suggest.")
        return

    ups_type = "auto"
    lines = ["[main.plugins.mad_hatter]", "enabled = true",
             'ups_type = "auto"']

    conf = []          # (line, confidence-note)
    if chip == "ina219":
        shunt = FINDINGS.get("shunt_ohms")
        if shunt:
            conf.append(("shunt_ohms = %s" % shunt, "measured"))
        else:
            conf.append(("shunt_ohms = 0.1", "DEFAULT - could not measure"))
        if "invert_current" in FINDINGS:
            conf.append(("invert_current = %s"
                         % str(FINDINGS["invert_current"]).lower(), "measured"))
    if FINDINGS.get("cells", 1) > 1:
        conf.append(("battery_cells = %d" % FINDINGS["cells"], "measured"))
    if "internal_resistance" in FINDINGS:
        conf.append(("internal_resistance = %s" % FINDINGS["internal_resistance"],
                     "measured"))

    conf.append(("charging_gpio = -1", "safe default - see note below"))

    hint = _capacity_hint()
    if hint:
        conf.append(("battery_mah = %d" % hint[0], "board hint - CONFIRM your cells"))
    else:
        conf.append(("battery_mah = 2000", "*** YOU MUST SET THIS ***"))

    if chip in ("max170xx", "pisugar2", "pisugar3"):
        draw = _expected_avg_draw()
        conf.append(("avg_current_ma = %d" % draw,
                     "est. for this board - tune after a real discharge"))

    print()
    for line in lines:
        print("    " + line)
    for line, why in conf:
        pad = " " * max(1, 34 - len(line))
        print("    %s%s# %s" % (line, pad, why))
    print("    show_voltage = true" + " " * 15 + "# taste")
    print("    shutdown_enabled = false" + " " * 10 + "# policy - your call")
    print()

    info('ups_type = "auto" is deliberate: %s was detected, and auto also' % chip)
    note("avoids the per-board default GPIO, which is one less way to clash.")

    if chip in ("max170xx", "pisugar2", "pisugar3"):
        print()
        warn("This is a fuel gauge with NO current sensor.")
        note("Charging '+' can only come from a GPIO status pin, or from the")
        note("plugin's voltage-trend fallback (slower, ~2 min to settle).")
        note("With charging_gpio = -1 you get the fallback, which is safe and")
        note("needs no pins. Only set a real pin if section 7 above VERIFIED")
        note("it free - a clash here stops pwnagotchi booting at all.")
        note("Since v2.3.0 the plugin measures the average draw ITSELF from how")
        note("fast the SOC gauge falls: draw = (percent per hour / 100) x")
        note("battery_mah. After ~15 min of discharging it uses that in place")
        note("of avg_current_ma, so avg_current_ma is only the cold-start")
        note("value. Get battery_mah right and the rest self-calibrates.")
        note("Watch it appear:  journalctl -u pwnagotchi | grep MadHatter")
        note("or set debug_mode = true to see ~NNNmA on screen.")
        note("NOTE: coulomb counting cannot work on this chip, so the")
        note("accumulated-mAh trick below does NOT apply to you.")

    print()
    if hint:
        import textwrap
        mah, why = hint
        warn("battery_mah is not detectable, but I can narrow it down:")
        for wrapped in textwrap.wrap(why, 62):
            note(wrapped)
        note("Start with battery_mah = %d and correct it against the cells." % mah)
    else:
        warn("battery_mah cannot be detected. Read it off the cell, or the")
        note("vendor's spec. Every runtime estimate scales directly off it,")
        note("so a wrong value makes every '~2h14m' wrong by the same factor.")
        note("If your pack is unlabelled and the chip measures current, run the")
        note("plugin with debug_mode for a full discharge and read the")
        note("accumulated mAh from /root/.mad_hatter_state.json.")


def _expected_avg_draw():
    """Midpoint of this board's expected draw, as a starting avg_current_ma.

    Only a starting point: the real figure depends on display, Wi-Fi activity
    and what else is plugged in, and the user should correct it after watching
    an actual discharge.
    """
    low, high = expected_draw(FINDINGS.get("model", ""))
    return int(round((low + high) / 2.0 / 50.0) * 50)


def _capacity_hint():
    """Board-specific capacity guidance where the hardware is identifiable.

    Deliberately a hint, not a detection: it is inferred from the board model,
    not measured, and the user still has to confirm which cells they fitted.
    """
    chip = FINDINGS.get("chip")
    model = FINDINGS.get("model", "").lower()
    cells = FINDINGS.get("cells", 1)

    if chip == "max170xx" and "pi 5" in model and cells == 1:
        return (6800,
                "MAX17040 at 0x36 on a Pi 5 is the Geekworm X120x family "
                "(X1200/X1201/X1202...). Those carry 2 or 4 18650 cells in "
                "PARALLEL - which is why the gauge reads 1S ~3.9V. Two 3400mAh "
                "cells give ~6800mAh; two 3000mAh give ~6000; a 4-cell X1202 "
                "roughly doubles it. Check what you actually fitted.")
    return None


def summary():
    head("Summary")
    if PROBLEMS:
        for problem in PROBLEMS:
            bad(problem)
        print()
        info("Fix the above, then re-run.")
    else:
        ok("No blocking problems found.")
    undetected = [k for k in ("shunt_ohms", "invert_current") if k not in FINDINGS]
    if FINDINGS.get("chip") == "ina219" and undetected:
        print()
        info("Not determined: %s" % ", ".join(undetected))
        note("Re-run with --watch 600 on battery power to measure them.")


# --------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description="MadHatter UPS diagnostic")
    ap.add_argument("--bus", type=int, default=1)
    ap.add_argument("--watch", type=int, default=0, metavar="SECONDS",
                    help="sample this long to measure polarity and resistance")
    ap.add_argument("--interactive", action="store_true",
                    help="prompt for charger plug/unplug (definitive polarity)")
    ap.add_argument("--shunt", type=float, default=None,
                    help="known shunt in ohms, skips inference")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    if not args.json:
        print(_c("1", "MadHatter doctor v%s" % VERSION))

    cfg = check_environment(args)
    if "no smbus" in PROBLEMS or "i2c disabled" in PROBLEMS:
        summary()
        return 1

    bus, _ = open_bus(args.bus)
    detected = scan(bus, args)
    if not detected:
        check_gpio(cfg)
        summary()
        return 1
    kind, addr = detected

    check_byte_order(bus, kind, addr)

    sampler = Sampler(bus, kind, addr, args.shunt or 0.1)
    try:
        sampler.setup()
    except Exception as exc:
        warn("Chip setup failed: %s" % exc)

    voltage, _ = sampler.sample()
    analyse_pack(voltage)

    if kind == "ina219":
        if args.shunt:
            info("Using shunt_ohms = %s from --shunt" % args.shunt)
            FINDINGS["shunt_ohms"] = args.shunt
        else:
            found = infer_shunt(bus, addr, FINDINGS.get("model", ""))
            if found:
                sampler.shunt = found

    if args.watch or args.interactive:
        watch(sampler, args.watch or 180, args.interactive)
    else:
        head("6. Polarity and internal resistance")
        info("Skipped. Re-run with --watch 300 (on battery) to measure these.")

    check_gpio(cfg)
    emit_config()
    summary()

    if args.json:
        print(json.dumps({"findings": FINDINGS, "problems": PROBLEMS}, indent=2))
    return 0 if not PROBLEMS else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\nInterrupted.")
        sys.exit(130)
