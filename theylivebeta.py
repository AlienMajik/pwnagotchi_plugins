import logging
import time
import threading
import os
import subprocess
import random
import asyncio
import websockets
import json
import requests
import pwnagotchi.plugins as plugins
import pwnagotchi.ui.fonts as fonts
from pwnagotchi.ui.components import LabeledValue
from pwnagotchi.ui.view import BLACK
import pwnagotchi

def is_connected():
    try:
        # check DNS
        host = 'https://api.opwngrid.xyz/api/v1/uptime'
        r = requests.get(host, headers=None, timeout=(30.0, 60.0))
        if r.json().get('isUp'):
            return True
    except:
        pass
    return False

class GPSBackend:
    def __init__(self, plugin):
        self.plugin = plugin
        self.coordinates = {}
        self.running = True

    def get_current(self, poll):
        raise NotImplementedError("get_current must be implemented by subclasses")

class GPSD(GPSBackend):
    def __init__(self, gpsdhost, gpsdport, plugin):
        super().__init__(plugin)
        self.socket = None
        self.stream = None
        self.connect(host=gpsdhost, port=gpsdport)

    def connect(self, host="127.0.0.1", port=2947):
        logging.info("[TheyLive] Connecting to gpsd socket at {}:{}".format(host, port))
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((host, port))
            self.stream = self.socket.makefile(mode="rw")
        except Exception as e:
            logging.warning(f"[TheyLive] error occured during socket setup, try power cycle the device. Err: {e}")
        self.stream.write('?WATCH={"enable":true}\n')
        self.stream.flush()
        welcome_raw = self.stream.readline()
        welcome = json.loads(welcome_raw)
        if welcome['class'] != "VERSION":
            raise Exception("Unexpected data received as welcome. Is the server a gpsd 3 server?")
        logging.info("[TheyLive] connected")

    def get_current(self, poll):
        if not self.running:
            return None

        self.stream.write("?POLL;\n")
        self.stream.flush()
        raw = self.stream.readline()
        if not raw.strip():
            logging.warning("[TheyLive] Empty response from gpsd")
            return None
        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, ValueError) as e:
            logging.error(f"[TheyLive] Error decoding gpsd response: {e} - Raw data: {raw}")
            return None
        except Exception as e:
            logging.error(f"[TheyLive] Unexpected error in gpsd response: {e} - Raw data: {raw}")
            return None

        if 'class' in data:
            if data['class'] == 'POLL':
                if 'tpv' in data and poll == 'tpv' and data['tpv']:
                    return data['tpv'][0]
                elif 'sky' in data and poll == 'sky' and data['sky']:
                    return data['sky'][0]
                else:
                    logging.debug(f"[TheyLive] No data in {poll} from gpsd POLL")
                    return None
            elif data['class'] == 'DEVICES':
                return None
        return None

class PwnDroidGPS(GPSBackend):
    def __init__(self, host, port, plugin):
        super().__init__(plugin)
        self.host = host
        self.port = port
        self.websocket = None
        self.thread = threading.Thread(target=self._start_fetch_loop, daemon=True)
        self.thread.start()

    def _start_fetch_loop(self):
        asyncio.run(self._fetch_loop())

    async def _fetch_loop(self):
        uri = f"ws://{self.host}:{self.port}"
        while self.running:
            try:
                async with websockets.connect(uri) as websocket:
                    self.websocket = websocket
                    while self.running:
                        try:
                            message = await websocket.recv()
                            if message:
                                self.coordinates = json.loads(message)
                                # Map to GPSD-like format
                                self.coordinates = {
                                    'mode': 3 if 'latitude' in self.coordinates and self.coordinates['latitude'] else 0,
                                    'lat': self.coordinates.get('latitude', 0.0),
                                    'lon': self.coordinates.get('longitude', 0.0),
                                    'altMSL': self.coordinates.get('altitude', 0.0),
                                    'speed': self.coordinates.get('speed', 0.0)
                                }
                                # Update session gps for compatibility with other plugins
                                if self.plugin.agent:
                                    session_gps = {
                                        'Latitude': self.coordinates['lat'],
                                        'Longitude': self.coordinates['lon'],
                                        'Altitude': self.coordinates['altMSL'],
                                        'Speed': self.coordinates['speed']
                                    }
                                    self.plugin.agent.session()['gps'] = session_gps
                            else:
                                logging.error("[TheyLive-PwnDroid] Received empty message")
                                await asyncio.sleep(5)
                        except websockets.ConnectionClosed:
                            break
            except Exception as e:
                logging.error(f"[TheyLive-PwnDroid] Connection error: {e}")
                await asyncio.sleep(5)

    def get_current(self, poll):
        if poll == 'tpv':
            return self.coordinates if self.coordinates else None
        return None  # 'sky' not supported

