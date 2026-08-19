"""
TheyLive - advanced GPS plugin for Pwnagotchi.

Original: discord@rai68 (gpsd-easy)
Enhanced by: AlienMajik
v2.2.1: reliability, reconnection, stale-fix protection, webhook export.
Verified against jayofelony Pwnagotchi 2.9.5.8 (handshakes are .pcapng, View.add_element
colour inversion, LabeledValue value placement, threaded on_loaded dispatch).

License: LGPL
"""

import asyncio
import json
import logging
import math
import os
import shutil
import socket
import subprocess
import threading
import time

import pwnagotchi.plugins as plugins
import pwnagotchi.ui.fonts as fonts
from pwnagotchi.ui.components import LabeledValue
from pwnagotchi.ui.view import BLACK

LOG = "[TheyLive]"

# ---------------------------------------------------------------------------
# Field definitions
# ---------------------------------------------------------------------------
# Every UI element created by this plugin is namespaced with UI_PREFIX so it can
# never collide with a core Pwnagotchi element ('status', 'mode', 'name', ...)
# or with an element owned by another plugin.
UI_PREFIX = "theylive_"

FIELD_LABELS = {
    "gpsstat": "stat:",
    "fix": "fix:",
    "sat": "sat:",
    "hdop": "hdop:",
    "pdop": "pdop:",
    "vdop": "vdop:",
    "lat": "lat:",
    "lon": "lon:",
    "alt": "alt:",
    "spd": "spd:",
    "trk": "trk:",
    "dist": "dist:",
}

DEFAULT_FIELDS = ["gpsstat", "fix", "sat", "hdop", "lat", "lon", "alt", "spd", "trk"]

# factor applied to the m/s value returned by gpsd, plus display suffix
SPEED_UNITS = {
    "ms": (1.0, "m/s"),
    "kph": (3.6, "km/h"),
    "mph": (2.23694, "mph"),
    "kn": (1.94384, "kn"),
}
DISTANCE_UNITS = {
    "m": (1.0, "m"),
    "ft": (3.28084, "ft"),
}

EARTH_RADIUS_M = 6371008.8


def haversine(lat1, lon1, lat2, lon2):
    """Great-circle distance in metres between two WGS84 points."""
    try:
        p1, p2 = math.radians(lat1), math.radians(lat2)
        dp = p2 - p1
        dl = math.radians(lon2 - lon1)
        a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
        return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(min(1.0, a)))
    except Exception:
        return 0.0


# pwnagotchi's LabeledValue.draw() places the value at
#   x + label_spacing + 5 * len(label)
# regardless of the actual font metrics, so mirror that exact arithmetic to make
# every value line up on one column. (Measuring the font instead drifts.)
LABEL_SPACING = 5


def label_offset(label):
    """Horizontal distance from a LabeledValue's origin to its value."""
    return LABEL_SPACING + 5 * len(label)


def is_connected(timeout=5):
    """Internet connectivity check with multiple fallbacks (cheap DNS test first)."""
    try:
        socket.setdefaulttimeout(timeout)
        socket.create_connection(("1.1.1.1", 53), timeout=timeout).close()
        return True
    except Exception:
        pass
    try:
        import requests
    except Exception:
        return False
    for url in ("https://api.opwngrid.xyz/api/v1/uptime", "https://www.google.com"):
        try:
            r = requests.get(url, timeout=timeout)
            if "uptime" in url:
                if r.json().get("isUp"):
                    return True
            elif r.status_code == 200:
                return True
        except Exception:
            continue
    return False


