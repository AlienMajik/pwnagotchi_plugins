import logging
import sqlite3
import os
from threading import Lock
import pwnagotchi.plugins as plugins
from pwnagotchi.ui.components import LabeledValue
from pwnagotchi.ui.view import BLACK
import pwnagotchi.ui.fonts as fonts
from flask import render_template_string
import time
from math import radians, sin, cos, sqrt, atan2
from datetime import datetime
import subprocess

class Database:
    def __init__(self, path):
        self.__path = path
        self.__db_connect()

    def __db_connect(self):
        logging.info('[SnoopR] Setting up database connection...')
        self.__connection = sqlite3.connect(self.__path, check_same_thread=False)
        cursor = self.__connection.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS networks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                mac TEXT NOT NULL UNIQUE,
                type TEXT NOT NULL,
                name TEXT,
                device_type TEXT NOT NULL,  -- 'wifi' or 'bluetooth'
                is_snooper INTEGER DEFAULT 0
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS detections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL,
                network_id INTEGER NOT NULL,
                encryption TEXT,
                signal_strength INTEGER,
                latitude TEXT,
                longitude TEXT,
                timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(session_id) REFERENCES sessions(id),
                FOREIGN KEY(network_id) REFERENCES networks(id)
            )
        ''')
        cursor.close()
        self.__connection.commit()
        logging.info('[SnoopR] Successfully connected to db')

    def disconnect(self):
        self.__connection.commit()
        self.__connection.close()
        logging.info('[SnoopR] Closed db connection')

    def new_session(self):
        cursor = self.__connection.cursor()
        cursor.execute('INSERT INTO sessions DEFAULT VALUES')
        session_id = cursor.lastrowid
        cursor.close()
        self.__connection.commit()
        return session_id

    def add_detection(self, session_id, mac, type_, name, device_type, encryption, signal_strength, latitude, longitude):
        cursor = self.__connection.cursor()
        cursor.execute('SELECT id FROM networks WHERE mac = ? AND device_type = ?', (mac, device_type))
        result = cursor.fetchone()
        if result:
            network_id = result[0]
        else:
            cursor.execute('INSERT INTO networks (mac, type, name, device_type) VALUES (?, ?, ?, ?)', (mac, type_, name, device_type))
            network_id = cursor.lastrowid
        cursor.execute('''
            INSERT INTO detections (session_id, network_id, encryption, signal_strength, latitude, longitude)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (session_id, network_id, encryption, signal_strength, latitude, longitude))
        cursor.close()
        self.__connection.commit()
        return network_id

    def get_all_networks(self):
        cursor = self.__connection.cursor()
        cursor.execute('''
            SELECT n.mac, n.type, n.name, n.device_type, MIN(d.timestamp) as first_seen, MIN(d.session_id) as first_session,
                   MAX(d.timestamp) as last_seen, MAX(d.session_id) as last_session, COUNT(DISTINCT d.session_id) as sessions_count,
                   d2.latitude, d2.longitude, n.is_snooper
            FROM networks n
            LEFT JOIN detections d ON n.id = d.network_id
            LEFT JOIN detections d2 ON n.id = d2.network_id AND d2.timestamp = (
                SELECT MAX(timestamp) FROM detections WHERE network_id = n.id
            )
            GROUP BY n.id, n.mac, n.type, n.name, n.device_type
        ''')
        rows = cursor.fetchall()
        networks = []
        for row in rows:
            mac, type_, name, device_type, first_seen, first_session, last_seen, last_session, sessions_count, latitude, longitude, is_snooper = row
            networks.append({
                'mac': mac,
                'type': type_,
                'name': name,
                'device_type': device_type,
                'first_seen': first_seen,
                'first_session': first_session,
                'last_seen': last_seen,
                'last_session': last_session,
                'sessions_count': sessions_count,
                'latitude': float(latitude) if latitude and latitude != '-' else None,
                'longitude': float(longitude) if longitude and longitude != '-' else None,
                'is_snooper': bool(is_snooper)
            })
        cursor.close()
        return networks

    def network_count(self, device_type=None):
        cursor = self.__connection.cursor()
        if device_type:
            cursor.execute('SELECT COUNT(DISTINCT mac) FROM networks WHERE device_type = ?', (device_type,))
        else:
            cursor.execute('SELECT COUNT(DISTINCT mac) FROM networks')
        count = cursor.fetchone()[0]
        cursor.close()
        return count

    def snooper_count(self, device_type=None):
        cursor = self.__connection.cursor()
        if device_type:
            cursor.execute('SELECT COUNT(*) FROM networks WHERE is_snooper = 1 AND device_type = ?', (device_type,))
        else:
            cursor.execute('SELECT COUNT(*) FROM networks WHERE is_snooper = 1')
        count = cursor.fetchone()[0]
        cursor.close()
        return count

    def update_snooper_status(self, mac, device_type, is_snooper):
        cursor = self.__connection.cursor()
        cursor.execute('UPDATE networks SET is_snooper = ? WHERE mac = ? AND device_type = ?', (is_snooper, mac, device_type))
        cursor.close()
        self.__connection.commit()

