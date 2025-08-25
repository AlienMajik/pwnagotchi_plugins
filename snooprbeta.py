import logging
import sqlite3
import os
from threading import Lock, Thread
from datetime import datetime, timedelta
import time
from math import radians, sin, cos, sqrt, atan2
import subprocess
import pwnagotchi.plugins as plugins
from pwnagotchi.ui.components import LabeledValue
from pwnagotchi.ui.view import BLACK
import pwnagotchi.ui.fonts as fonts
from flask import render_template_string, request, jsonify
import json
import socket
import select
import requests
import numpy as np
from scipy.optimize import least_squares

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
                device_type TEXT NOT NULL,
                is_snooper INTEGER DEFAULT 0,
                triangulated_lat TEXT,
                triangulated_lon TEXT
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
                channel INTEGER,
                auth_mode TEXT,
                timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(session_id) REFERENCES sessions(id),
                FOREIGN KEY(network_id) REFERENCES networks(id)
            )
        ''')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_detections_network_id ON detections(network_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_networks_mac ON networks(mac)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_detections_timestamp ON detections(timestamp)')
        cursor.execute("PRAGMA table_info(detections)")
        columns = [column[1] for column in cursor.fetchall()]
        if 'channel' not in columns:
            cursor.execute("ALTER TABLE detections ADD COLUMN channel INTEGER")
            logging.info('[SnoopR] Added "channel" column to detections table')
        if 'auth_mode' not in columns:
            cursor.execute("ALTER TABLE detections ADD COLUMN auth_mode TEXT")
            logging.info('[SnoopR] Added "auth_mode" column to detections table')
        cursor.execute("PRAGMA table_info(networks)")
        columns = [column[1] for column in cursor.fetchall()]
        if 'triangulated_lat' not in columns:
            cursor.execute("ALTER TABLE networks ADD COLUMN triangulated_lat TEXT")
            logging.info('[SnoopR] Added "triangulated_lat" column to networks table')
        if 'triangulated_lon' not in columns:
            cursor.execute("ALTER TABLE networks ADD COLUMN triangulated_lon TEXT")
            logging.info('[SnoopR] Added "triangulated_lon" column to networks table')
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

    def add_detection(self, session_id, mac, type_, name, device_type, encryption, signal_strength, latitude, longitude, channel, auth_mode):
        cursor = self.__connection.cursor()
        try:
            cursor.execute('SELECT id FROM networks WHERE mac = ? AND device_type = ?', (mac, device_type))
            result = cursor.fetchone()
            if result:
                network_id = result[0]
            else:
                cursor.execute('INSERT INTO networks (mac, type, name, device_type) VALUES (?, ?, ?, ?)', (mac, type_, name, device_type))
                network_id = cursor.lastrowid
            cursor.execute('''
                INSERT INTO detections (session_id, network_id, encryption, signal_strength, latitude, longitude, channel, auth_mode)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (session_id, network_id, encryption, signal_strength, latitude, longitude, channel, auth_mode))
            self.__connection.commit()
            logging.debug(f'[SnoopR] Added detection: {mac} ({device_type}) at {latitude},{longitude}')
            return network_id
        except Exception as e:
            logging.error(f'[SnoopR] Database error: {e}')
            raise
        finally:
            cursor.close()

    def add_detection_batch(self, detections):
        cursor = self.__connection.cursor()
        try:
            # Collect unique networks and map keys to ids
            net_map = {}
            for det in detections:
                mac, type_, name, device_type = det[0:4]
                key = (mac, device_type)
                if key not in net_map:
                    cursor.execute('SELECT id FROM networks WHERE mac = ? AND device_type = ?', key)
                    result = cursor.fetchone()
                    if result:
                        net_id = result[0]
                    else:
                        cursor.execute('INSERT INTO networks (mac, type, name, device_type) VALUES (?, ?, ?, ?)', (mac, type_, name, device_type))
                        net_id = cursor.lastrowid
                    net_map[key] = net_id
            # Prepare detection tuples
            det_tuples = []
            for det in detections:
                mac, type_, name, device_type, encryption, signal_strength, latitude, longitude, channel, auth_mode, session_id = det
                key = (mac, device_type)
                network_id = net_map[key]
                det_tuples.append((session_id, network_id, encryption, signal_strength, latitude, longitude, channel, auth_mode))
            cursor.executemany('''
                INSERT INTO detections (session_id, network_id, encryption, signal_strength, latitude, longitude, channel, auth_mode)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', det_tuples)
            self.__connection.commit()
            logging.debug(f'[SnoopR] Batch added {len(detections)} detections')
        except Exception as e:
            logging.error(f'[SnoopR] Batch database error: {e}')
            raise
        finally:
            cursor.close()

    def get_network_details(self, mac, device_type):
        cursor = self.__connection.cursor()
        try:
            cursor.execute('''
                SELECT n.mac, n.type, n.name, n.device_type, n.is_snooper,
                       COUNT(DISTINCT d.session_id) as sessions_count,
                       MIN(datetime(d.timestamp, 'localtime')) as first_seen, MAX(datetime(d.timestamp, 'localtime')) as last_seen,
                       n.triangulated_lat, n.triangulated_lon
                FROM networks n
                LEFT JOIN detections d ON n.id = d.network_id
                WHERE n.mac = ? AND n.device_type = ?
                GROUP BY n.id
            ''', (mac, device_type))
            network = cursor.fetchone()
            if not network:
                return None
            cursor.execute('''
                SELECT latitude, longitude, datetime(timestamp, 'localtime') as timestamp, signal_strength
                FROM detections d
                JOIN networks n ON d.network_id = n.id
                WHERE n.mac = ? AND n.device_type = ?
                ORDER BY d.timestamp
            ''', (mac, device_type))
            detections = cursor.fetchall()
            triangulated_lat = float(network[8]) if network[8] else None
            triangulated_lon = float(network[9]) if network[9] else None
            result = {
                'mac': network[0], 'type': network[1], 'name': network[2], 'device_type': network[3],
                'is_snooper': bool(network[4]), 'sessions_count': network[5],
                'first_seen': network[6], 'last_seen': network[7],
                'triangulated_latitude': triangulated_lat,
                'triangulated_longitude': triangulated_lon,
                'detections': [{'latitude': float(d[0]) if d[0] != '-' else None, 'longitude': float(d[1]) if d[1] != '-' else None,
                                'timestamp': d[2], 'signal_strength': d[3]} for d in detections]
            }
            return result
        finally:
            cursor.close()

    def get_all_networks(self, sort_by=None, filter_by=None, include_paths=False):
        cursor = self.__connection.cursor()
        try:
            query = '''
                SELECT n.mac, n.type, n.name, n.device_type, 
                       MIN(datetime(d.timestamp, 'localtime')) as first_seen, MIN(d.session_id) as first_session,
                       MAX(datetime(d.timestamp, 'localtime')) as last_seen, MAX(d.session_id) as last_session, 
                       COUNT(DISTINCT d.session_id) as sessions_count,
                       (SELECT latitude FROM detections dd WHERE dd.network_id = n.id ORDER BY dd.timestamp DESC LIMIT 1) as last_latitude,
                       (SELECT longitude FROM detections dd WHERE dd.network_id = n.id ORDER BY dd.timestamp DESC LIMIT 1) as last_longitude,
                       n.is_snooper, n.triangulated_lat, n.triangulated_lon
                FROM networks n
                JOIN detections d ON n.id = d.network_id
                WHERE 1=1
            '''
            if filter_by == 'snoopers':
                query += ' AND n.is_snooper = 1'
            elif filter_by == 'bluetooth':
                query += ' AND n.device_type = "bluetooth"'
            elif filter_by == 'aircraft':
                query += ' AND n.device_type = "aircraft"'
            elif filter_by == 'clients':
                query += ' AND n.type = "wi-fi client"'
            query += ' GROUP BY n.id'
            if sort_by == 'device_type':
                query += ' ORDER BY n.device_type'
            elif sort_by == 'is_snooper':
                query += ' ORDER BY n.is_snooper DESC'
            cursor.execute(query)
            rows = cursor.fetchall()
            networks = []
            for row in rows:
                mac, type_, name, device_type, first_seen, first_session, last_seen, last_session, sessions_count, last_latitude, last_longitude, is_snooper, triangulated_lat, triangulated_lon = row
                lat = float(triangulated_lat) if triangulated_lat else (float(last_latitude) if last_latitude and last_latitude != '-' else None)
                lon = float(triangulated_lon) if triangulated_lon else (float(last_longitude) if last_longitude and last_longitude != '-' else None)
                networks.append({
                    'mac': mac, 'type': type_, 'name': name, 'device_type': device_type,
                    'first_seen': first_seen, 'first_session': first_session,
                    'last_seen': last_seen, 'last_session': last_session,
                    'sessions_count': sessions_count,
                    'latitude': lat,
                    'longitude': lon,
                    'is_snooper': bool(is_snooper)
                })
            if include_paths or filter_by == 'snoopers':
                for net in networks:
                    cursor.execute('''
                        SELECT latitude, longitude, datetime(timestamp, 'localtime') as timestamp, signal_strength 
                        FROM detections 
                        WHERE network_id = (SELECT id FROM networks WHERE mac=? AND device_type=?) 
                        ORDER BY timestamp
                    ''', (net['mac'], net['device_type']))
                    dets = cursor.fetchall()
                    net['path'] = [{
                        'latitude': float(d[0]) if d[0] != '-' else None,
                        'longitude': float(d[1]) if d[1] != '-' else None,
                        'timestamp': d[2],
                        'signal_strength': d[3]
                    } for d in dets if d[0] != '-' and d[1] != '-']
            logging.debug(f'[SnoopR] Web UI networks: {len(networks)} entries, first: {networks[0] if networks else "None"}')
            return networks
        except Exception as e:
            logging.error(f'[SnoopR] get_all_networks error: {e}')
            return []
        finally:
            cursor.close()

    def network_count(self, device_type=None):
        cursor = self.__connection.cursor()
        try:
            if device_type:
                cursor.execute('SELECT COUNT(DISTINCT mac) FROM networks WHERE device_type = ?', (device_type,))
            else:
                cursor.execute('SELECT COUNT(DISTINCT mac) FROM networks')
            count = cursor.fetchone()[0]
            return count
        finally:
            cursor.close()

    def snooper_count(self, device_type=None):
        cursor = self.__connection.cursor()
        try:
            if device_type:
                cursor.execute('SELECT COUNT(*) FROM networks WHERE is_snooper = 1 AND device_type = ?', (device_type,))
            else:
                cursor.execute('SELECT COUNT(*) FROM networks WHERE is_snooper = 1')
            count = cursor.fetchone()[0]
            return count
        finally:
            cursor.close()

    def update_snooper_status(self, mac, device_type, is_snooper):
        cursor = self.__connection.cursor()
        try:
            cursor.execute('UPDATE networks SET is_snooper = ? WHERE mac = ? AND device_type = ?', (is_snooper, mac, device_type))
            self.__connection.commit()
        finally:
            cursor.close()

    def update_triangulated_position(self, mac, device_type, lat, lon):
        cursor = self.__connection.cursor()
        try:
            cursor.execute('UPDATE networks SET triangulated_lat = ?, triangulated_lon = ? WHERE mac = ? AND device_type = ?', (lat, lon, mac, device_type))
            self.__connection.commit()
        finally:
            cursor.close()

    def prune_old_data(self, days):
        cursor = self.__connection.cursor()
        try:
            cutoff_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d %H:%M:%S')
            cursor.execute('DELETE FROM detections WHERE timestamp < ?', (cutoff_date,))
            cursor.execute('DELETE FROM sessions WHERE id NOT IN (SELECT DISTINCT session_id FROM detections)')
            cursor.execute('DELETE FROM networks WHERE id NOT IN (SELECT DISTINCT network_id FROM detections)')
            self.__connection.commit()
            cursor.execute('VACUUM')
            logging.info(f'[SnoopR] Pruned data older than {days} days and vacuumed database')
        finally:
            cursor.close()

class MeshNetwork:
    def __init__(self, host_ip, port, peers):
        self.host_ip = host_ip
        self.port = port
        self.peers = peers
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.bind((host_ip, port))
        self.socket.setblocking(False)

    def broadcast_detection(self, detection):
        data = json.dumps(detection).encode('utf-8')
        for peer in self.peers:
            try:
                self.socket.sendto(data, (peer, self.port))
            except Exception as e:
                logging.error(f'[SnoopR] Failed to send to {peer}: {e}')

    def receive_detections(self, db):
        ready, _, _ = select.select([self.socket], [], [], 0.1)
        if ready:
            data, _ = self.socket.recvfrom(4096)
            detection = json.loads(data.decode('utf-8'))
            db.add_detection_batch([(
                detection['mac'], detection['type'], detection['name'], detection['device_type'],
                detection['encryption'], detection['signal_strength'], detection['latitude'],
                detection['longitude'], detection['channel'], detection['auth_mode'], detection['session_id']
            )])
            logging.debug(f'[SnoopR] Received mesh detection: {detection["mac"]}')

    def close(self):
        self.socket.close()

class SnoopR(plugins.Plugin):
    __author__ = 'AlienMajik'
    __version__ = '2.4.0'
    __license__ = 'GPL3'
    __description__ = 'Enhanced wardriving plugin with robust GPS/Bluetooth/Wi-Fi and SkyHigh integration, including aircraft tracking, Wi-Fi client detection, paths for snoopers, triangulation for precise locations, and exports.'
    DEFAULT_PATH = '/root/snoopr'
    DATABASE_NAME = 'snoopr.db'

    def __init__(self):
        self.__db = None
        self.ready = False
        self.__gps_available = True
        self.__lock = Lock()
        self.__last_gps = {'latitude': '-', 'longitude': '-', 'altitude': '-'}
        self.__last_valid_gps = None
        self.__session_id = None
        self.__bluetooth_enabled = False
        self.last_scan_time = 0
        self.__whitelist = []
        self.__whitelist_macs = []
        self.prune_days = 30
        self.__mesh = None
        self.__ap_batch = []
        self.__recent_aircraft = {}

    def on_loaded(self):
        logging.info('[SnoopR] Plugin loaded.')
        self.__path = self.options.get('path', self.DEFAULT_PATH)
        self.__ui_enabled = self.options.get('ui', {}).get('enabled', True)
        self.__gps_config = {'method': self.options.get('gps', {}).get('method', 'bettercap')}
        self.movement_threshold = self.options.get('movement_threshold', 0.1)
        self.time_threshold_minutes = self.options.get('time_threshold_minutes', 5)
        self.__bluetooth_enabled = self.options.get('bluetooth_enabled', False)
        self.timer = self.options.get('timer', 45)
        self.__whitelist = self.options.get('whitelist', [])
        self.__whitelist_macs = self.options.get('whitelist_macs', [])
        self.prune_days = self.options.get('prune_days', 30)
        self.mesh_enabled = self.options.get('mesh_enabled', False)
        self.mesh_host_ip = self.options.get('mesh_host_ip', '192.168.1.1')
        self.mesh_port = self.options.get('mesh_port', 9999)
        self.mesh_peers = self.options.get('mesh_peers', [])
        self.aircraft_file = self.options.get('aircraft_file', '/root/handshakes/skyhigh_aircraft.json')
        self.log_without_gps = self.options.get('log_without_gps', True)
        if not os.path.exists(self.__path):
            os.makedirs(self.__path)
        self.__db = Database(os.path.join(self.__path, self.DATABASE_NAME))
        self.__session_id = self.__db.new_session()
        self.__db.prune_old_data(self.prune_days)
        if self.mesh_enabled:
            try:
                self.__mesh = MeshNetwork(self.mesh_host_ip, self.mesh_port, self.mesh_peers)
            except Exception as e:
                logging.error(f'[SnoopR] Mesh setup failed: {e}')
                self.__mesh = None
        self.ready = True

    def on_ui_setup(self, ui):
        if self.__ui_enabled:
            ui.add_element('snoopr_wifi_networks', LabeledValue(
                color=BLACK, label='WiFi Nets:', value='0', position=(7, 95),
                label_font=fonts.Small, text_font=fonts.Small))
            ui.add_element('snoopr_wifi_snoopers', LabeledValue(
                color=BLACK, label='WiFi Snoopers:', value='0', position=(7, 105),
                label_font=fonts.Small, text_font=fonts.Small))
            ui.add_element('snoopr_last_scan', LabeledValue(
                color=BLACK, label='Last Scan:', value='N/A', position=(7, 135),
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
                Thread(target=self.on_bluetooth_scan).start()
            if self.mesh_enabled and self.__mesh:
                self.__mesh.receive_detections(self.__db)
            if os.path.exists(self.aircraft_file):
                try:
                    with open(self.aircraft_file, 'r') as f:
                        aircraft = json.load(f)
                    if isinstance(aircraft, dict):
                        aircraft_data = list(aircraft.values())
                        logging.debug(f'[SnoopR] Aircraft loaded: {len(aircraft_data)} entries, first: {aircraft_data[0] if aircraft_data else "None"}')
                    elif not isinstance(aircraft, list):
                        logging.warning(f"[SnoopR] Invalid aircraft file format: {type(aircraft)}")
                        aircraft_data = []
                    else:
                        aircraft_data = aircraft
                    for plane in aircraft_data:
                        if not isinstance(plane, dict):
                            logging.warning(f"[SnoopR] Invalid aircraft entry: {plane}")
                            continue
                        icao = plane.get('icao24', 'UNKNOWN')
                        callsign = plane.get('callsign', 'UNKNOWN').strip()
                        lat = plane.get('latitude')
                        lon = plane.get('longitude')
                        is_drone = plane.get('is_drone', False)
                        altitude = plane.get('alt', 10000)
                        if icao not in self.__recent_aircraft:
                            self.__recent_aircraft[icao] = {'last_seen': current_time, 'positions': [], 'snooper': is_drone}
                        self.__recent_aircraft[icao]['positions'].append((lat, lon, current_time, altitude))
                        self.__recent_aircraft[icao]['last_seen'] = current_time
                        # Log aircraft detection to database
                        if lat not in (None, 'N/A') and lon not in (None, 'N/A'):
                            try:
                                network_id = self.__db.add_detection(
                                    self.__session_id, icao, 'aircraft', callsign, 'aircraft', '', 0,
                                    str(lat), str(lon), 0, ''
                                )
                                self.check_aircraft_snooper_status(icao, 'aircraft')
                            except Exception as e:
                                logging.error(f'[SnoopR] Failed to log aircraft detection: {e}')
                        # Proximity alert
                        if self.__last_gps['latitude'] != '-' and lat not in (None, 'N/A') and lon not in (None, 'N/A'):
                            try:
                                dist = self.__calculate_distance(
                                    float(self.__last_gps['latitude']), float(self.__last_gps['longitude']),
                                    float(lat), float(lon)
                                )
                                if dist < 5 and (icao not in self.__recent_aircraft or current_time - self.__recent_aircraft[icao]['last_seen'] > 60):
                                    alert_type = 'Drone' if is_drone else 'Aircraft'
                                    snooper_flag = 'Snooper ' if self.__recent_aircraft[icao]['snooper'] else ''
                                    logging.critical(f"[SnoopR] {snooper_flag}{alert_type} {icao} ({callsign}) detected {dist:.2f} miles away!")
                                    self.__notify(f"{snooper_flag}{alert_type} {icao} ({callsign}) {dist:.2f}mi away!")
                                    self.__recent_aircraft[icao]['last_seen'] = current_time
                            except (ValueError, TypeError) as e:
                                logging.warning(f"[SnoopR] Invalid aircraft coords: {e}")
                    self.__recent_aircraft = {k: v for k, v in self.__recent_aircraft.items() if current_time - v['last_seen'] < 3600}
                except Exception as e:
                    logging.error(f"[SnoopR] Failed to process aircraft file: {e}")
            ui.set('snoopr_wifi_networks', str(self.__db.network_count('wifi')))
            ui.set('snoopr_wifi_snoopers', str(self.__db.snooper_count('wifi')))
            if self.last_scan_time == 0:
                ui.set('snoopr_last_scan', 'N/A')
            else:
                ui.set('snoopr_last_scan', datetime.fromtimestamp(self.last_scan_time).strftime('%H:%M:%S'))
            if self.__bluetooth_enabled:
                ui.set('snoopr_bt_networks', str(self.__db.network_count('bluetooth')))
                ui.set('snoopr_bt_snoopers', str(self.__db.snooper_count('bluetooth')))

    def on_unload(self, ui):
        if self.__ui_enabled:
            with ui._lock:
                ui.remove_element('snoopr_wifi_networks')
                ui.remove_element('snoopr_wifi_snoopers')
                ui.remove_element('snoopr_last_scan')
                if self.__bluetooth_enabled:
                    ui.remove_element('snoopr_bt_networks')
                    ui.remove_element('snoopr_bt_snoopers')
        self.__db.disconnect()
        if self.mesh_enabled and self.__mesh:
            self.__mesh.close()
        logging.info('[SnoopR] Plugin unloaded')

    def __get_gps(self, agent):
        if agent is None:
            logging.warning('[SnoopR] Agent is None, cannot fetch new GPS from bettercap. Using last valid GPS if available.')
            return self.__last_valid_gps
        for attempt in range(5):
            try:
                time.sleep(5)  # Increased delay for bettercap API
                info = agent.session()
                gps_data = info.get('gps', None)
                if gps_data and gps_data.get('Latitude') and gps_data.get('Longitude'):
                    logging.debug(f'[SnoopR] Bettercap GPS acquired: {gps_data["Latitude"]}, {gps_data["Longitude"]}')
                    self.__last_valid_gps = gps_data
                    return gps_data
            except Exception as e:
                logging.warning(f'[SnoopR] Bettercap GPS failed (attempt {attempt + 1}/5): {e}')
        logging.warning('[SnoopR] No GPS data after retries')
        return self.__last_valid_gps if self.__last_valid_gps else None

    def on_unfiltered_ap_list(self, agent, aps):
        if not self.ready:
            return
        with self.__lock:
            gps_data = self.__get_gps(agent)
            if gps_data and all([gps_data['Latitude'], gps_data['Longitude']]):
                self.__last_gps = {
                    'latitude': gps_data['Latitude'],
                    'longitude': gps_data['Longitude'],
                    'altitude': gps_data['Altitude'] or '-'
                }
                coordinates = {'latitude': str(gps_data['Latitude']), 'longitude': str(gps_data['Longitude'])}
            else:
                coordinates = {'latitude': '-', 'longitude': '-'}
            self.__ap_batch = []
            for ap in aps:
                mac = ap['mac']
                if mac in self.__whitelist_macs:
                    logging.debug(f'[SnoopR] Skipping whitelisted MAC: {mac}')
                    continue
                ssid = ap['hostname'] if ap['hostname'] != '<hidden>' else ''
                if ssid in self.__whitelist:
                    logging.debug(f'[SnoopR] Skipping whitelisted AP: {ssid}')
                    continue
                encryption = f"{ap['encryption']}{ap.get('cipher', '')}{ap.get('authentication', '')}"
                rssi = ap['rssi']
                channel = ap.get('channel', 0)
                auth_mode = ap.get('authentication', '')
                self.__ap_batch.append((
                    mac, 'wi-fi ap', ssid, 'wifi', encryption, rssi,
                    coordinates['latitude'], coordinates['longitude'], channel, auth_mode, self.__session_id
                ))
                logging.info(f'[SnoopR] Detected Wi-Fi AP: {mac} ({ssid}) at {coordinates["latitude"]},{coordinates["longitude"]}')
                self.check_and_update_snooper_status(mac, 'wifi')
                # Add clients
                if 'clients' in ap:
                    for client in ap['clients']:
                        client_mac = client if isinstance(client, str) else client.get('mac')
                        if not client_mac:
                            continue
                        if client_mac in self.__whitelist_macs:
                            logging.debug(f'[SnoopR] Skipping whitelisted client MAC: {client_mac}')
                            continue
                        client_name = '' if isinstance(client, str) else client.get('hostname', '')
                        client_rssi = rssi if isinstance(client, str) else client.get('rssi', rssi)
                        self.__ap_batch.append((
                            client_mac, 'wi-fi client', client_name, 'wifi', encryption, client_rssi,
                            coordinates['latitude'], coordinates['longitude'], channel, auth_mode, self.__session_id
                        ))
                        logging.info(f'[SnoopR] Detected Wi-Fi Client: {client_mac} at {coordinates["latitude"]},{coordinates["longitude"]}')
                        self.check_and_update_snooper_status(client_mac, 'wifi')
            if self.__ap_batch:
                try:
                    self.__db.add_detection_batch(self.__ap_batch)
                    logging.info(f'[SnoopR] Saved {len(self.__ap_batch)} Wi-Fi detections')
                    if self.mesh_enabled and self.__mesh:
                        for detection in self.__ap_batch:
                            self.__mesh.broadcast_detection({
                                'mac': detection[0], 'type': detection[1], 'name': detection[2],
                                'device_type': detection[3], 'encryption': detection[4], 'signal_strength': detection[5],
                                'latitude': detection[6], 'longitude': detection[7], 'channel': detection[8],
                                'auth_mode': detection[9], 'session_id': detection[10]
                            })
                except Exception as e:
                    logging.error(f'[SnoopR] Failed to save Wi-Fi batch: {e}')

    def on_bluetooth_scan(self):
        if not self.ready or not self.__bluetooth_enabled:
            logging.debug('[SnoopR] Bluetooth scan skipped: not ready or disabled')
            return
        with self.__lock:
            gps_data = self.__get_gps(None)
            if gps_data and all([gps_data['Latitude'], gps_data['Longitude']]):
                self.__last_gps = {
                    'latitude': gps_data['Latitude'],
                    'longitude': gps_data['Longitude'],
                    'altitude': gps_data['Altitude'] or '-'
                }
                coordinates = {'latitude': str(gps_data['Latitude']), 'longitude': str(gps_data['Longitude'])}
            else:
                if not self.log_without_gps:
                    logging.warning("[SnoopR] No valid GPS data available, skipping Bluetooth scan.")
                    return
                coordinates = {'latitude': '-', 'longitude': '-'}
            for attempt in range(3):
                try:
                    logging.debug(f'[SnoopR] Attempting Bluetooth scan (attempt {attempt + 1}/3)')
                    cmd_inq = "hcitool inq --flush"
                    inq_output = subprocess.check_output(cmd_inq.split(), stderr=subprocess.STDOUT).decode().splitlines()
                    for line in inq_output[1:]:
                        fields = line.split()
                        if len(fields) < 1:
                            continue
                        mac_address = fields[0]
                        if mac_address in self.__whitelist_macs:
                            logging.debug(f'[SnoopR] Skipping whitelisted Bluetooth MAC: {mac_address}')
                            continue
                        name = self.get_device_name(mac_address)
                        if name in self.__whitelist:
                            logging.debug(f'[SnoopR] Skipping whitelisted Bluetooth: {name}')
                            continue
                        network_id = self.__db.add_detection(
                            self.__session_id, mac_address, 'bluetooth', name, 'bluetooth', '', 0,
                            coordinates['latitude'], coordinates['longitude'], 0, ''
                        )
                        self.check_and_update_snooper_status(mac_address, 'bluetooth')
                        logging.info(f'[SnoopR] Logged Bluetooth device: {mac_address} ({name}) at {coordinates["latitude"]},{coordinates["longitude"]}')
                    break  # Exit loop on success
                except subprocess.CalledProcessError as e:
                    logging.error(f"[SnoopR] hcitool scan failed (attempt {attempt + 1}/3): {e.output.decode()}")
                    if attempt < 2:
                        time.sleep(1)
                        continue
                    logging.error("[SnoopR] Bluetooth scan failed after 3 attempts")
                    self.__notify("Bluetooth scan failed!")

    def get_device_name(self, mac_address):
        for attempt in range(3):
            try:
                cmd_name = f"hcitool name {mac_address}"
                name_output = subprocess.check_output(cmd_name.split(), stderr=subprocess.STDOUT).decode().strip()
                return name_output if name_output else 'Unknown'
            except subprocess.CalledProcessError:
                if attempt < 2:
                    time.sleep(1)
                    continue
                logging.warning(f"[SnoopR] Failed to get name for {mac_address} after 3 attempts")
                return 'Unknown'

    def estimate_position(self, detections):
        positions = []
        distances = []
        for lat, lon, rssi in detections:
            if lat is not None and lon is not None and rssi is not None:
                positions.append([lat, lon])
                # RSSI to distance (miles); TxPower=20 dBm, n=3 (urban), freq=2400 MHz
                dist = 10 ** ((20 - rssi - 32.44 - 20 * np.log10(2400)) / (10 * 3)) / 1609.34
                distances.append(dist)
        if len(positions) < 3:
            return None
        positions = np.array(positions)
        distances = np.array(distances)
        
        def residuals(x):
            return np.linalg.norm(positions - x, axis=1) - distances
        
        initial_guess = np.mean(positions, axis=0)
        result = least_squares(residuals, initial_guess)
        return result.x  # [lat, lon]

    def check_and_update_snooper_status(self, mac, device_type):
        cursor = self.__db._Database__connection.cursor()
        try:
            cursor.execute('''
                SELECT d.latitude, d.longitude, d.timestamp, d.signal_strength
                FROM detections d
                JOIN networks n ON d.network_id = n.id
                WHERE n.mac = ? AND n.device_type = ?
                ORDER BY d.timestamp
            ''', (mac, device_type))
            rows = cursor.fetchall()
            cursor.execute('SELECT COUNT(DISTINCT session_id) FROM detections d JOIN networks n ON d.network_id = n.id WHERE n.mac = ? AND n.device_type = ?', (mac, device_type))
            session_count = cursor.fetchone()[0]
            if len(rows) < 3 or session_count < 2:
                return
            is_snooper = False
            for i in range(1, len(rows)):
                lat1, lon1, t1, _ = rows[i-1]
                lat2, lon2, t2, _ = rows[i]
                if lat1 == '-' or lon1 == '-' or lat2 == '-' or lon2 == '-':
                    continue
                lat1, lon1, lat2, lon2 = map(float, [lat1, lon1, lat2, lon2])
                t1 = datetime.strptime(t1, '%Y-%m-%d %H:%M:%S')
                t2 = datetime.strptime(t2, '%Y-%m-%d %H:%M:%S')
                time_diff = (t2 - t1).total_seconds() / 60.0
                if time_diff > self.time_threshold_minutes:
                    dist = self.__calculate_distance(lat1, lon1, lat2, lon2)
                    velocity = (dist * 1609.34) / (time_diff * 60)
                    if dist > self.movement_threshold or velocity > 1.5:
                        is_snooper = True
                        break
            self.__db.update_snooper_status(mac, device_type, int(is_snooper))
            # Triangulation for Wi-Fi and Bluetooth (skip aircraft)
            if device_type in ['wifi', 'bluetooth']:
                valid_dets = [(float(r[0]) if r[0] != '-' else None, float(r[1]) if r[1] != '-' else None, r[3]) for r in rows]
                triangulated = self.estimate_position([(d[0], d[1], d[2]) for d in valid_dets if d[0] is not None and d[1] is not None and d[2] is not None])
                if triangulated is not None:
                    self.__db.update_triangulated_position(mac, device_type, str(triangulated[0]), str(triangulated[1]))
        finally:
            cursor.close()

    def check_aircraft_snooper_status(self, icao, device_type):
        cursor = self.__db._Database__connection.cursor()
        try:
            cursor.execute('''
                SELECT d.latitude, d.longitude, d.timestamp, d.signal_strength
                FROM detections d
                JOIN networks n ON d.network_id = n.id
                WHERE n.mac = ? AND n.device_type = ?
                ORDER BY d.timestamp
            ''', (icao, device_type))
            rows = cursor.fetchall()
            cursor.execute('SELECT COUNT(DISTINCT session_id) FROM detections d JOIN networks n ON d.network_id = n.id WHERE n.mac = ? AND n.device_type = ?', (icao, device_type))
            session_count = cursor.fetchone()[0]
            if len(rows) < 3 or session_count < 2:
                return
            is_snooper = False
            for i in range(1, len(rows)):
                lat1, lon1, t1, _ = rows[i-1]
                lat2, lon2, t2, _ = rows[i]
                if lat1 == '-' or lon1 == '-' or lat2 == '-' or lon2 == '-':
                    continue
                lat1, lon1, lat2, lon2 = map(float, [lat1, lon1, lat2, lon2])
                t1 = datetime.strptime(t1, '%Y-%m-%d %H:%M:%S')
                t2 = datetime.strptime(t2, '%Y-%m-%d %H:%M:%S')
                time_diff = (t2 - t1).total_seconds() / 3600.0  # Hours for aircraft
                if time_diff > self.time_threshold_minutes / 60.0:
                    dist = self.__calculate_distance(lat1, lon1, lat2, lon2)
                    velocity = (dist * 1609.34) / (time_diff * 3600)  # mph
                    if dist < 5 and velocity < 50:  # Loitering or slow-moving
                        is_snooper = True
                        break
            self.__db.update_snooper_status(icao, device_type, int(is_snooper))
            # Optional triangulation for aircraft if desired (using same method)
            valid_dets = [(float(r[0]) if r[0] != '-' else None, float(r[1]) if r[1] != '-' else None, r[3]) for r in rows]
            triangulated = self.estimate_position([(d[0], d[1], d[2]) for d in valid_dets if d[0] is not None and d[1] is not None and d[2] is not None])
            if triangulated is not None:
                self.__db.update_triangulated_position(icao, device_type, str(triangulated[0]), str(triangulated[1]))
        finally:
            cursor.close()

    def __calculate_distance(self, lat1, lon1, lat2, lon2):
        R = 3958.8
        lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
        c = 2 * atan2(sqrt(a), sqrt(1-a))
        return R * c

    def __notify(self, message):
        logging.info(f"[SnoopR] Notification: {message}")

    def on_webhook(self, path, request):
        if request.method == 'GET':
            sort_by = request.args.get('sort_by', None)
            filter_by = request.args.get('filter_by', None)
            if path == 'network':
                mac = request.args.get('mac')
                device_type = request.args.get('device_type')
                if mac and device_type:
                    details = self.__db.get_network_details(mac, device_type)
                    return jsonify(details) if details else ("Not found.", 404)
            elif path == 'export_csv':
                all_networks = self.__db.get_all_networks()
                headers = ['mac', 'type', 'name', 'device_type', 'first_seen', 'last_seen', 'sessions_count', 'is_snooper', 'last_latitude', 'last_longitude']
                csv_lines = [','.join(headers)]
                for net in all_networks:
                    line = [str(net.get(h, '')) for h in headers]
                    csv_lines.append(','.join(line))
                return '\n'.join(csv_lines), 200, {'Content-Type': 'text/csv; charset=utf-8', 'Content-Disposition': 'attachment; filename=snoopr_networks.csv'}
            elif path == 'export_kml':
                all_networks = self.__db.get_all_networks(include_paths=True)
                kml = '''<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
<Document>
'''
                for net in all_networks:
                    if net['latitude'] is not None and net['longitude'] is not None:
                        kml += f'''<Placemark>
<name>{net['name']} ({net['mac']})</name>
<description>Device Type: {net['device_type']}\nSnooper: {'Yes' if net['is_snooper'] else 'No'}\nSessions: {net['sessions_count']}\nFirst Seen: {net['first_seen']}\nLast Seen: {net['last_seen']}</description>
<Point>
<coordinates>{net['longitude']},{net['latitude']},0</coordinates>
</Point>
</Placemark>
'''
                    if 'path' in net and len(net['path']) > 1:
                        coords = ' '.join([f"{p['longitude']},{p['latitude']},0" for p in net['path'] if p['latitude'] is not None and p['longitude'] is not None])
                        if coords:
                            kml += f'''<Placemark>
<name>Path for {net['mac']}</name>
<LineString>
<coordinates>{coords}</coordinates>
</LineString>
</Placemark>
'''
                kml += '</Document></kml>'
                return kml, 200, {'Content-Type': 'application/vnd.google-earth.kml+xml', 'Content-Disposition': 'attachment; filename=snoopr.kml'}
            if path == '/' or not path:
                all_networks = self.__db.get_all_networks(sort_by=sort_by, filter_by=filter_by, include_paths=(filter_by == 'snoopers'))
                snoopers = [n for n in all_networks if n['is_snooper']]
                center = [float(self.__last_gps['latitude']), float(self.__last_gps['longitude'])] if self.__last_gps['latitude'] != '-' else [37.7177, -122.4393]
                
                # Add aircraft to map
                aircraft_markers = []
                if os.path.exists(self.aircraft_file):
                    try:
                        with open(self.aircraft_file, 'r') as f:
                            aircraft = json.load(f)
                        if isinstance(aircraft, dict):
                            aircraft_data = list(aircraft.values())
                        else:
                            aircraft_data = aircraft if isinstance(aircraft, list) else []
                        for plane in aircraft_data:
                            if plane.get('latitude') and plane.get('longitude'):
                                icao = plane.get('icao24', 'UNKNOWN')
                                is_snooper = self.__recent_aircraft.get(icao, {}).get('snooper', plane.get('is_drone', False))
                                aircraft_markers.append({
                                    'mac': icao,
                                    'type': 'aircraft',
                                    'name': plane.get('callsign', 'UNKNOWN').strip(),
                                    'device_type': 'aircraft',
                                    'first_seen': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                                    'first_session': self.__session_id,
                                    'last_seen': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                                    'last_session': self.__session_id,
                                    'sessions_count': 1,
                                    'latitude': float(plane['latitude']),
                                    'longitude': float(plane['longitude']),
                                    'is_snooper': is_snooper
                                })
                    except Exception as e:
                        logging.error(f'[SnoopR] Failed to load aircraft for map: {e}')
                all_networks.extend(aircraft_markers)
                
                # Add paths for aircraft snoopers
                if filter_by == 'snoopers':
                    for net in all_networks:
                        if net['device_type'] == 'aircraft':
                            icao = net['mac']
                            if icao in self.__recent_aircraft:
                                pos = self.__recent_aircraft[icao]['positions']
                                net['path'] = [{'latitude': p[0], 'longitude': p[1], 'timestamp': datetime.fromtimestamp(p[2]).strftime('%Y-%m-%d %H:%M:%S'), 'signal_strength': 0} for p in pos if p[0] is not None and p[1] is not None]
                
                logging.debug(f'[SnoopR] Web UI center: {center}, networks: {len(all_networks)}')
                return render_template_string(HTML_PAGE, networks=all_networks, snoopers=snoopers, center=center, sort_by=sort_by, filter_by=filter_by)
        return "Not found.", 404

HTML_PAGE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SnoopR - Wardrived Networks & Aircraft</title>
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        table { width: 100%; border-collapse: collapse; }
        th, td { padding: 8px; text-align: left; border-bottom: 1px solid #ddd; cursor: pointer; }
        th { background-color: #f2f2f2; }
        .snooper { background-color: #ffcccc; }
        #map { height: 400px; margin-top: 20px; }
        .filter-container { margin-bottom: 20px; }
        .filter-btn { padding: 5px 10px; margin-right: 10px; cursor: pointer; }
        .filter-btn.active { background-color: #4CAF50; color: white; }
        #scroll-to-top-button, #scroll-to-bottom-button {
            position: fixed;
            left: 50%;
            transform: translateX(-50%);
            padding: 5px 10px;
            background-color: #4CAF50;
            color: white;
            border: none;
            cursor: pointer;
            z-index: 1000;
        }
        #scroll-to-top-button { top: 10px; }
        #scroll-to-bottom-button { bottom: 10px; }
    </style>
</head>
<body>
    <button id="scroll-to-top-button">Scroll to Top</button>
    <h1>SnoopR - Wardrived Networks & Aircraft</h1>
    <div class="filter-container">
        <button class="filter-btn active" onclick="toggleFilter('all')">All</button>
        <button class="filter-btn" onclick="toggleFilter('snoopers')">Snoopers</button>
        <button class="filter-btn" onclick="toggleFilter('bluetooth')">Bluetooth</button>
        <button class="filter-btn" onclick="toggleFilter('aircraft')">Aircraft</button>
        <button class="filter-btn" onclick="toggleFilter('clients')">Wi-Fi Clients</button>
    </div>
    <div style="margin-bottom: 20px;">
        <a href="/export_csv" download>Export to CSV</a> |
        <a href="/export_kml" download>Export to KML</a>
    </div>
    <table>
        <thead>
            <tr>
                <th><a href="?sort_by=device_type&filter_by={{ filter_by }}">Device Type</a></th>
                <th>MAC/ICAO24</th>
                <th>Type</th>
                <th>Name/Callsign</th>
                <th>First Seen</th>
                <th>Last Seen</th>
                <th># Sessions</th>
                <th><a href="?sort_by=is_snooper&filter_by={{ filter_by }}">Snooper</a></th>
            </tr>
        </thead>
        <tbody>
            {% for network in networks %}
            <tr onclick="panToNetwork({{ network.latitude | default(center[0]) }}, {{ network.longitude | default(center[1]) }})" class="{{ 'snooper' if network.is_snooper else '' }}">
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
    <button id="scroll-to-bottom-button">Scroll to Bottom</button>
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <script>
        var networks = {{ networks | tojson }};
        var center = {{ center | tojson }};
        console.log('Networks:', networks);
        console.log('Center:', center);
        var map = L.map('map').setView(center, 13);
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '© OpenStreetMap contributors'
        }).addTo(map);
        var markers = [];
        networks.forEach(function(network) {
            var lat = network.latitude !== null ? network.latitude : center[0];
            var lon = network.longitude !== null ? network.longitude : center[1];
            var isNoCoords = network.latitude === null || network.longitude === null;
            var color = network.is_snooper ? 'red' : (network.device_type === 'aircraft' ? 'green' : (isNoCoords ? 'gray' : 'blue'));
            var marker = L.circleMarker([lat, lon], {
                color: color,
                radius: network.device_type === 'aircraft' ? 8 : 5
            }).bindPopup(
                `<b>Device Type:</b> ${network.device_type}<br>
                 <b>${network.device_type === 'aircraft' ? 'ICAO24' : 'MAC'}:</b> ${network.mac}<br>
                 <b>${network.device_type === 'aircraft' ? 'Callsign' : 'Name'}:</b> ${network.name}<br>
                 <b>Snooper:</b> ${network.is_snooper ? 'Yes' : 'No'}<br>
                 <b>First Seen:</b> ${network.first_seen}<br>
                 <b>Last Seen:</b> ${network.last_seen}<br>
                 <b>Sessions:</b> ${network.sessions_count}<br>
                 <b>Coords:</b> ${isNoCoords ? 'Unknown (plotted at center)' : lat + ', ' + lon}`
            );
            markers.push({marker: marker, network: network});
            marker.addTo(map);
            if (network.path && network.path.length > 1) {
                var pathCoords = network.path.map(p => [p.latitude, p.longitude]).filter(c => c[0] !== null && c[1] !== null);
                if (pathCoords.length > 1) {
                    L.polyline(pathCoords, {color: network.is_snooper ? 'red' : 'blue'}).addTo(map);
                }
            }
        });
        function panToNetwork(lat, lon) {
            if (lat && lon) {
                map.panTo([lat, lon]);
            }
        }
        document.getElementById('scroll-to-top-button').addEventListener('click', function() {
            window.scrollTo({top: 0, behavior: 'smooth'});
        });
        document.getElementById('scroll-to-bottom-button').addEventListener('click', function() {
            window.scrollTo({top: document.body.scrollHeight, behavior: 'smooth'});
        });
        var currentFilter = '{{ filter_by or "all" }}';
        document.querySelectorAll('.filter-btn').forEach(btn => {
            if (btn.textContent.toLowerCase().includes(currentFilter)) {
                btn.classList.add('active');
            }
        });
        function toggleFilter(filter) {
            if (currentFilter === filter) return;
            currentFilter = filter;
            document.querySelectorAll('.filter-btn').forEach(btn => {
                btn.classList.remove('active');
                if (btn.textContent.toLowerCase().includes(filter)) {
                    btn.classList.add('active');
                }
            });
            window.location.href = `?filter_by=${filter}&sort_by={{ sort_by }}`;
        }
        var bounds = [];
        networks.forEach(function(network) {
            if (network.latitude !== null && network.longitude !== null) {
                bounds.push([network.latitude, network.longitude]);
            }
        });
        if (bounds.length > 0) {
            map.fitBounds(bounds);
        } else {
            map.setView(center, 13);
        }
    </script>
</body>
</html>
'''