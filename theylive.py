import logging
import time
import threading
import subprocess
import json
import requests
import socket
import websockets  # Added for PwnDroid mode (was missing in previous version)
import pwnagotchi.plugins as plugins
import pwnagotchi.ui.fonts as fonts
from pwnagotchi.ui.components import LabeledValue
from pwnagotchi.ui.view import BLACK
import pwnagotchi


def is_connected():
    """More robust internet connectivity check with multiple fallbacks."""
    trials = [
        "https://api.opwngrid.xyz/api/v1/uptime",
        "https://www.google.com",
        "https://www.cloudflare.com",
    ]
    for url in trials:
        try:
            r = requests.get(url, timeout=10)
            if "uptime" in url:
                if r.json().get("isUp"):
                    return True
            elif r.status_code == 200:
                return True
        except Exception:
            pass
    # Final DNS fallback
    try:
        socket.create_connection(("8.8.8.8", 53), timeout=10)
        return True
    except Exception:
        return False


class GPSBackend:
    def __init__(self, plugin):
        self.plugin = plugin
        self.running = True

    def get_current(self, poll):
        raise NotImplementedError("get_current must be implemented by subclasses")


class GPSD(GPSBackend):
    def __init__(self, gpsdhost, gpsdport, plugin):
        super().__init__(plugin)
        self.socket = None
        self.stream = None
        self.latest_tpv = None
        self.latest_sky = None
        self.lock = threading.Lock()
        self.thread = threading.Thread(target=self._stream_reader, daemon=True)
        self.connect(host=gpsdhost, port=gpsdport)
        if self.stream:
            self.thread.start()

    def connect(self, host="127.0.0.1", port=2947):
        logging.info("[TheyLive] Connecting to gpsd socket at {}:{}".format(host, port))
        for attempt in range(5):
            try:
                self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.socket.connect((host, port))
                self.stream = self.socket.makefile(mode="rw")
                if self.stream:
                    self.stream.write('?WATCH={"enable":true,"json":true}\n')
                    self.stream.flush()
                    welcome_raw = self.stream.readline()
                    welcome = json.loads(welcome_raw)
                    if welcome['class'] != "VERSION":
                        raise Exception("Unexpected welcome message - not a gpsd v3 server?")
                    logging.info("[TheyLive] Connected to gpsd")
                    return
            except Exception as e:
                logging.warning(f"[TheyLive] Connection attempt {attempt+1} failed: {e}. Retrying...")
                time.sleep(5)
        logging.error("[TheyLive] Failed to connect to gpsd after retries.")
        self.stream = None

    def _stream_reader(self):
        while self.running and self.stream:
            try:
                raw = self.stream.readline().strip()
                if not raw:
                    continue
                data = json.loads(raw)
                with self.lock:
                    if data.get('class') == 'TPV':
                        self.latest_tpv = data
                    elif data.get('class') == 'SKY':
                        self.latest_sky = data
            except (json.JSONDecodeError, ValueError) as e:
                logging.error(f"[TheyLive] JSON decode error: {e}")
            except Exception as e:
                logging.error(f"[TheyLive] Stream reader error: {e}")
                break

    def get_current(self, poll):
        with self.lock:
            if poll == 'tpv':
                return self.latest_tpv
            elif poll == 'sky':
                return self.latest_sky
        return None


class PwnDroidGPS(GPSBackend):
    def __init__(self, host, port, plugin):
        super().__init__(plugin)
        self.host = host
        self.port = port
        self.coordinates = {}
        self.thread = threading.Thread(target=self._start_fetch_loop, daemon=True)
        self.thread.start()

    def _start_fetch_loop(self):
        import asyncio
        asyncio.run(self._fetch_loop())

    async def _fetch_loop(self):
        uri = f"ws://{self.host}:{self.port}"
        while self.running:
            try:
                async with websockets.connect(uri, ping_interval=20, ping_timeout=60) as websocket:
                    while self.running:
                        try:
                            message = await websocket.recv()
                            if not message:
                                logging.error("[TheyLive-PwnDroid] Empty message received")
                                continue
                            raw = json.loads(message)
                            lat = raw.get('latitude')
                            lon = raw.get('longitude')
                            mode = 3 if lat is not None and lon is not None else 0
                            self.coordinates = {
                                'mode': mode,
                                'lat': lat if lat is not None else 0.0,
                                'lon': lon if lon is not None else 0.0,
                                'altMSL': raw.get('altitude', 0.0),
                                'speed': raw.get('speed', 0.0),
                                'track': raw.get('bearing') or raw.get('course') or raw.get('track'),
                                'time': time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                            }
                            if self.plugin.agent:
                                self.plugin.agent.session()['gps'] = {
                                    'Latitude': self.coordinates['lat'],
                                    'Longitude': self.coordinates['lon'],
                                    'Altitude': self.coordinates['altMSL'],
                                    'Speed': self.coordinates['speed']
                                }
                        except websockets.ConnectionClosed:
                            break
            except Exception as e:
                logging.error(f"[TheyLive-PwnDroid] Connection error: {e}")
                await asyncio.sleep(5)

    def get_current(self, poll):
        if poll == 'tpv':
            return self.coordinates if self.coordinates else None
        elif poll == 'sky':
            return {}
        return None