class SnoopR(plugins.Plugin):
    __author__ = 'AlienMajik'
    __version__ = '1.0.0'
    __license__ = 'GPL3'
    __description__ = 'A plugin for wardriving Wi-Fi and Bluetooth networks and detecting snoopers.'

    DEFAULT_PATH = '/root/snoopr'
    DATABASE_NAME = 'snoopr.db'

    def __init__(self):
        self.__db = None
        self.ready = False
        self.__gps_available = True
        self.__lock = Lock()
        self.__last_gps = {'latitude': '-', 'longitude': '-', 'altitude': '-'}
        self.__session_id = None
        self.__bluetooth_enabled = False
        self.last_scan_time = 0

    def on_loaded(self):
        logging.info('[SnoopR] Plugin loaded.')
        self.__path = self.options.get('path', self.DEFAULT_PATH)
        self.__ui_enabled = self.options.get('ui', {}).get('enabled', True)
        self.__gps_config = {'method': self.options.get('gps', {}).get('method', 'bettercap')}
        self.movement_threshold = self.options.get('movement_threshold', 0.1)  # miles
        self.time_threshold_minutes = self.options.get('time_threshold_minutes', 5)  # minutes
        self.__bluetooth_enabled = self.options.get('bluetooth_enabled', False)
        self.timer = self.options.get('timer', 45)  # Scan interval in seconds

        if not os.path.exists(self.__path):
            os.makedirs(self.__path)
        self.__db = Database(os.path.join(self.__path, self.DATABASE_NAME))
        self.__session_id = self.__db.new_session()
        self.ready = True

    def on_ui_setup(self, ui):
        if self.__ui_enabled:
            ui.add_element('snoopr_wifi_networks', LabeledValue(
                color=BLACK, label='WiFi Nets:', value='0', position=(7, 95),
                label_font=fonts.Small, text_font=fonts.Small))
            ui.add_element('snoopr_wifi_snoopers', LabeledValue(
                color=BLACK, label='WiFi Snoopers:', value='0', position=(7, 105),
                label_font=fonts.Small, text_font=fonts.Small))
            if self.__bluetooth_enabled:
                ui.add_element('snoopr_bt_networks', LabeledValue(
                    color=BLACK, label='BT Nets:', value='0', position=(7, 115),
                    label_font=fonts.Small, text_font=fonts.Small))
                ui.add_element('snoopr_bt_snoopers', LabeledValue(
                    color=BLACK, label='BT Snoopers:', value='0', position=(7, 125),
                    label_font=fonts.Small, text_font=fonts.Small))

    def on_ui_update(self, ui):
        if self.__ui_enabled and self.ready:
            current_time = time.time()
            if current_time - self.last_scan_time >= self.timer:
                self.last_scan_time = current_time
                self.on_bluetooth_scan()
            ui.set('snoopr_wifi_networks', str(self.__db.network_count('wifi')))
            ui.set('snoopr_wifi_snoopers', str(self.__db.snooper_count('wifi')))
            if self.__bluetooth_enabled:
                ui.set('snoopr_bt_networks', str(self.__db.network_count('bluetooth')))
                ui.set('snoopr_bt_snoopers', str(self.__db.snooper_count('bluetooth')))

    def on_unload(self, ui):
        if self.__ui_enabled:
            with ui._lock:
                ui.remove_element('snoopr_wifi_networks')
                ui.remove_element('snoopr_wifi_snoopers')
                if self.__bluetooth_enabled:
                    ui.remove_element('snoopr_bt_networks')
                    ui.remove_element('snoopr_bt_snoopers')
        self.__db.disconnect()
        logging.info('[SnoopR] Plugin unloaded')

    def on_unfiltered_ap_list(self, agent, aps):
        if not self.ready:
            return
        gps_data = self.__get_gps(agent)
        if gps_data and all([gps_data['Latitude'], gps_data['Longitude']]):
            self.__last_gps = {
                'latitude': gps_data['Latitude'],
                'longitude': gps_data['Longitude'],
                'altitude': gps_data['Altitude'] or '-'
            }
            coordinates = {'latitude': str(gps_data['Latitude']), 'longitude': str(gps_data['Longitude'])}
            for ap in aps:
                mac = ap['mac']
                ssid = ap['hostname'] if ap['hostname'] != '<hidden>' else ''
                encryption = f"{ap['encryption']}{ap.get('cipher', '')}{ap.get('authentication', '')}"
                rssi = ap['rssi']
                self.__db.add_detection(self.__session_id, mac, 'wi-fi ap', ssid, 'wifi', encryption, rssi, coordinates['latitude'], coordinates['longitude'])
                self.check_and_update_snooper_status(mac, 'wifi')
        else:
            self.__gps_available = False
            self.__last_gps = {'latitude': '-', 'longitude': '-', 'altitude': '-'}

    def on_bluetooth_scan(self):
        if not self.ready or not self.__bluetooth_enabled:
            return
        gps_data = self.__last_gps
        if gps_data['latitude'] == '-' or gps_data['longitude'] == '-':
            logging.warning('[SnoopR] GPS not available... skipping Bluetooth scan')
            return
        coordinates = {'latitude': gps_data['latitude'], 'longitude': gps_data['longitude']}
        try:
            cmd_inq = "hcitool inq --flush"
            inq_output = subprocess.check_output(cmd_inq.split(), stderr=subprocess.DEVNULL).decode().splitlines()
            for line in inq_output[1:]:
                fields = line.split()
                if len(fields) < 1:
                    continue
                mac_address = fields[0]
                name = self.get_device_name(mac_address)
                self.__db.add_detection(self.__session_id, mac_address, 'bluetooth', name, 'bluetooth', '', 0, coordinates['latitude'], coordinates['longitude'])
                self.check_and_update_snooper_status(mac_address, 'bluetooth')
                logging.debug(f'[SnoopR] Logged Bluetooth device: {mac_address} ({name})')
        except subprocess.CalledProcessError as e:
            logging.error(f"[SnoopR] Error running hcitool: {e}")

    def get_device_name(self, mac_address):
        try:
            cmd_name = f"hcitool name {mac_address}"
            name_output = subprocess.check_output(cmd_name.split(), stderr=subprocess.DEVNULL).decode().strip()
            return name_output if name_output else 'Unknown'
        except subprocess.CalledProcessError:
            return 'Unknown'

    def check_and_update_snooper_status(self, mac, device_type):
        cursor = self.__db._Database__connection.cursor()
        cursor.execute('''
            SELECT d.latitude, d.longitude, d.timestamp
            FROM detections d
            JOIN networks n ON d.network_id = n.id
            WHERE n.mac = ? AND n.device_type = ?
            ORDER BY d.timestamp
        ''', (mac, device_type))
        rows = cursor.fetchall()
        if len(rows) < 2:
            return
        is_snooper = False
        for i in range(1, len(rows)):
            lat1, lon1, t1 = rows[i-1]
            lat2, lon2, t2 = rows[i]
            if lat1 == '-' or lon1 == '-' or lat2 == '-' or lon2 == '-':
                continue
            lat1, lon1, lat2, lon2 = map(float, [lat1, lon1, lat2, lon2])
            t1 = datetime.strptime(t1, '%Y-%m-%d %H:%M:%S')
            t2 = datetime.strptime(t2, '%Y-%m-%d %H:%M:%S')
            time_diff = (t2 - t1).total_seconds() / 60.0
            if time_diff > self.time_threshold_minutes:
                dist = self.__calculate_distance(lat1, lon1, lat2, lon2)
                if dist > self.movement_threshold:
                    is_snooper = True
                    break
        self.__db.update_snooper_status(mac, device_type, int(is_snooper))

    def __get_gps(self, agent):
        if self.__gps_config['method'] == 'bettercap':
            info = agent.session()
            return info.get('gps', None)
        return None

    def __calculate_distance(self, lat1, lon1, lat2, lon2):
        R = 3958.8  # Earth's radius in miles
        lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
        c = 2 * atan2(sqrt(a), sqrt(1-a))
        return R * c

    def on_webhook(self, path, request):
        if request.method == 'GET' and (path == '/' or not path):
            all_networks = self.__db.get_all_networks()
            snoopers = [n for n in all_networks if n['is_snooper']]
            center = [float(self.__last_gps['latitude']), float(self.__last_gps['longitude'])] if self.__last_gps['latitude'] != '-' else [0, 0]
            return render_template_string(HTML_PAGE, networks=all_networks, snoopers=snoopers, center=center)
        return "Not found.", 404