class TheyLive(plugins.Plugin):
    __author__ = "discord@rai68"  # Original author
    __version__ = "1.1.0"  # Updated version with PwnDroid support
    __license__ = "LGPL"
    __description__ = (
        "Setups and installs gpsd to report lat/long on the screen and setup bettercap pcap gps logging. "
        "Added support for PwnDroid for GPS sharing via Android app over Bluetooth tether."
    )

    def __init__(self):
        self.gps_backend = None
        self.fields = ['fix', 'lat', 'lon', 'alt', 'spd']
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
        self.bettercap = True
        self.loaded = False
        self.ui_setup = False
        self.valid_device = False
        self.running = False

        # display setup
        self._black = 0x00

        self.pps_device = ''
        self.device = ''
        self.baud = 9600

        # auto setup
        self.disableAuto = False
        self.mode = "server"

    def setup(self):
        if self.disableAuto or self.mode == 'peer' or self.mode == 'pwndroid':
            return True

        # Update APT cache first to avoid outdated cache issues
        logging.info('[TheyLive] Updating APT cache')
        subprocess.run(['apt-get', 'update'], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True)

        aptRes = subprocess.run(['apt', '-qq', 'list', 'gpsd'],
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True)
        if 'installed' not in aptRes.stdout:
            logging.info('[TheyLive] GPSd not installed, trying now. This may take up to 5-10 minutes just let me run')
            if is_connected():
                subprocess.run(['apt-get', 'install', '-y', 'gpsd', 'gpsd-clients'])
            else:
                logging.error('[TheyLive] GPSd not installed, no internet. Please connect and reload pwnagotchi')
                return False

        logging.info('[TheyLive] GPSd should be installed')
        baseConf = [
            'GPSD_OPTIONS="-n -N -b"\n',
            f'BAUDRATE="{self.baud}"\n',
            f'MAIN_GPS="{self.device}"\n',
            f'PPS_DEVICES="{self.pps_device}"\n',
            'GPSD_SOCKET="/var/run/gpsd.sock"\n',
            '/bin/stty -F ${MAIN_GPS} ${BAUDRATE}\n',
            '/bin/setserial ${MAIN_GPS} low_latency\n'
        ]
        baseService = [
            '[Unit]\n',
            'Description=GPS (Global Positioning System) Daemon for pwnagotchi\n',
            'Requires=gpsd.socket\n',
            '[Service]\n',
            'EnvironmentFile=/etc/default/gpsd\n',
            'ExecStart=/usr/sbin/gpsd $GPSD_OPTIONS $MAIN_GPS $PPS_DEVICES\n',
            '[Install]\n',
            'WantedBy=multi-user.target\n',
            'Also=gpsd.socket\n',
        ]
        baseSocket = [
            '[Unit]\n',
            'Description=GPS (Global Positioning System) Daemon Sockets\n',
            '[Socket]\n',
            'ListenStream=/run/gpsd.sock\n',
            'ListenStream=[::]:2947\n',
            'ListenStream=0.0.0.0:2947\n',
            'SocketMode=0600\n',
            'BindIPv6Only=yes\n',
            '[Install]\n',
            'WantedBy=sockets.target\n'
        ]

        logging.info("[TheyLive] Updating autoconfig if changed")
        with open("/etc/default/gpsd", 'a+', newline="\n") as gpsdConf:
            fileLinesConf = gpsdConf.readlines()
            changedConf = baseConf != fileLinesConf
            if changedConf:
                gpsdConf.seek(0)
                gpsdConf.truncate()
                for line in baseConf:
                    gpsdConf.write(line)
        with open("/etc/systemd/system/gpsd.service", 'a+', newline="\n") as gpsdService:
            fileLinesService = gpsdService.readlines()
            changedService = baseService != fileLinesService
            if changedService:
                gpsdService.seek(0)
                gpsdService.truncate()
                for line in baseService:
                    gpsdService.write(line)

        with open("/lib/systemd/system/gpsd.socket", 'a+', newline="\n") as gpsdSocket:
            fileLinesSocket = gpsdSocket.readlines()
            changedSocket = baseSocket != fileLinesSocket
            if changedSocket:
                gpsdSocket.seek(0)
                gpsdSocket.truncate()
                for line in baseSocket:
                    gpsdSocket.write(line)
        changed = changedConf or changedService or changedSocket
        logging.info(f"[TheyLive] finished updating configs, Updated: {changed}")
        if changed:
            subprocess.run(["systemctl", "stop", "gpsd.service", "gpsd.socket"])
            subprocess.run(["systemctl", "daemon-reload"])
        serRes = subprocess.run(['systemctl', "status","gpsd.service"],stdout = subprocess.PIPE,stderr = subprocess.STDOUT,universal_newlines = True)
        if 'active (running)' not in serRes.stdout:
            subprocess.run(["systemctl", "start","gpsd.service"])
        return True

    def on_loaded(self):
        logging.info("[TheyLive] plugin loading begin")
        if 'host' in self.options:
            self.host = self.options['host']

        if 'port' in self.options:
            self.port = self.options['port']

        if 'pwndroid_host' in self.options:
            self.pwndroid_host = self.options['pwndroid_host']

        if 'pwndroid_port' in self.options:
            self.pwndroid_port = self.options['pwndroid_port']

        #auto setup variables
        if 'auto' in self.options:
            self.disableAuto = not self.options['auto']

        if 'mode' in self.options:
            self.mode = self.options['mode']

        if 'baud' in self.options:
            self.baud = self.options['baud']

        if 'device' in self.options:
            self.device = self.options['device']

        if 'pps_device' in self.options:
            self.pps_device = self.options['pps_device']

        logging.debug("[TheyLive] starting major setup function")
        if self.mode != 'pwndroid':
            res = self.setup()
            logging.debug("[TheyLive] ended major setup function, status: {res}")
            self.gps_backend = GPSD(self.host, self.port, self)
        else:
            self.gps_backend = PwnDroidGPS(self.pwndroid_host, self.pwndroid_port, self)
            logging.info("[TheyLive] PwnDroid mode enabled, using WebSocket for GPS")

        # other variables like display and bettercap
        if 'bettercap' in self.options:
            self.bettercap = self.options['bettercap']

        if 'fields' in self.options:
            self.fields = self.options['fields']

        if 'speedUnit' in self.options:
            self.speedUnit = self.options['speedUnit']

        if 'distanceUnit' in self.options:
            self.distanceUnit = self.options['distanceUnit']
        if 'topleft_x' in self.options:
            self.element_pos_x = self.options['topleft_x']

        if 'topleft_y' in self.options:
            self.element_pos_y = self.options['topleft_y']
        if 'invert' in pwnagotchi.config['ui'] and pwnagotchi.config['ui']['invert'] == 1 or BLACK == 0xFF:
            self._black = 0xFF
        self.loaded = True
        logging.info("[TheyLive] plugin loading finished!")

    def on_ready(self, agent):
        while not self.loaded:
            time.sleep(0.1)
        self.agent = agent
        if self.bettercap and self.mode != 'pwndroid':
            logging.info(f"[TheyLive] enabling bettercap's gps module for {self.host}:{self.port}")
            try:
                agent.run("gps off")
            except Exception:
                logging.info(f"[TheyLive] bettercap gps was already off")
                pass
            agent.run(f"set gps.device {self.host}:{self.port}; set gps.baudrate 9600; gps on")
            logging.info("[TheyLive] bettercap set and on")
            self.running = True
        else:
            try:
                agent.run("gps off")
            except Exception:
                logging.info(f"[TheyLive] bettercap gps was already off")
                pass
            logging.info("[TheyLive] bettercap gps reporting disabled (not supported in PwnDroid mode)")

    def on_handshake(self, agent, filename, access_point, client_station):
        coords = self.gps_backend.get_current('tpv')
        if coords is not None and 'lat' in coords and 'lon' in coords:
            gps_filename = filename.replace(".pcap", ".gps.json")
            logging.info(f"[TheyLive] saving GPS to {gps_filename} ({coords})")
            with open(gps_filename, "w+t") as fp:
                struct = {
                    'Longitude': coords['lon'],
                    'Latitude': coords['lat']
                }
                json.dump(struct, fp)
        else:
            logging.info("[TheyLive] not saving GPS: no fix")

    def on_ui_setup(self, ui):
        # add coordinates for other displays
        while not self.loaded:
            time.sleep(0.1)
        label_spacing = 0
        logging.info(f"[TheyLive] setting up UI elements: {self.fields}")
        for i, item in enumerate(self.fields):
            element_pos_x = self.element_pos_x
            element_pos_y = self.element_pos_y + (self.spacing * i)
            if len(item) == 4:
                element_pos_x = element_pos_x - 5
            pos = (element_pos_x, element_pos_y)
            ui.add_element(
                item,
                LabeledValue(
                    color=self._black,
                    label=f"{item}:",
                    value="-",
                    position=pos,
                    label_font=fonts.Small,
                    text_font=fonts.Small,
                    label_spacing=label_spacing,
                ),
            )
        logging.info(f"[TheyLive] done setting up UI elements: {self.fields}")
        self.ui_setup = True

    def on_unload(self, ui):
        logging.info("[TheyLive] bettercap gps reporting disabled")
        try:
            self.agent.run("gps off")
        except Exception:
            logging.info(f"[TheyLive] bettercap gps was already off")
        if self.mode != 'pwndroid':
            subprocess.run(["systemctl", "stop","gpsd.service"])

        with ui._lock:
            for element in self.fields:
                try:
                    ui.remove_element(element)
                except:
                    logging.warning("[TheyLive] Element would not be removed skipping")
                    pass

        self.gps_backend.running = False
        logging.info("[TheyLive] plugin disabled")

    def on_ui_update(self, ui):
        if not self.ui_setup:
            return

        coords = self.gps_backend.get_current('tpv')
        if coords is None:
            return

        for item in self.fields:
            if item == 'fix':
                try:
                    if coords['mode'] == 0:
                        ui.set("fix", f"-")
                    elif coords['mode'] == 1:
                        ui.set("fix", f"0D")
                    elif coords['mode'] == 2:
                        ui.set("fix", f"2D")
                    elif coords['mode'] == 3:
                        ui.set("fix", f"3D")
                    else:
                        ui.set("fix", f"err")
                except: ui.set("fix", f"err")
            elif item == 'lat':
                try:
                    if coords['mode'] == 0:
                        ui.set("lat", f"{0:.4f} ")
                    elif coords['mode'] == 1:
                        ui.set("lat", f"{0:.4f} ")
                    elif coords['mode'] == 2:
                        ui.set("lat", f"{coords['lat']:.4f} ")
                    elif coords['mode'] == 3:
                        ui.set("lat", f"{coords['lat']:.4f} ")
                    else:
                        ui.set("lat", f"err")
                except: ui.set("lat", f"err")
            elif item == 'lon':
                try:
                    if coords['mode'] == 0:
                        ui.set("lon", f"{0:.4f} ")
                    elif coords['mode'] == 1:
                        ui.set("lon", f"{0:.4f} ")
                    elif coords['mode'] == 2:
                        ui.set("lon", f"{coords['lon']:.4f} ")
                    elif coords['mode'] == 3:
                        ui.set("lon", f"{coords['lon']:.4f} ")
                    else:
                        ui.set("lon", f"err")
                except: ui.set("lon", f"err")
            elif item == 'alt':
                try:
                    if 'altMSL' in coords:
                        if self.distanceUnit == 'ft':
                            coords['altMSL'] = coords['altMSL'] * 3.281
                        if coords['mode'] == 0:
                            ui.set("alt", f"{0:.1f}{self.distanceUnit}")
                        elif coords['mode'] == 1:
                            ui.set("alt", f"{0:.1f}{self.distanceUnit}")
                        elif coords['mode'] == 2:
                            ui.set("alt", f"{0:.1f}{self.distanceUnit}")
                        elif coords['mode'] == 3:
                            ui.set("alt", f"{coords['altMSL']:.1f}{self.distanceUnit}")
                        else:
                            ui.set("alt", f"err")
                    else:
                        ui.set("alt", f"{0:.1f}{self.distanceUnit}")
                except: ui.set("alt", f"err")

            elif item == 'spd':
                try:
                    if 'speed' in coords:
                        if self.speedUnit == 'kph':
                            coords['speed'] = coords['speed'] * 3.6
                        elif self.speedUnit == 'mph':
                            coords['speed'] = coords['speed'] * 2.237
                        else:
                            coords['speed']
                    else:
                        coords['speed'] = 0

                    if self.speedUnit == 'kph':
                        displayUnit = 'km/h'
                    elif self.speedUnit == 'mph':
                        displayUnit = 'mph'
                    elif self.speedUnit == 'ms':
                        displayUnit = 'm/s'
                    else:
                        coords['mode'] = -1  # err mode
                    if coords['mode'] == 0:
                        ui.set("spd", f"{0:.2f}{displayUnit}")
                    elif coords['mode'] == 1:
                        ui.set("spd", f"{0:.2f}{displayUnit}")
                    elif coords['mode'] == 2:
                        ui.set("spd", f"{coords['speed']:.2f}{displayUnit}")
                    elif coords['mode'] == 3:
                        ui.set("spd", f"{coords['speed']:.2f}{displayUnit}")
                    else:
                        ui.set("spd", f"err")
                except:
                    ui.set("spd", f"err")

            else:
                if item:
                    # custom item add unit after f}
                    try:
                        if coords['mode'] == 0:
                            ui.set(item, f"{0:.1f}")
                        elif coords['mode'] == 1:
                            ui.set(item, f"{coords[item]:.2f}")
                        elif coords['mode'] == 2:
                            ui.set(item, f"{coords[item]:.2f}")
                        elif coords['mode'] == 3:
                            ui.set(item, f"{coords[item]:.2f}")
                        else:
                            ui.set(item, f"err")
                    except: ui.set(item, f"err")