class TheyLive(plugins.Plugin):
    __author__ = "discord@rai68 (original) - enhanced by AlienMajik"
    __version__ = "2.1.0"  # Bumped for status conflict fix
    __license__ = "LGPL"
    __description__ = (
        "Advanced GPS plugin for pwnagotchi: displays rich GPS data on screen, logs per-handshake and continuous tracks, "
        "supports gpsd and PwnDroid (Android sharing). Enhancements: HDOP, used/visible sats, heading, smart fix status, "
        "knots unit, continuous NDJSON logging, E-ink friendly updates, robust fixes, no core UI conflicts."
    )

    def __init__(self):
        self.gps_backend = None
        # Default rich field set - 'gpsstat' replaces 'status' to avoid conflict with core Pwnagotchi status line
        self.fields = ['gpsstat', 'fix', 'sat', 'hdop', 'lat', 'lon', 'alt', 'spd', 'trk']
        self.speedUnit = 'ms'
        self.distanceUnit = 'm'
        self.element_pos_x = 130
        self.element_pos_y = 47
        self.host = '127.0.0.1'
        self.port = 2947
        self.pwndroid_host = '192.168.44.1'
        self.pwndroid_port = 8080
        self.spacing = 12
        self.agent = None
        self.loaded = False
        self.ui_setup = False
        self.running = False
        self._black = 0x00
        self.baud = 9600
        self.device = ''
        self.pps_device = ''
        self.disableAuto = False
        self.mode = "server"
        self.bettercap = True
        # New features
        self.track_log = True  # enabled by default - very useful for wardriving
        self.track_interval = 10
        self.track_file = '/root/pwnagotchi_gps_track.ndjson'
        self.track_thread = None
        # E-ink optimization
        self.last_values = {}

    def setup(self):
        if self.disableAuto or self.mode in ('peer', 'pwndroid'):
            return True
        logging.info('[TheyLive] Updating APT cache')
        subprocess.run(['apt-get', 'update'], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        apt_res = subprocess.run(['apt', '-qq', 'list', 'gpsd'], capture_output=True, text=True)
        if 'installed' not in apt_res.stdout:
            logging.info('[TheyLive] Installing gpsd (this may take several minutes)')
            if is_connected():
                subprocess.run(['apt-get', 'install', '-y', 'gpsd', 'gpsd-clients'])
            else:
                logging.error('[TheyLive] No internet - cannot install gpsd')
                return False
        # Write config files (idempotent)
        with open("/etc/default/gpsd", 'w') as f:
            f.writelines([
                'GPSD_OPTIONS="-n -N -b"\n',
                f'BAUDRATE="{self.baud}"\n',
                f'MAIN_GPS="{self.device}"\n',
                f'PPS_DEVICES="{self.pps_device}"\n',
                'GPSD_SOCKET="/var/run/gpsd.sock"\n',
                '/bin/stty -F ${MAIN_GPS} ${BAUDRATE}\n',
                '/bin/setserial ${MAIN_GPS} low_latency\n',
            ])
        with open("/etc/systemd/system/gpsd.service", 'w') as f:
            f.writelines([
                '[Unit]\nDescription=GPS Daemon for pwnagotchi\nRequires=gpsd.socket\n',
                '[Service]\nEnvironmentFile=/etc/default/gpsd\nExecStart=/usr/sbin/gpsd $GPSD_OPTIONS $MAIN_GPS $PPS_DEVICES\n',
                '[Install]\nWantedBy=multi-user.target\nAlso=gpsd.socket\n',
            ])
        with open("/lib/systemd/system/gpsd.socket", 'w') as f:
            f.writelines([
                '[Unit]\nDescription=GPS Daemon Sockets\n',
                '[Socket]\nListenStream=/run/gpsd.sock\nListenStream=[::]:2947\nListenStream=0.0.0.0:2947\nSocketMode=0600\nBindIPv6Only=yes\n',
                '[Install]\nWantedBy=sockets.target\n',
            ])
        subprocess.run(["systemctl", "daemon-reload"])
        subprocess.run(["systemctl", "restart", "gpsd.service"])
        return True

    def on_loaded(self):
        logging.info("[TheyLive] Loading enhanced plugin")
        # Config overrides
        self.host = self.options.get('host', self.host)
        self.port = self.options.get('port', self.port)
        self.pwndroid_host = self.options.get('pwndroid_host', self.pwndroid_host)
        self.pwndroid_port = self.options.get('pwndroid_port', self.pwndroid_port)
        self.disableAuto = not self.options.get('auto', True)
        self.mode = self.options.get('mode', self.mode)
        self.baud = self.options.get('baud', self.baud)
        self.device = self.options.get('device', self.device)
        self.pps_device = self.options.get('pps_device', self.pps_device)
        self.bettercap = self.options.get('bettercap', self.bettercap)
        self.fields = self.options.get('fields', self.fields)
        self.speedUnit = self.options.get('speedUnit', self.speedUnit)
        self.distanceUnit = self.options.get('distanceUnit', self.distanceUnit)
        self.element_pos_x = self.options.get('topleft_x', self.element_pos_x)
        self.element_pos_y = self.options.get('topleft_y', self.element_pos_y)
        # New feature options
        self.track_log = self.options.get('track_log', self.track_log)
        self.track_interval = self.options.get('track_interval', self.track_interval)
        self.track_file = self.options.get('track_file', self.track_file)
        if 'invert' in pwnagotchi.config['ui'] and pwnagotchi.config['ui']['invert']:
            self._black = 0xFF
        elif BLACK == 0xFF:
            self._black = 0xFF
        if self.mode != 'pwndroid':
            self.setup()
            self.gps_backend = GPSD(self.host, self.port, self)
        else:
            self.gps_backend = PwnDroidGPS(self.pwndroid_host, self.pwndroid_port, self)
            logging.info("[TheyLive] PwnDroid mode active")
        self.loaded = True
        logging.info("[TheyLive] Plugin loaded successfully")

    def on_ready(self, agent):
        while not self.loaded:
            time.sleep(0.1)
        self.agent = agent
        self.running = True
        if self.bettercap and self.mode != 'pwndroid':
            logging.info(f"[TheyLive] Enabling bettercap GPS ({self.host}:{self.port})")
            try:
                agent.run("gps off")
            except:
                pass
            agent.run(f"set gps.device {self.host}:{self.port}; set gps.baudrate 9600; gps on")
        else:
            try:
                agent.run("gps off")
            except:
                pass
            logging.info("[TheyLive] bettercap GPS disabled (not supported in PwnDroid mode)")
        if self.track_log:
            self.track_thread = threading.Thread(target=self._track_logger, daemon=True)
            self.track_thread.start()
            logging.info(f"[TheyLive] Continuous track logging enabled -> {self.track_file}")

    def _track_logger(self):
        while self.running:
            coords = self.gps_backend.get_current('tpv') or {}
            sky = self.gps_backend.get_current('sky') or {}
            if coords.get('mode', 0) >= 2 and 'lat' in coords and 'lon' in coords:
                entry = {
                    'time': coords.get('time') or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    'lat': coords['lat'],
                    'lon': coords['lon'],
                    'alt': coords.get('altMSL'),
                    'speed': coords.get('speed'),
                    'track': coords.get('track'),
                    'hdop': sky.get('hdop'),
                }
                try:
                    with open(self.track_file, 'a') as f:
                        json.dump(entry, f)
                        f.write('\n')
                except Exception as e:
                    logging.error(f"[TheyLive] Track logging error: {e}")
            time.sleep(self.track_interval)

    def on_handshake(self, agent, filename, access_point, client_station):
        coords = self.gps_backend.get_current('tpv')
        if coords and coords.get('mode', 0) >= 2 and 'lat' in coords and 'lon' in coords:
            gps_file = filename.replace(".pcap", ".gps.json")
            data = {
                'Latitude': coords['lat'],
                'Longitude': coords['lon'],
                'Altitude': coords.get('altMSL'),
                'Speed': coords.get('speed'),
                'Track': coords.get('track'),
            }
            try:
                with open(gps_file, "w") as f:
                    json.dump(data, f)
                logging.info(f"[TheyLive] Saved per-handshake GPS: {gps_file}")
            except Exception as e:
                logging.error(f"[TheyLive] Failed to save handshake GPS: {e}")
        else:
            logging.debug("[TheyLive] No valid fix for handshake GPS")

    def on_ui_setup(self, ui):
        while not self.loaded:
            time.sleep(0.1)
        for i, item in enumerate(self.fields):
            # Custom short label for the fix status field
            label = "stat:" if item == 'gpsstat' else f"{item}:"
            # Alignment logic preserved and extended: longer labels shift left to align values
            effective_len = 4 if item == 'gpsstat' else len(item)  # Treat gpsstat as length 4 for alignment (like hdop)
            pos_x = self.element_pos_x - 5 * (effective_len - 3 if effective_len > 3 else 0)
            pos_y = self.element_pos_y + (self.spacing * i)
            ui.add_element(
                item,  # Unique element name (no conflict with core 'status')
                LabeledValue(
                    color=self._black,
                    label=label,
                    value="-",
                    position=(pos_x, pos_y),
                    label_font=fonts.Small,
                    text_font=fonts.Small,
                ),
            )
        self.ui_setup = True
        self.last_values.clear()

    def on_unload(self, ui):
        self.running = False
        try:
            self.agent.run("gps off")
        except:
            pass
        if self.mode != 'pwndroid':
            subprocess.run(["systemctl", "stop", "gpsd.service"])
        with ui._lock:
            for item in self.fields:
                try:
                    ui.remove_element(item)
                except:
                    pass
        self.gps_backend.running = False
        logging.info("[TheyLive] Plugin unloaded")

    def on_ui_update(self, ui):
        if not self.ui_setup:
            return
        coords = self.gps_backend.get_current('tpv') or {}
        sky = self.gps_backend.get_current('sky') or {}
        mode = coords.get('mode', 0)
        lat = coords.get('lat', 0.0)
        lon = coords.get('lon', 0.0)
        alt = coords.get('altMSL', 0.0)
        speed_raw = coords.get('speed', 0.0)
        heading = coords.get('track')
        hdop = sky.get('hdop')
        visible = len(sky.get('satellites', []))
        used = sum(1 for s in sky.get('satellites', []) if s.get('used')) if visible else 0
        # Unit conversion
        if self.distanceUnit == 'ft':
            alt *= 3.28084
        if self.speedUnit == 'kph':
            speed = speed_raw * 3.6
            unit = 'km/h'
        elif self.speedUnit == 'mph':
            speed = speed_raw * 2.23694
            unit = 'mph'
        elif self.speedUnit == 'kn':
            speed = speed_raw * 1.94384
            unit = 'kn'
        else:
            speed = speed_raw
            unit = 'm/s'
        # Status calculation
        if mode == 3:
            if hdop is not None and hdop < 2.0:
                status = "Good 3D"
            elif hdop is not None:
                status = f"3D ({hdop:.1f})"
            else:
                status = "3D fix"
        elif mode == 2:
            status = "2D fix"
        elif mode == 1:
            status = "Fix"
        else:
            status = "No fix"
        for item in self.fields:
            try:
                if item == 'gpsstat':
                    val = status
                elif item == 'fix':
                    val = {0: '-', 1: '1D', 2: '2D', 3: '3D'}.get(mode, 'err')
                elif item == 'sat':
                    val = f"{used}/{visible}" if visible else "-"
                elif item == 'hdop':
                    val = f"{hdop:.1f}" if hdop is not None else "-"
                elif item == 'lat':
                    val = f"{lat:.4f}" if mode >= 2 else "-"
                elif item == 'lon':
                    val = f"{lon:.4f}" if mode >= 2 else "-"
                elif item == 'alt':
                    val = f"{alt:.1f}{self.distanceUnit}" if mode == 3 else "-"
                elif item == 'spd':
                    val = f"{speed:.1f}{unit}" if mode >= 2 else "-"
                elif item == 'trk':
                    val = f"{heading:.0f}°" if heading is not None and speed_raw > 1.0 else "-"
                else:
                    val = "-"
                # E-ink optimization: only update if changed
                if self.last_values.get(item) != val:
                    ui.set(item, val)
                    self.last_values[item] = val
            except Exception as e:
                logging.debug(f"[TheyLive] UI update error for {item}: {e}")
                ui.set(item, "err")