HTML_PAGE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SnoopR - Wardrived Networks</title>
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        table { width: 100%; border-collapse: collapse; }
        th, td { padding: 8px; text-align: left; border-bottom: 1px solid #ddd; }
        th { background-color: #f2f2f2; }
        .snooper { background-color: #ffcccc; }
        #map { height: 400px; margin-top: 20px; }
    </style>
</head>
<body>
    <h1>SnoopR - Wardrived Networks</h1>
    <table>
        <thead>
            <tr>
                <th>Device Type</th>
                <th>MAC Address</th>
                <th>Type</th>
                <th>Name</th>
                <th>First Seen</th>
                <th>Last Seen</th>
                <th># Sessions</th>
                <th>Snooper</th>
            </tr>
        </thead>
        <tbody>
            {% for network in networks %}
            <tr class="{{ 'snooper' if network.is_snooper else '' }}">
                <td>{{ network.device_type }}</td>
                <td>{{ network.mac }}</td>
                <td>{{ network.type }}</td>
                <td>{{ network.name }}</td>
                <td>{{ network.first_seen }}</td>
                <td>{{ network.last_seen }}</td>
                <td>{{ network.sessions_count }}</td>
                <td>{{ 'Yes' if network.is_snooper else 'No' }}</td>
            </tr>
            {% endfor %}
        </tbody>
    </table>
    <div id="map"></div>
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <script>
        var networks = {{ networks | tojson }};
        var center = {{ center | tojson }};
        var map = L.map('map').setView(center, 13);
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '© OpenStreetMap contributors'
        }).addTo(map);
        networks.forEach(function(network) {
            if (network.latitude && network.longitude) {
                var color = network.is_snooper ? 'red' : 'blue';
                L.circleMarker([network.latitude, network.longitude], {
                    color: color,
                    radius: 5
                }).addTo(map).bindPopup(
                    `Device Type: ${network.device_type}<br>MAC: ${network.mac}<br>Name: ${network.name}<br>Snooper: ${network.is_snooper ? 'Yes' : 'No'}`
                );
            }
        });
    </script>
</body>
</html>
'''