def write_if_changed(path, content):
    """Write only when the content actually differs. Returns True if written."""
    try:
        if os.path.exists(path):
            with open(path, "r") as f:
                if f.read() == content:
                    return False
        parent = os.path.dirname(path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        with open(path, "w") as f:
            f.write(content)
        return True
    except Exception as e:
        logging.error(f"{LOG} Could not write {path}: {e}")
        return False


def run_cmd(args, timeout=300):
    try:
        return subprocess.run(args, capture_output=True, text=True, timeout=timeout)
    except Exception as e:
        logging.warning(f"{LOG} Command {' '.join(args)} failed: {e}")
        return None


# ---------------------------------------------------------------------------
# Backends
# ---------------------------------------------------------------------------
class GPSBackend:
    name = "generic"

    def __init__(self, plugin):
        self.plugin = plugin
        self.running = True
        self.connected = False

    def get_current(self, poll="tpv"):
        raise NotImplementedError

    def stop(self):
        self.running = False


class GPSD(GPSBackend):
    """gpsd JSON client with automatic reconnect and stale-data protection."""

    name = "gpsd"

    def __init__(self, host, port, plugin, max_age=10.0):
        super().__init__(plugin)
        self.host = host
        self.port = int(port)
        self.max_age = float(max_age)
        self._sock = None
        self._stream = None
        self._tpv = None
        self._tpv_ts = 0.0
        self._sky = None
        self._sky_ts = 0.0
        self._lock = threading.Lock()
        self._thread = threading.Thread(target=self._run, daemon=True, name="theylive-gpsd")
        self._thread.start()

    # -- connection handling -------------------------------------------------
    def _close(self):
        self.connected = False
        for obj in (self._stream, self._sock):
            try:
                if obj is not None:
                    obj.close()
            except Exception:
                pass
        self._stream = None
        self._sock = None

    def _connect(self):
        self._close()
        try:
            self._sock = socket.create_connection((self.host, self.port), timeout=10)
            self._sock.settimeout(30)
            self._stream = self._sock.makefile(mode="rw", encoding="utf-8", newline="\n")
            self._stream.write('?WATCH={"enable":true,"json":true}\n')
            self._stream.flush()
            deadline = time.monotonic() + 10
            while time.monotonic() < deadline:
                line = self._stream.readline()
                if line == "":
                    raise ConnectionError("gpsd closed the connection during handshake")
                try:
                    msg = json.loads(line)
                except ValueError:
                    continue
                if msg.get("class") == "VERSION":
                    self.connected = True
                    logging.info(
                        f"{LOG} Connected to gpsd {msg.get('release', '?')} at {self.host}:{self.port}"
                    )
                    return True
            raise ConnectionError("no VERSION banner received from gpsd")
        except Exception as e:
            logging.warning(f"{LOG} gpsd connect to {self.host}:{self.port} failed: {e}")
            self._close()
            return False

    def _run(self):
        backoff = 2
        while self.running:
            if not self.connected:
                if not self._connect():
                    time.sleep(backoff)
                    backoff = min(backoff * 2, 60)
                    continue
                backoff = 2
            try:
                line = self._stream.readline()
                # readline() returning '' means EOF: without this check the old
                # version spun at 100% CPU forever after gpsd went away.
                if line == "":
                    raise ConnectionError("gpsd connection closed (EOF)")
                line = line.strip()
                if not line:
                    continue
                msg = json.loads(line)
                cls = msg.get("class")
                now = time.monotonic()
                if cls == "TPV":
                    with self._lock:
                        self._tpv = msg
                        self._tpv_ts = now
                elif cls == "SKY":
                    with self._lock:
                        self._sky = msg
                        self._sky_ts = now
            except socket.timeout:
                logging.warning(f"{LOG} No data from gpsd for 30s - reconnecting")
                self._close()
            except ValueError as e:
                logging.debug(f"{LOG} Ignoring malformed gpsd JSON: {e}")
            except Exception as e:
                if self.running:
                    logging.warning(f"{LOG} gpsd stream error: {e} - reconnecting")
                self._close()
                time.sleep(2)
        self._close()

    # -- data access ---------------------------------------------------------
    def get_current(self, poll="tpv"):
        now = time.monotonic()
        with self._lock:
            if poll == "tpv":
                if self._tpv is not None and (now - self._tpv_ts) <= self.max_age:
                    return self._tpv
            elif poll == "sky":
                # SKY arrives less often than TPV, allow a longer window
                if self._sky is not None and (now - self._sky_ts) <= max(self.max_age * 3, 30):
                    return self._sky
        return None

    def stop(self):
        self.running = False
        try:
            if self._sock is not None:
                self._sock.shutdown(socket.SHUT_RDWR)
        except Exception:
            pass
        self._close()


class PwnDroidGPS(GPSBackend):
    """Android GPS over a WebSocket (PwnDroid / ShareGPS style JSON)."""

    name = "pwndroid"

    def __init__(self, host, port, plugin, max_age=15.0):
        super().__init__(plugin)
        self.host = host
        self.port = int(port)
        self.max_age = float(max_age)
        self._coords = None
        self._ts = 0.0
        self._lock = threading.Lock()
        self._thread = threading.Thread(target=self._runner, daemon=True, name="theylive-pwndroid")
        self._thread.start()

    def _runner(self):
        try:
            import websockets  # imported lazily so server/peer mode never needs it
        except ImportError:
            logging.error(
                f"{LOG} PwnDroid mode needs the 'websockets' package: sudo pip3 install websockets"
            )
            return
        try:
            asyncio.run(self._fetch_loop(websockets))
        except Exception as e:
            logging.error(f"{LOG} PwnDroid loop terminated: {e}")

    async def _fetch_loop(self, websockets):
        uri = f"ws://{self.host}:{self.port}"
        backoff = 2
        while self.running:
            try:
                async with websockets.connect(
                    uri, ping_interval=20, ping_timeout=60, close_timeout=5
                ) as ws:
                    self.connected = True
                    backoff = 2
                    logging.info(f"{LOG} PwnDroid connected to {uri}")
                    while self.running:
                        message = await ws.recv()
                        if not message:
                            continue
                        try:
                            raw = json.loads(message)
                        except ValueError:
                            logging.debug(f"{LOG} PwnDroid sent non-JSON data")
                            continue
                        self._ingest(raw)
            except Exception as e:
                self.connected = False
                if self.running:
                    logging.warning(f"{LOG} PwnDroid connection error: {e} - retrying in {backoff}s")
                # asyncio is imported at module level now; the old version had it
                # only as a local of the caller, so this line raised NameError.
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 60)
        self.connected = False

    def _ingest(self, raw):
        lat = raw.get("latitude", raw.get("lat"))
        lon = raw.get("longitude", raw.get("lon"))
        if lat is None or lon is None:
            return
        alt = raw.get("altitude", raw.get("alt"))
        coords = {
            "mode": 3 if alt is not None else 2,
            "lat": float(lat),
            "lon": float(lon),
            "altMSL": float(alt) if alt is not None else None,
            "speed": raw.get("speed"),
            "track": raw.get("bearing", raw.get("course", raw.get("track"))),
            "accuracy": raw.get("accuracy"),
            "time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
        with self._lock:
            self._coords = coords
            self._ts = time.monotonic()

    def get_current(self, poll="tpv"):
        if poll != "tpv":
            return None
        with self._lock:
            if self._coords is not None and (time.monotonic() - self._ts) <= self.max_age:
                return self._coords
        return None

    def stop(self):
        self.running = False


# ---------------------------------------------------------------------------
# Plugin
# ---------------------------------------------------------------------------
class TheyLive(plugins.Plugin):
    __author__ = "discord@rai68 (original) - enhanced by AlienMajik"
    __version__ = "2.2.1"
    __license__ = "LGPL"
    __description__ = (
        "Advanced GPS plugin for Pwnagotchi: rich on-screen GPS data, per-handshake and continuous "
        "track logging, GPX/GeoJSON export, gpsd and PwnDroid backends with automatic reconnection, "
        "stale-fix protection and namespaced UI elements (no core UI conflicts)."
    )

    def __init__(self):
        self.gps_backend = None
        self.fields = list(DEFAULT_FIELDS)
        self.speedUnit = "ms"
        self.distanceUnit = "m"
        self.element_pos_x = 130
        self.element_pos_y = 47
        self.spacing = 12
        self.align_values = True
        self.precision = 5

        self.host = "127.0.0.1"
        self.port = 2947
        self.pwndroid_host = "192.168.44.1"
        self.pwndroid_port = 8080

        self.mode = "server"
        self.baud = 9600
        self.device = "/dev/ttyACM0"
        self.pps_device = ""
        self.disableAuto = False
        self.bettercap = True
        self.gpsd_listen_all = False
        self.stop_gpsd_on_unload = False
        self.max_fix_age = 10.0
        self.min_track_speed = 1.0

        # track logging
        self.track_log = True
        self.track_interval = 10
        self.track_min_distance = 3.0
        self.track_max_gap = 300
        self.track_file = "/root/pwnagotchi_gps_track.ndjson"
        self.track_max_mb = 32
        self.track_handshakes = True

        self.agent = None
        self._cfg_lock = threading.Lock()
        self._configured = False
        self._overflow_warned = False
        self.loaded = False
        self.ui_setup = False
        self.running = False
        self._black = 0x00
        self._worker = None
        self._last_values = {}
        self._last_point = None
        self._last_written = 0.0
        self._writes = 0
        self.stats = {
            "points": 0,
            "handshakes": 0,
            "distance_m": 0.0,
            "first_fix": None,
            "last_fix": None,
        }

    # -- option helpers ------------------------------------------------------
    def _opt(self, key, default, cast=None):
        try:
            value = (getattr(self, "options", None) or {}).get(key, default)
            if value is None:
                return default
            return cast(value) if cast else value
        except Exception:
            logging.warning(f"{LOG} Invalid value for option '{key}', using {default!r}")
            return default

    def _validate_fields(self, raw):
        if isinstance(raw, str):
            raw = [f.strip() for f in raw.split(",")]
        elif not isinstance(raw, (list, tuple)):
            logging.warning(f"{LOG} 'fields' must be a list - using defaults")
            return list(DEFAULT_FIELDS)
        out = []
        for item in raw or []:
            item = str(item).strip()
            if item == "status":  # legacy name that clobbered the core status line
                logging.warning(f"{LOG} Field 'status' is deprecated - using 'gpsstat'")
                item = "gpsstat"
            if item not in FIELD_LABELS:
                logging.warning(f"{LOG} Unknown field '{item}' ignored")
                continue
            if item not in out:
                out.append(item)
        return out or list(DEFAULT_FIELDS)

    # -- gpsd auto setup -----------------------------------------------------
    def setup(self):
        """Install and configure gpsd. Only touches the system when needed."""
        if shutil.which("gpsd") is None:
            if not is_connected():
                logging.error(f"{LOG} gpsd is not installed and there is no internet connection")
                return False
            logging.info(f"{LOG} Installing gpsd (this can take several minutes)")
            run_cmd(["apt-get", "update"], timeout=600)
            res = run_cmd(["apt-get", "install", "-y", "gpsd", "gpsd-clients"], timeout=1800)
            if res is None or res.returncode != 0:
                logging.error(f"{LOG} gpsd installation failed")
                return False

        if self.device and not os.path.exists(self.device):
            logging.warning(
                f"{LOG} GPS device {self.device} does not exist yet - check 'device' in config.toml"
            )

        listen = "0.0.0.0" if self.gpsd_listen_all else "127.0.0.1"
        devices = " ".join(d for d in (self.device, self.pps_device) if d)
        changed = False

        changed |= write_if_changed(
            "/etc/default/gpsd",
            "# Managed by the TheyLive pwnagotchi plugin - manual edits will be overwritten\n"
            'START_DAEMON="true"\n'
            'GPSD_OPTIONS="-n -N"\n'
            f'BAUDRATE="{self.baud}"\n'
            f'MAIN_GPS="{self.device}"\n'
            f'PPS_DEVICES="{self.pps_device}"\n'
            f'DEVICES="{devices}"\n'
            'GPSD_SOCKET="/run/gpsd.sock"\n'
            'USBAUTO="true"\n',
        )

        # stty/setserial belong in ExecStartPre, not in the EnvironmentFile:
        # systemd rejects non KEY=VALUE lines, which broke the old unit.
        changed |= write_if_changed(
            "/etc/systemd/system/gpsd.service",
            "[Unit]\n"
            "Description=GPS (Global Positioning System) Daemon - configured by TheyLive\n"
            "Requires=gpsd.socket\n"
            "After=network.target\n"
            "\n"
            "[Service]\n"
            "Type=simple\n"
            "EnvironmentFile=-/etc/default/gpsd\n"
            "ExecStartPre=-/bin/stty -F ${MAIN_GPS} ${BAUDRATE}\n"
            "ExecStartPre=-/bin/setserial ${MAIN_GPS} low_latency\n"
            "ExecStart=/usr/sbin/gpsd $GPSD_OPTIONS $MAIN_GPS $PPS_DEVICES\n"
            "Restart=on-failure\n"
            "RestartSec=5\n"
            "\n"
            "[Install]\n"
            "WantedBy=multi-user.target\n"
            "Also=gpsd.socket\n",
        )

        changed |= write_if_changed(
            "/etc/systemd/system/gpsd.socket",
            "[Unit]\n"
            "Description=GPS (Global Positioning System) Daemon Sockets\n"
            "\n"
            "[Socket]\n"
            "ListenStream=/run/gpsd.sock\n"
            f"ListenStream={listen}:{self.port}\n"
            "SocketMode=0600\n"
            "BindIPv6Only=yes\n"
            "\n"
            "[Install]\n"
            "WantedBy=sockets.target\n",
        )

        if changed:
            logging.info(f"{LOG} gpsd configuration updated - reloading systemd")
            run_cmd(["systemctl", "daemon-reload"], timeout=60)
            run_cmd(["systemctl", "enable", "gpsd.socket", "gpsd.service"], timeout=60)
            run_cmd(["systemctl", "restart", "gpsd.socket"], timeout=60)
            run_cmd(["systemctl", "restart", "gpsd.service"], timeout=60)
        else:
            res = run_cmd(["systemctl", "is-active", "gpsd.service"], timeout=30)
            if res is None or res.stdout.strip() != "active":
                logging.info(f"{LOG} Starting gpsd")
                run_cmd(["systemctl", "start", "gpsd.socket"], timeout=60)
                run_cmd(["systemctl", "start", "gpsd.service"], timeout=60)
        return True

    # -- lifecycle -----------------------------------------------------------
    def on_loaded(self):
        self._ensure_config()
        threading.Thread(target=self._init_backend, daemon=True, name="theylive-init").start()

    def _ensure_config(self):
        """Parse options exactly once.

        On pwnagotchi >= 2.9.5.x ``on_loaded`` is dispatched on its own thread
        while every other callback runs on the plugin's event queue, so
        ``on_ui_setup`` can genuinely land first. Both entry points call this.
        """
        with self._cfg_lock:
            if self._configured:
                return
            self._parse_options()
            self._configured = True

    def _parse_options(self):
        logging.info(f"{LOG} Loading v{self.__version__}")

        self.mode = str(self._opt("mode", self.mode)).lower()
        if self.mode not in ("server", "peer", "pwndroid"):
            logging.warning(f"{LOG} Unknown mode '{self.mode}' - falling back to 'server'")
            self.mode = "server"

        self.host = self._opt("host", self.host, str)
        self.port = self._opt("port", self.port, int)
        self.pwndroid_host = self._opt("pwndroid_host", self.pwndroid_host, str)
        self.pwndroid_port = self._opt("pwndroid_port", self.pwndroid_port, int)
        self.disableAuto = not self._opt("auto", True, bool)
        self.baud = self._opt("baud", self.baud, int)
        self.device = self._opt("device", self.device, str)
        self.pps_device = self._opt("pps_device", self.pps_device, str)
        self.bettercap = self._opt("bettercap", self.bettercap, bool)
        self.gpsd_listen_all = self._opt("gpsd_listen_all", self.gpsd_listen_all, bool)
        self.stop_gpsd_on_unload = self._opt("stop_gpsd_on_unload", self.stop_gpsd_on_unload, bool)
        self.max_fix_age = self._opt("max_fix_age", self.max_fix_age, float)
        self.min_track_speed = self._opt("min_track_speed", self.min_track_speed, float)

        self.fields = self._validate_fields(self._opt("fields", self.fields))
        self.speedUnit = self._opt("speedUnit", self.speedUnit, str)
        if self.speedUnit not in SPEED_UNITS:
            logging.warning(f"{LOG} Unknown speedUnit '{self.speedUnit}' - using m/s")
            self.speedUnit = "ms"
        self.distanceUnit = self._opt("distanceUnit", self.distanceUnit, str)
        if self.distanceUnit not in DISTANCE_UNITS:
            logging.warning(f"{LOG} Unknown distanceUnit '{self.distanceUnit}' - using m")
            self.distanceUnit = "m"

        self.element_pos_x = self._opt("topleft_x", self.element_pos_x, int)
        self.element_pos_y = self._opt("topleft_y", self.element_pos_y, int)
        self.spacing = self._opt("spacing", self.spacing, int)
        self.align_values = self._opt("align_values", self.align_values, bool)
        self.precision = max(3, min(8, self._opt("precision", self.precision, int)))

        self.track_log = self._opt("track_log", self.track_log, bool)
        self.track_interval = max(1, self._opt("track_interval", self.track_interval, int))
        self.track_min_distance = self._opt("track_min_distance", self.track_min_distance, float)
        self.track_max_gap = self._opt("track_max_gap", self.track_max_gap, int)
        self.track_file = self._opt("track_file", self.track_file, str)
        self.track_max_mb = self._opt("track_max_mb", self.track_max_mb, int)
        self.track_handshakes = self._opt("track_handshakes", self.track_handshakes, bool)

        self.loaded = True
        self.running = True
        logging.info(f"{LOG} Loaded in '{self.mode}' mode, fields: {', '.join(self.fields)}")

    def _init_backend(self):
        try:
            if self.mode == "pwndroid":
                self.gps_backend = PwnDroidGPS(
                    self.pwndroid_host, self.pwndroid_port, self, max_age=self.max_fix_age * 1.5
                )
                logging.info(f"{LOG} PwnDroid mode active")
            else:
                if self.mode == "server" and not self.disableAuto:
                    try:
                        self.setup()
                    except Exception as e:
                        logging.error(f"{LOG} gpsd auto-setup failed: {e}")
                self.gps_backend = GPSD(self.host, self.port, self, max_age=self.max_fix_age)
        except Exception as e:
            logging.error(f"{LOG} Backend initialisation failed: {e}")

    def on_ready(self, agent):
        self._ensure_config()
        self.agent = agent
        self.running = True
        self._configure_bettercap(agent)
        if self._worker is None or not self._worker.is_alive():
            self._worker = threading.Thread(
                target=self._gps_worker, daemon=True, name="theylive-worker"
            )
            self._worker.start()
        if self.track_log:
            logging.info(f"{LOG} Continuous track logging -> {self.track_file}")

    def _configure_bettercap(self, agent):
        try:
            agent.run("gps off")
        except Exception:
            pass
        if not self.bettercap or self.mode == "pwndroid":
            logging.info(f"{LOG} bettercap GPS integration disabled")
            return
        try:
            logging.info(f"{LOG} Enabling bettercap GPS via {self.host}:{self.port}")
            agent.run(f"set gps.device {self.host}:{self.port}")
            agent.run(f"set gps.baudrate {self.baud}")
            agent.run("gps on")
        except Exception as e:
            logging.warning(f"{LOG} Could not enable bettercap GPS: {e}")

    def on_unload(self, ui):
        self.running = False
        try:
            if self.agent is not None:
                self.agent.run("gps off")
        except Exception:
            pass
        if self.gps_backend is not None:
            try:
                self.gps_backend.stop()
            except Exception:
                pass
        if self.stop_gpsd_on_unload and self.mode == "server":
            run_cmd(["systemctl", "stop", "gpsd.service"], timeout=60)
        try:
            with ui._lock:
                for item in self.fields:
                    try:
                        ui.remove_element(UI_PREFIX + item)
                    except Exception:
                        pass
        except Exception:
            for item in self.fields:
                try:
                    ui.remove_element(UI_PREFIX + item)
                except Exception:
                    pass
        self.ui_setup = False
        self._last_values.clear()
        logging.info(f"{LOG} Plugin unloaded")

    # -- data helpers --------------------------------------------------------
    def _poll(self, what):
        backend = self.gps_backend
        if backend is None:
            return None
        try:
            return backend.get_current(what)
        except Exception as e:
            logging.debug(f"{LOG} Backend poll error: {e}")
            return None

    @staticmethod
    def _altitude(coords):
        """gpsd >= 3.20 reports altMSL; older releases only have alt/altHAE."""
        for key in ("altMSL", "alt", "altHAE"):
            value = coords.get(key)
            if value is not None:
                return float(value)
        return None

    def _snapshot(self):
        """Return a normalised dict of the current fix (never stale)."""
        coords = self._poll("tpv") or {}
        sky = self._poll("sky") or {}
        mode = int(coords.get("mode", 0) or 0)
        sats = sky.get("satellites") or []
        speed = coords.get("speed")
        return {
            "mode": mode,
            "lat": coords.get("lat"),
            "lon": coords.get("lon"),
            "alt": self._altitude(coords),
            "speed": float(speed) if isinstance(speed, (int, float)) else None,
            "track": coords.get("track"),
            "hdop": sky.get("hdop"),
            "pdop": sky.get("pdop"),
            "vdop": sky.get("vdop"),
            "accuracy": coords.get("accuracy") or coords.get("eph"),
            "visible": len(sats),
            "used": sum(1 for s in sats if s.get("used")),
            "time": coords.get("time") or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "valid": mode >= 2 and coords.get("lat") is not None and coords.get("lon") is not None,
        }

    # -- worker: odometer, track log -----------------------------------------
    def _gps_worker(self):
        while self.running:
            try:
                fix = self._snapshot()
                if fix["valid"]:
                    now = time.time()
                    if self.stats["first_fix"] is None:
                        self.stats["first_fix"] = fix["time"]
                        logging.info(
                            f"{LOG} First fix acquired: {fix['lat']:.5f}, {fix['lon']:.5f}"
                        )
                    self.stats["last_fix"] = fix["time"]

                    moved = None
                    if self._last_point is not None:
                        moved = haversine(
                            self._last_point[0], self._last_point[1], fix["lat"], fix["lon"]
                        )
                        # ignore sub-metre GPS jitter in the odometer
                        if moved >= max(2.0, self.track_min_distance):
                            self.stats["distance_m"] += moved

                    should_log = (
                        self._last_point is None
                        or moved is None
                        or moved >= self.track_min_distance
                        or (now - self._last_written) >= self.track_max_gap
                    )
                    if self.track_log and should_log:
                        self._write_track_point(fix)
                        self._last_written = now
                    self._last_point = (fix["lat"], fix["lon"])
            except Exception as e:
                logging.debug(f"{LOG} Worker error: {e}")
            # sleep in small slices so unloading is responsive
            slept = 0.0
            while self.running and slept < self.track_interval:
                time.sleep(0.5)
                slept += 0.5

    def _rotate_track_file(self):
        try:
            limit = self.track_max_mb * 1024 * 1024
            if limit > 0 and os.path.getsize(self.track_file) > limit:
                backup = self.track_file + ".1"
                if os.path.exists(backup):
                    os.remove(backup)
                os.rename(self.track_file, backup)
                logging.info(f"{LOG} Rotated track log to {backup}")
        except FileNotFoundError:
            pass
        except Exception as e:
            logging.debug(f"{LOG} Track rotation failed: {e}")

    def _write_track_point(self, fix, extra=None):
        entry = {
            "time": fix["time"],
            "lat": round(fix["lat"], 7),
            "lon": round(fix["lon"], 7),
            "alt": fix["alt"],
            "speed": fix["speed"],
            "track": fix["track"],
            "hdop": fix["hdop"],
            "sat": fix["used"],
            "mode": fix["mode"],
        }
        if extra:
            entry.update(extra)
        try:
            parent = os.path.dirname(self.track_file)
            if parent:
                os.makedirs(parent, exist_ok=True)
            with open(self.track_file, "a") as f:
                f.write(json.dumps(entry) + "\n")
            self.stats["points"] += 1
            self._writes += 1
            if self._writes % 200 == 0:
                self._rotate_track_file()
        except Exception as e:
            logging.error(f"{LOG} Track logging error: {e}")

    # -- handshakes ----------------------------------------------------------
    def on_handshake(self, agent, filename, access_point, client_station):
        fix = self._snapshot()
        if not fix["valid"]:
            logging.debug(f"{LOG} No valid fix for handshake {os.path.basename(filename)}")
            return
        # 2.9.5.x captures are .pcapng and webgpsmap looks for <base>.gps.json
        # after stripping that suffix, so strip whichever suffix is present.
        gps_file = filename
        for suffix in (".pcapng", ".pcap"):
            if gps_file.endswith(suffix):
                gps_file = gps_file[: -len(suffix)]
                break
        gps_file += ".gps.json"
        accuracy = fix["accuracy"]
        if accuracy is None and fix["hdop"] is not None:
            accuracy = round(float(fix["hdop"]) * 5.0, 1)  # rough UERE estimate
        data = {
            # webgpsmap / wigle friendly keys
            "Latitude": fix["lat"],
            "Longitude": fix["lon"],
            "Altitude": fix["alt"],
            "Speed": fix["speed"],
            "Track": fix["track"],
            "Accuracy": accuracy,
            "Fix": fix["mode"],
            "Satellites": fix["used"],
            "Updated": fix["time"],
        }
        try:
            with open(gps_file, "w") as f:
                json.dump(data, f)
            self.stats["handshakes"] += 1
            logging.info(f"{LOG} Saved per-handshake GPS: {os.path.basename(gps_file)}")
        except Exception as e:
            logging.error(f"{LOG} Failed to save handshake GPS: {e}")

        if self.track_log and self.track_handshakes:
            ap = access_point or {}
            self._write_track_point(
                fix,
                {
                    "type": "handshake",
                    "ssid": ap.get("hostname"),
                    "bssid": ap.get("mac"),
                    "channel": ap.get("channel"),
                },
            )

    # -- UI ------------------------------------------------------------------
    def on_ui_setup(self, ui):
        self._ensure_config()
        self._black = self._ui_color()
        for i, item in enumerate(self.fields):
            label = FIELD_LABELS.get(item, f"{item}:")
            # Shift the label left by the exact offset the core widget uses, so
            # every value starts at element_pos_x.
            pos_x = self.element_pos_x - label_offset(label) if self.align_values else self.element_pos_x
            pos_y = self.element_pos_y + (self.spacing * i)
            self._warn_if_offscreen(ui, pos_x, pos_y)
            name = UI_PREFIX + item
            try:
                ui.remove_element(name)  # tolerate a plugin reload
            except Exception:
                pass
            try:
                ui.add_element(
                    name,
                    LabeledValue(
                        color=self._black,
                        label=label,
                        value="-",
                        position=(max(0, pos_x), pos_y),
                        label_font=fonts.Small,
                        text_font=fonts.Small,
                    ),
                )
            except Exception as e:
                logging.error(f"{LOG} Could not add UI element {name}: {e}")
        self._last_values.clear()
        self.ui_setup = True

    @staticmethod
    def _ui_color():
        """Text colour, read live from the view module.

        On the jayofelony images BLACK is 0xFF and View.__init__ rewrites the
        module global to 0x00 when ui.invert is set - and View.add_element then
        flips any non-zero colour again. Reading the global at element-creation
        time is exactly what the core widgets do, so we match them either way.
        """
        try:
            import pwnagotchi.ui.view as _view

            return getattr(_view, "BLACK", BLACK)
        except Exception:
            return BLACK

    def _warn_if_offscreen(self, ui, pos_x, pos_y):
        if self._overflow_warned:
            return
        try:
            width, height = ui.width(), ui.height()
        except Exception:
            return
        if pos_x < 0 or pos_y + 10 > height or pos_x > width:
            logging.warning(
                f"{LOG} Field at ({pos_x},{pos_y}) falls outside the {width}x{height} "
                f"display - lower topleft_y/spacing or use fewer fields"
            )
            self._overflow_warned = True

    def _status_text(self, fix):
        backend = self.gps_backend
        if backend is None:
            return "Starting"
        if not getattr(backend, "connected", False):
            return "No gpsd" if backend.name == "gpsd" else "No link"
        mode = fix["mode"]
        if mode == 3:
            hdop = fix["hdop"]
            if hdop is not None:
                return "Good 3D" if hdop < 2.0 else f"3D ({hdop:.1f})"
            if fix["accuracy"] is not None:
                return f"3D +-{float(fix['accuracy']):.0f}m"
            return "3D fix"
        if mode == 2:
            return "2D fix"
        if fix["visible"]:
            return f"Acq {fix['used']}/{fix['visible']}"
        return "No fix"

    def _format_distance(self):
        metres = self.stats["distance_m"]
        if self.distanceUnit == "ft":
            miles = metres / 1609.344
            return f"{miles:.2f}mi"
        if metres >= 1000:
            return f"{metres / 1000:.2f}km"
        return f"{metres:.0f}m"

    def on_ui_update(self, ui):
        if not self.ui_setup:
            return
        fix = self._snapshot()
        mode = fix["mode"]
        valid = fix["valid"]

        alt_factor, alt_suffix = DISTANCE_UNITS[self.distanceUnit]
        spd_factor, spd_suffix = SPEED_UNITS[self.speedUnit]
        alt = fix["alt"] * alt_factor if fix["alt"] is not None else None
        speed_raw = fix["speed"]
        speed = speed_raw * spd_factor if speed_raw is not None else None
        status = self._status_text(fix)

        for item in self.fields:
            name = UI_PREFIX + item
            try:
                if item == "gpsstat":
                    val = status
                elif item == "fix":
                    val = {0: "-", 1: "NF", 2: "2D", 3: "3D"}.get(mode, "-")
                elif item == "sat":
                    val = f"{fix['used']}/{fix['visible']}" if fix["visible"] else "-"
                elif item in ("hdop", "pdop", "vdop"):
                    dop = fix[item]
                    val = f"{float(dop):.1f}" if dop is not None else "-"
                elif item == "lat":
                    val = f"{fix['lat']:.{self.precision}f}" if valid else "-"
                elif item == "lon":
                    val = f"{fix['lon']:.{self.precision}f}" if valid else "-"
                elif item == "alt":
                    val = f"{alt:.1f}{alt_suffix}" if valid and alt is not None else "-"
                elif item == "spd":
                    val = f"{speed:.1f}{spd_suffix}" if valid and speed is not None else "-"
                elif item == "trk":
                    heading = fix["track"]
                    moving = speed_raw is not None and speed_raw > self.min_track_speed
                    val = f"{float(heading):.0f}d" if (heading is not None and moving) else "-"
                elif item == "dist":
                    val = self._format_distance()
                else:
                    val = "-"
            except Exception as e:
                logging.debug(f"{LOG} Value error for {item}: {e}")
                val = "-"
            # E-ink friendly: only redraw fields whose value actually changed
            if self._last_values.get(item) != val:
                try:
                    ui.set(name, val)
                    self._last_values[item] = val
                except Exception as e:
                    logging.debug(f"{LOG} UI set failed for {name}: {e}")

    # -- web ui --------------------------------------------------------------
    def on_webhook(self, path, request):
        from flask import Response, abort

        if path is None or path == "/" or path == "":
            fix = self._snapshot()
            rows = "".join(
                f"<tr><th>{k}</th><td>{v}</td></tr>"
                for k, v in (
                    ("Mode", self.mode),
                    ("Backend", getattr(self.gps_backend, "name", "-")),
                    ("Connected", getattr(self.gps_backend, "connected", False)),
                    ("Status", self._status_text(fix)),
                    ("Latitude", fix["lat"]),
                    ("Longitude", fix["lon"]),
                    ("Altitude", fix["alt"]),
                    ("Satellites", f"{fix['used']}/{fix['visible']}"),
                    ("HDOP", fix["hdop"]),
                    ("Track points", self.stats["points"]),
                    ("Handshakes tagged", self.stats["handshakes"]),
                    ("Distance", self._format_distance()),
                    ("First fix", self.stats["first_fix"]),
                    ("Track file", self.track_file),
                )
            )
            html = (
                "<html><head><title>TheyLive GPS</title>"
                "<meta name='viewport' content='width=device-width, initial-scale=1'>"
                "<style>body{font-family:sans-serif;margin:2em}"
                "table{border-collapse:collapse}th,td{border:1px solid #ccc;padding:.4em .8em;text-align:left}"
                "a{margin-right:1em}</style></head><body>"
                f"<h1>TheyLive v{self.__version__}</h1><table>{rows}</table>"
                "<p><a href='/plugins/theylive/gpx'>Download GPX</a>"
                "<a href='/plugins/theylive/geojson'>Download GeoJSON</a></p>"
                "</body></html>"
            )
            return html

        if path in ("gpx", "geojson"):
            points = self._read_track()
            if not points:
                abort(404)
            if path == "gpx":
                return Response(
                    self._to_gpx(points),
                    mimetype="application/gpx+xml",
                    headers={"Content-Disposition": "attachment; filename=theylive.gpx"},
                )
            return Response(
                json.dumps(self._to_geojson(points)),
                mimetype="application/geo+json",
                headers={"Content-Disposition": "attachment; filename=theylive.geojson"},
            )
        abort(404)

    def _read_track(self, limit=200000):
        points = []
        try:
            with open(self.track_file, "r") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                    except ValueError:
                        continue
                    if entry.get("lat") is not None and entry.get("lon") is not None:
                        points.append(entry)
                    if len(points) >= limit:
                        break
        except FileNotFoundError:
            return []
        except Exception as e:
            logging.error(f"{LOG} Could not read track file: {e}")
        return points

    @staticmethod
    def _to_gpx(points):
        out = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            '<gpx version="1.1" creator="TheyLive" xmlns="http://www.topografix.com/GPX/1/1">',
            "<trk><name>TheyLive track</name><trkseg>",
        ]
        for p in points:
            seg = f'<trkpt lat="{p["lat"]}" lon="{p["lon"]}">'
            if p.get("alt") is not None:
                seg += f'<ele>{p["alt"]}</ele>'
            if p.get("time"):
                seg += f'<time>{p["time"]}</time>'
            out.append(seg + "</trkpt>")
        out.append("</trkseg></trk></gpx>")
        return "\n".join(out)

    @staticmethod
    def _to_geojson(points):
        line = {
            "type": "Feature",
            "properties": {"name": "TheyLive track", "points": len(points)},
            "geometry": {
                "type": "LineString",
                "coordinates": [[p["lon"], p["lat"]] for p in points],
            },
        }
        features = [line]
        for p in points:
            if p.get("type") == "handshake":
                features.append(
                    {
                        "type": "Feature",
                        "properties": {
                            "ssid": p.get("ssid"),
                            "bssid": p.get("bssid"),
                            "time": p.get("time"),
                        },
                        "geometry": {"type": "Point", "coordinates": [p["lon"], p["lat"]]},
                    }
                )
        return {"type": "FeatureCollection", "features": features}
