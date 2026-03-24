#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
import sqlite3
import os
import json
import time
import threading
import requests
import socket
import base64
import hashlib
from threading import Lock
from datetime import datetime, timedelta
from math import radians, sin, cos, sqrt, atan2, exp, radians as rad
import asyncio
from collections import defaultdict, deque
from functools import wraps

# Pwnagotchi imports
import pwnagotchi.plugins as plugins
from pwnagotchi.ui.components import LabeledValue
from pwnagotchi.ui.view import BLACK
import pwnagotchi.ui.fonts as fonts
from flask import render_template_string, request, abort, Response, stream_with_context
import pwnagotchi

# Third-party (optional)
try:
    from bleak import BleakScanner
    HAS_BLEAK = True
except ImportError:
    HAS_BLEAK = False

try:
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    from cryptography.hazmat.backends import default_backend
    HAS_CRYPTO = True
except ImportError:
    HAS_CRYPTO = False

try:
    from scipy.optimize import minimize
    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False

# ---------------------------------------------------------------------
# Utility Classes
# ---------------------------------------------------------------------

class KalmanFilter:
    """Simple Kalman filter for RSSI smoothing."""
    def __init__(self, process_noise=0.008, measurement_noise=1.0, initial_estimate=None, initial_certainty=1.0):
        self.mu = initial_estimate if initial_estimate is not None else -70.0
        self.sigma = initial_certainty
        self.R = process_noise
        self.Q = measurement_noise
        self.initialized = initial_estimate is not None

    def initialize(self, measurement):
        self.mu = measurement
        self.sigma = 1.0
        self.initialized = True

    def predict(self):
        self.mu_bar = self.mu
        self.sigma_bar = self.sigma + self.R

    def update(self, measurement):
        K = self.sigma_bar / (self.sigma_bar + self.Q)
        self.mu = self.mu_bar + K * (measurement - self.mu_bar)
        self.sigma = self.sigma_bar - K * self.sigma_bar

    def filter(self, measurement):
        if not self.initialized:
            self.initialize(measurement)
            return measurement
        self.predict()
        self.update(measurement)
        return self.mu


class CircularBuffer:
    """Thread-safe circular buffer for recent values."""
    def __init__(self, maxlen=100):
        self.buffer = deque(maxlen=maxlen)
        self.lock = Lock()

    def append(self, item):
        with self.lock:
            self.buffer.append(item)

    def get_all(self):
        with self.lock:
            return list(self.buffer)

    def clear(self):
        with self.lock:
            self.buffer.clear()


def haversine(lat1, lon1, lat2, lon2):
    """Great-circle distance in meters."""
    R = 6371000
    phi1 = radians(lat1)
    phi2 = radians(lat2)
    dphi = radians(lat2 - lat1)
    dlambda = radians(lon2 - lon1)
    a = sin(dphi/2)**2 + cos(phi1)*cos(phi2)*sin(dlambda/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1-a))
    return R * c


def haversine_miles(lat1, lon1, lat2, lon2):
    """Distance in miles."""
    R = 3958.8
    phi1 = radians(lat1)
    phi2 = radians(lat2)
    dphi = radians(lat2 - lat1)
    dlambda = radians(lon2 - lon1)
    a = sin(dphi/2)**2 + cos(phi1)*cos(phi2)*sin(dlambda/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1-a))
    return R * c


def cross(o, a, b):
    return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])


def convex_hull(points):
    points = sorted(set(points))
    if len(points) <= 1:
        return points
    lower = []
    for p in points:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    upper = []
    for p in reversed(points):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    return lower[:-1] + upper[:-1]


def polygon_diameter(points):
    hull = convex_hull(points)
    if len(hull) < 2:
        return 0.0
    max_dist = 0.0
    n = len(hull)
    for i in range(n):
        for j in range(i+1, n):
            d = haversine(hull[i][0], hull[i][1], hull[j][0], hull[j][1])
            if d > max_dist:
                max_dist = d
    return max_dist


def point_in_polygon(point, polygon):
    """Ray casting algorithm. polygon is list of (lat,lon) in order."""
    x, y = point
    inside = False
    n = len(polygon)
    for i in range(n):
        x1, y1 = polygon[i]
        x2, y2 = polygon[(i+1)%n]
        if ((y1 > y) != (y2 > y)) and (x < (x2-x1)*(y-y1)/(y2-y1)+x1):
            inside = not inside
    return inside


# ---------------------------------------------------------------------
# Geofence classes
# ---------------------------------------------------------------------

class Geofence:
    def __init__(self, name, fence_type, params):
        self.name = name
        self.type = fence_type  # 'circle' or 'polygon'
        self.params = params

    def contains(self, lat, lon):
        if self.type == 'circle':
            center_lat, center_lon, radius = self.params
            return haversine(center_lat, center_lon, lat, lon) <= radius
        elif self.type == 'polygon':
            return point_in_polygon((lon, lat), self.params)  # note (lon,lat) order
        return False


# ---------------------------------------------------------------------
# Database Layer
# ---------------------------------------------------------------------

class Database:
    def __init__(self, path):
        self._path = path
        self._connection = None
        self.db_lock = threading.RLock()
        self._connect()

    def _connect(self):
        try:
            self._connection = sqlite3.connect(self._path, check_same_thread=False, timeout=10)
            self._connection.execute('PRAGMA journal_mode=WAL')
            self._connection.execute('PRAGMA synchronous=NORMAL')
            self._create_tables()
        except sqlite3.Error as e:
            logging.error(f'[SnoopR] DB connection failed: {e}')
            raise

    def _create_tables(self):
        with self._connection:
            self._connection.execute('''
                CREATE TABLE IF NOT EXISTS sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            self._connection.execute('''
                CREATE TABLE IF NOT EXISTS networks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    mac TEXT NOT NULL,
                    type TEXT NOT NULL,
                    name TEXT,
                    device_type TEXT NOT NULL,
                    vendor TEXT DEFAULT 'Unknown',
                    classification TEXT DEFAULT 'Unknown',
                    is_rogue INTEGER DEFAULT 0,
                    is_mesh INTEGER DEFAULT 0,
                    vulnerabilities TEXT DEFAULT '',
                    anomalies TEXT DEFAULT '',
                    is_snooper INTEGER DEFAULT 0,
                    triangulated_lat TEXT,
                    triangulated_lon TEXT,
                    triangulated_mse REAL,
                    max_velocity REAL,
                    persistence_score REAL DEFAULT 0.0,
                    windows_hit INTEGER DEFAULT 0,
                    cluster_count INTEGER DEFAULT 0,
                    last_seen TEXT,
                    UNIQUE(mac, device_type)
                )
            ''')
            self._connection.execute('''
                CREATE TABLE IF NOT EXISTS detections (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id INTEGER NOT NULL,
                    network_id INTEGER NOT NULL,
                    encryption TEXT,
                    signal_strength INTEGER,
                    latitude TEXT,
                    longitude TEXT,
                    altitude TEXT DEFAULT '-',
                    channel INTEGER,
                    auth_mode TEXT,
                    timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
                    filtered_signal_strength REAL,
                    FOREIGN KEY(session_id) REFERENCES sessions(id),
                    FOREIGN KEY(network_id) REFERENCES networks(id)
                )
            ''')
            self._connection.execute('''
                CREATE TABLE IF NOT EXISTS aircraft_info (
                    icao24 TEXT PRIMARY KEY,
                    registration TEXT,
                    type TEXT,
                    owner TEXT,
                    last_updated TEXT
                )
            ''')
            self._connection.execute('CREATE INDEX IF NOT EXISTS idx_detections_network_id ON detections(network_id)')
            self._connection.execute('CREATE INDEX IF NOT EXISTS idx_networks_mac ON networks(mac)')
            self._connection.execute('CREATE INDEX IF NOT EXISTS idx_detections_timestamp ON detections(timestamp)')
            self._connection.execute('CREATE INDEX IF NOT EXISTS idx_networks_last_seen ON networks(last_seen)')
            self._migrate()

    def _migrate(self):
        cursor = self._connection.cursor()
        for col, col_type in [
            ('channel', 'INTEGER'),
            ('auth_mode', 'TEXT'),
            ('altitude', 'TEXT DEFAULT "-"'),
            ('filtered_signal_strength', 'REAL')
        ]:
            try:
                cursor.execute(f"ALTER TABLE detections ADD COLUMN {col} {col_type}")
                logging.info(f'[SnoopR] Added column "{col}" to detections')
            except sqlite3.OperationalError:
                pass

        for col, col_type in [
            ('triangulated_lat', 'TEXT'),
            ('triangulated_lon', 'TEXT'),
            ('triangulated_mse', 'REAL'),
            ('max_velocity', 'REAL'),
            ('vendor', 'TEXT DEFAULT "Unknown"'),
            ('persistence_score', 'REAL DEFAULT 0.0'),
            ('windows_hit', 'INTEGER DEFAULT 0'),
            ('cluster_count', 'INTEGER DEFAULT 0'),
            ('classification', 'TEXT DEFAULT "Unknown"'),
            ('is_rogue', 'INTEGER DEFAULT 0'),
            ('is_mesh', 'INTEGER DEFAULT 0'),
            ('vulnerabilities', 'TEXT DEFAULT ""'),
            ('anomalies', 'TEXT DEFAULT ""'),
            ('last_seen', 'TEXT')
        ]:
            try:
                cursor.execute(f"ALTER TABLE networks ADD COLUMN {col} {col_type}")
                logging.info(f'[SnoopR] Added column "{col}" to networks')
            except sqlite3.OperationalError:
                pass
        self._connection.commit()
        cursor.close()

    def disconnect(self):
        with self.db_lock:
            if self._connection:
                self._connection.close()

    def new_session(self):
        with self.db_lock:
            cursor = self._connection.cursor()
            cursor.execute('INSERT INTO sessions DEFAULT VALUES')
            session_id = cursor.lastrowid
            self._connection.commit()
            cursor.close()
            return session_id

    def add_detection_batch(self, detections):
        if not detections:
            return
        with self.db_lock:
            with self._connection:
                cursor = self._connection.cursor()
                net_map = {}
                for det in detections:
                    mac, type_, name, device_type, vendor, classification, is_rogue, is_mesh, vulns, anomalies = det[:10]
                    key = (mac, device_type)
                    if key not in net_map:
                        cursor.execute('SELECT id FROM networks WHERE mac = ? AND device_type = ?', key)
                        rows = cursor.fetchall()
                        if rows:
                            net_id = rows[0][0]
                            if len(rows) > 1:
                                logging.warning(f'[SnoopR] Duplicate networks for {key}, using first.')
                            cursor.execute('''
                                UPDATE networks SET classification=?, is_rogue=?, is_mesh=?, vulnerabilities=?, anomalies=?, last_seen=CURRENT_TIMESTAMP
                                WHERE id=?
                            ''', (classification, is_rogue, is_mesh, vulns, anomalies, net_id))
                        else:
                            cursor.execute('''
                                INSERT INTO networks (mac, type, name, device_type, vendor, classification, is_rogue, is_mesh, vulnerabilities, anomalies, last_seen)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                            ''', (mac, type_, name, device_type, vendor, classification, is_rogue, is_mesh, vulns, anomalies))
                            net_id = cursor.lastrowid
                        net_map[key] = net_id
                for det in detections:
                    mac, type_, name, device_type, vendor, classification, is_rogue, is_mesh, vulns, anomalies, encryption, signal_strength, latitude, longitude, channel, auth_mode, altitude, session_id = det
                    network_id = net_map[(mac, device_type)]
                    cursor.execute('''
                        INSERT INTO detections (session_id, network_id, encryption, signal_strength, latitude, longitude, altitude, channel, auth_mode, filtered_signal_strength)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (session_id, network_id, encryption, signal_strength, latitude, longitude, altitude, channel, auth_mode, None))
                self._connection.commit()
                logging.debug(f'[SnoopR] Batch added {len(detections)} detections')
                cursor.close()

    def update_filtered_rssi(self, detection_id, filtered_rssi):
        with self.db_lock:
            with self._connection:
                self._connection.execute('UPDATE detections SET filtered_signal_strength = ? WHERE id = ?', (filtered_rssi, detection_id))

    def update_persistence(self, mac, device_type, score, windows_hit, cluster_count):
        with self.db_lock:
            with self._connection:
                self._connection.execute('''
                    UPDATE networks
                    SET persistence_score = ?, windows_hit = ?, cluster_count = ?
                    WHERE mac = ? AND device_type = ?
                ''', (score, windows_hit, cluster_count, mac, device_type))

    def update_snooper_status(self, mac, device_type, is_snooper):
        with self.db_lock:
            with self._connection:
                self._connection.execute('UPDATE networks SET is_snooper = ? WHERE mac = ? AND device_type = ?', (is_snooper, mac, device_type))

    def update_max_velocity(self, mac, device_type, max_velocity):
        with self.db_lock:
            with self._connection:
                self._connection.execute('UPDATE networks SET max_velocity = ? WHERE mac = ? AND device_type = ?', (max_velocity, mac, device_type))

    def update_triangulated_position(self, mac, device_type, lat, lon, mse=None):
        with self.db_lock:
            with self._connection:
                self._connection.execute('UPDATE networks SET triangulated_lat = ?, triangulated_lon = ?, triangulated_mse = ? WHERE mac = ? AND device_type = ?',
                                         (lat, lon, mse, mac, device_type))

    def update_anomalies(self, mac, device_type, anomalies):
        with self.db_lock:
            with self._connection:
                self._connection.execute('UPDATE networks SET anomalies = ? WHERE mac = ? AND device_type = ?', (anomalies, mac, device_type))

    def get_network_counts(self):
        with self.db_lock:
            try:
                with self._connection:
                    wifi = self._connection.execute('SELECT COUNT(*) FROM networks WHERE device_type="wifi"').fetchone()[0]
                    bt = self._connection.execute('SELECT COUNT(*) FROM networks WHERE device_type="bluetooth"').fetchone()[0]
                    aircraft = self._connection.execute('SELECT COUNT(*) FROM networks WHERE device_type="aircraft"').fetchone()[0]
                    snoopers = self._connection.execute('SELECT COUNT(*) FROM networks WHERE is_snooper=1').fetchone()[0]
                    high_pers = self._connection.execute('SELECT COUNT(*) FROM networks WHERE persistence_score >= 0.7').fetchone()[0]
                    return {'wifi': wifi, 'bluetooth': bt, 'aircraft': aircraft, 'snoopers': snoopers, 'high_persistence': high_pers}
            except sqlite3.Error as e:
                logging.error(f'[SnoopR] get_network_counts error: {e}')
                return {'wifi': 0, 'bluetooth': 0, 'aircraft': 0, 'snoopers': 0, 'high_persistence': 0}

    def get_all_networks(self, sort_by=None, filter_by=None, include_paths=False, limit=1000, offset=0):
        with self.db_lock:
            try:
                query = '''
                    WITH latest_detections AS (
                        SELECT network_id, latitude, longitude,
                               ROW_NUMBER() OVER (PARTITION BY network_id ORDER BY timestamp DESC) as rn
                        FROM detections
                        WHERE latitude != '-' AND longitude != '-'
                    )
                    SELECT n.mac, n.type, n.name, n.device_type, n.vendor,
                           MIN(datetime(d.timestamp, 'localtime')) as first_seen,
                           MAX(datetime(d.timestamp, 'localtime')) as last_seen,
                           COUNT(DISTINCT d.session_id) as sessions_count,
                           ld.latitude as last_latitude,
                           ld.longitude as last_longitude,
                           n.is_snooper, n.triangulated_lat, n.triangulated_lon, n.triangulated_mse, n.max_velocity,
                           n.persistence_score, n.windows_hit, n.cluster_count, n.anomalies
                    FROM networks n
                    JOIN detections d ON n.id = d.network_id
                    LEFT JOIN latest_detections ld ON n.id = ld.network_id AND ld.rn = 1
                    WHERE 1=1
                '''
                params = []
                if filter_by == 'snoopers':
                    query += ' AND n.is_snooper = 1'
                elif filter_by == 'bluetooth':
                    query += ' AND n.device_type = "bluetooth"'
                elif filter_by == 'aircraft':
                    query += ' AND n.device_type = "aircraft"'
                elif filter_by == 'clients':
                    query += ' AND n.type = "wi-fi client"'
                elif filter_by == 'high_persistence':
                    query += ' AND n.persistence_score >= 0.7'

                query += ' GROUP BY n.id'

                order_map = {
                    'device_type': 'n.device_type',
                    'is_snooper': 'n.is_snooper DESC',
                    'persistence': 'n.persistence_score DESC',
                    'velocity': 'n.max_velocity DESC',
                    'mac': 'n.mac',
                    'name': 'n.name',
                }
                if sort_by in order_map:
                    query += f' ORDER BY {order_map[sort_by]}'
                else:
                    query += ' ORDER BY n.persistence_score DESC'

                query += ' LIMIT ? OFFSET ?'
                params.extend([limit, offset])

                with self._connection:
                    rows = self._connection.execute(query, params).fetchall()

                networks = []
                for row in rows:
                    (mac, type_, name, device_type, vendor, first_seen, last_seen, sessions_count,
                     last_latitude, last_longitude, is_snooper, triangulated_lat, triangulated_lon,
                     triangulated_mse, max_velocity, persistence_score, windows_hit, cluster_count, anomalies) = row
                    lat = float(triangulated_lat) if triangulated_lat else (float(last_latitude) if last_latitude and last_latitude != '-' else None)
                    lon = float(triangulated_lon) if triangulated_lon else (float(last_longitude) if last_longitude and last_longitude != '-' else None)
                    net = {
                        'mac': mac,
                        'type': type_,
                        'name': name or 'Hidden',
                        'device_type': device_type,
                        'vendor': vendor,
                        'first_seen': first_seen,
                        'last_seen': last_seen,
                        'sessions_count': sessions_count,
                        'latitude': lat,
                        'longitude': lon,
                        'is_snooper': bool(is_snooper),
                        'triangulated_mse': float(triangulated_mse) if triangulated_mse else None,
                        'max_velocity': float(max_velocity) if max_velocity else None,
                        'persistence_score': round(float(persistence_score or 0.0), 3),
                        'windows_hit': windows_hit or 0,
                        'cluster_count': cluster_count or 0,
                        'anomalies': anomalies or ''
                    }
                    if include_paths and lat and lon:
                        path_rows = self._connection.execute('''
                            SELECT latitude, longitude, datetime(timestamp, 'localtime'), signal_strength
                            FROM detections WHERE network_id = (SELECT id FROM networks WHERE mac=? AND device_type=?)
                            ORDER BY timestamp
                        ''', (mac, device_type)).fetchall()
                        path = []
                        for pr in path_rows:
                            if pr[0] != '-' and pr[1] != '-':
                                path.append({
                                    'latitude': float(pr[0]),
                                    'longitude': float(pr[1]),
                                    'timestamp': pr[2],
                                    'signal_strength': pr[3]
                                })
                        if len(path) > 1:
                            net['path'] = path
                    networks.append(net)
                return networks
            except sqlite3.Error as e:
                logging.error(f'[SnoopR] get_all_networks error: {e}')
                return []

    def get_detections_for_network(self, mac, device_type, limit=100, days=None):
        with self.db_lock:
            try:
                query = '''
                    SELECT d.id, d.signal_strength, d.latitude, d.longitude, d.altitude, d.timestamp,
                           d.filtered_signal_strength
                    FROM detections d
                    JOIN networks n ON n.id = d.network_id
                    WHERE n.mac = ? AND n.device_type = ?
                '''
                params = [mac, device_type]
                if days:
                    cutoff = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d %H:%M:%S')
                    query += ' AND d.timestamp >= ?'
                    params.append(cutoff)
                query += ' ORDER BY d.timestamp DESC LIMIT ?'
                params.append(limit)

                with self._connection:
                    rows = self._connection.execute(query, params).fetchall()
                return [{'id': r[0], 'rssi': r[1], 'lat': r[2], 'lon': r[3], 'alt': r[4],
                         'timestamp': r[5], 'filtered_rssi': r[6]} for r in rows]
            except sqlite3.Error as e:
                logging.error(f'[SnoopR] get_detections_for_network error: {e}')
                return []

    def get_recent_devices(self, days=7):
        with self.db_lock:
            cutoff = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d %H:%M:%S')
            try:
                with self._connection:
                    rows = self._connection.execute('''
                        SELECT DISTINCT mac, device_type FROM networks WHERE last_seen >= ?
                    ''', (cutoff,)).fetchall()
                return rows
            except sqlite3.Error as e:
                logging.error(f'[SnoopR] get_recent_devices error: {e}')
                return []

    def get_aircraft_info(self, icao24):
        with self.db_lock:
            try:
                row = self._connection.execute('SELECT registration, type, owner, last_updated FROM aircraft_info WHERE icao24=?', (icao24,)).fetchone()
                if row:
                    return {'registration': row[0], 'type': row[1], 'owner': row[2], 'last_updated': row[3]}
            except sqlite3.Error as e:
                logging.error(f'[SnoopR] get_aircraft_info error: {e}')
            return None

    def update_aircraft_info(self, icao24, info):
        with self.db_lock:
            try:
                self._connection.execute('''
                    INSERT OR REPLACE INTO aircraft_info (icao24, registration, type, owner, last_updated)
                    VALUES (?, ?, ?, ?, ?)
                ''', (icao24, info.get('registration'), info.get('type'), info.get('owner'), datetime.now().isoformat()))
                self._connection.commit()
            except sqlite3.Error as e:
                logging.error(f'[SnoopR] update_aircraft_info error: {e}')

    def prune_old_data(self, days):
        with self.db_lock:
            cutoff = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d %H:%M:%S')
            # Perform deletions in a transaction
            with self._connection:
                self._connection.execute('DELETE FROM detections WHERE timestamp < ?', (cutoff,))
                self._connection.execute('DELETE FROM sessions WHERE id NOT IN (SELECT DISTINCT session_id FROM detections)')
                self._connection.execute('DELETE FROM networks WHERE id NOT IN (SELECT DISTINCT network_id FROM detections)')
            # VACUUM must be run outside a transaction
            self._connection.execute('VACUUM')
            logging.info(f'[SnoopR] Pruned data older than {days} days')


# ---------------------------------------------------------------------
# Mesh Network
# ---------------------------------------------------------------------

class MeshNetwork:
    def __init__(self, host_ip, port, peers, shared_key, has_crypto):
        self.host_ip = host_ip
        self.port = port
        self.peers = peers
        self.key = hashlib.sha256(shared_key.encode()).digest()[:32] if shared_key and has_crypto else None
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.bind((host_ip, port))
        self.socket.setblocking(False)
        self.has_crypto = has_crypto
        if self.has_crypto:
            self.backend = default_backend()
        if not self.key and has_crypto:
            logging.warning('[SnoopR] Mesh encryption disabled: no key provided')
        if not has_crypto:
            logging.warning('[SnoopR] Mesh encryption disabled: cryptography not available')

    def _encrypt(self, data):
        if not self.key or not self.has_crypto:
            return data
        iv = os.urandom(12)
        cipher = Cipher(algorithms.AES(self.key), modes.GCM(iv), backend=self.backend)
        encryptor = cipher.encryptor()
        ct = encryptor.update(data) + encryptor.finalize()
        return iv + encryptor.tag + ct

    def _decrypt(self, data):
        if not self.key or not self.has_crypto:
            return data
        iv = data[:12]
        tag = data[12:28]
        ct = data[28:]
        cipher = Cipher(algorithms.AES(self.key), modes.GCM(iv, tag), backend=self.backend)
        decryptor = cipher.decryptor()
        return decryptor.update(ct) + decryptor.finalize()

    def broadcast_detection(self, detection):
        data = json.dumps(detection).encode('utf-8')
        encrypted = self._encrypt(data)
        for peer in self.peers:
            try:
                self.socket.sendto(encrypted, (peer, self.port))
            except (socket.error, OSError) as e:
                logging.error(f'[SnoopR] Mesh send to {peer} failed: {e}')

    def receive_detections(self, db, session_id):
        try:
            encrypted, addr = self.socket.recvfrom(4096)
            data = self._decrypt(encrypted)
            detection = json.loads(data.decode('utf-8'))
            db.add_detection_batch([(
                detection['mac'], detection['type'], detection['name'], detection['device_type'], 'Unknown',
                'Unknown', 0, 0, 'None', 'None',
                detection['encryption'], detection['signal_strength'], detection['latitude'],
                detection['longitude'], detection['channel'], detection['auth_mode'],
                detection.get('altitude', '-'), session_id
            )])
        except BlockingIOError:
            pass
        except (json.JSONDecodeError, KeyError, socket.error) as e:
            logging.error(f'[SnoopR] Mesh receive error: {e}')
        except Exception as e:
            logging.error(f'[SnoopR] Mesh receive unexpected error: {e}')

    def close(self):
        self.socket.close()


# ---------------------------------------------------------------------
# Background Threads
# ---------------------------------------------------------------------

class AircraftProcessor(threading.Thread):
    def __init__(self, plugin, interval=30, cache_timeout=600):
        super().__init__(daemon=True)
        self.plugin = plugin
        self.db = plugin.db
        self.aircraft_file = plugin.aircraft_file
        self.session_id = plugin.session_id
        self.interval = interval
        self.cache_timeout = cache_timeout
        self.cache = {}  # icao -> (lat, lon, alt, callsign, last_added, heading?, speed?)
        self.stop_event = threading.Event()
        self.last_mtime = 0
        self.geofences = plugin.geofences  # list of Geofence objects

    def run(self):
        while not self.stop_event.wait(self.interval):
            self.process()

    def stop(self):
        self.stop_event.set()

    def _fetch_aircraft_info(self, icao24):
        """Fetch from OpenSky or cache; runs in thread."""
        # Check cache first (DB)
        cached = self.db.get_aircraft_info(icao24)
        if cached:
            # If younger than 30 days, use it
            last = datetime.fromisoformat(cached['last_updated'])
            if (datetime.now() - last) < timedelta(days=30):
                return cached
        # Otherwise fetch from OpenSky
        try:
            if self.plugin.opensky_username and self.plugin.opensky_password:
                auth = (self.plugin.opensky_username, self.plugin.opensky_password)
            else:
                auth = None
            url = f"https://opensky-network.org/api/metadata/aircraft/icao/{icao24}"
            resp = requests.get(url, auth=auth, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                info = {
                    'registration': data.get('registration'),
                    'type': data.get('typecode'),
                    'owner': data.get('owner')
                }
                self.db.update_aircraft_info(icao24, info)
                return info
        except Exception as e:
            logging.debug(f'[SnoopR] OpenSky lookup failed for {icao24}: {e}')
        return None

    def _check_geofences(self, lat, lon):
        for gf in self.geofences:
            if gf.contains(lat, lon):
                return gf.name
        return None

    def process(self):
        if not os.path.exists(self.aircraft_file):
            return
        try:
            current_mtime = os.path.getmtime(self.aircraft_file)
            if current_mtime <= self.last_mtime:
                return
            self.last_mtime = current_mtime
            with open(self.aircraft_file, 'r') as f:
                aircraft = json.load(f)
            data = list(aircraft.values()) if isinstance(aircraft, dict) else aircraft if isinstance(aircraft, list) else []
            new_detections = []
            now = datetime.now()
            for plane in data:
                if not isinstance(plane, dict):
                    continue
                icao = plane.get('icao24')
                if not icao:
                    continue
                lat = plane.get('latitude')
                lon = plane.get('longitude')
                alt = plane.get('alt', '-')
                callsign = plane.get('callsign', 'UNKNOWN').strip()
                speed = plane.get('speed')          # knots, optional
                heading = plane.get('heading')      # degrees, optional
                vert_rate = plane.get('vert_rate')  # ft/min, optional
                squawk = plane.get('squawk')        # optional
                if lat is None or lon is None:
                    continue
                cached = self.cache.get(icao)
                add = False
                if not cached:
                    add = True
                else:
                    dist = haversine(cached[0], cached[1], lat, lon)
                    if dist > 500:
                        add = True
                    elif cached[2] != callsign or cached[3] != alt:
                        add = True
                    elif (now - cached[4]).total_seconds() > self.cache_timeout:
                        add = True
                if add:
                    # Run enhanced anomaly detection
                    anomalies = self.plugin.detect_aircraft_anomalies(
                        icao, lat, lon, alt, callsign, now,
                        speed=speed, heading=heading, vert_rate=vert_rate, squawk=squawk
                    )
                    # Check geofences
                    gf_name = self._check_geofences(lat, lon)
                    if gf_name:
                        anomalies.append(f"Geofence:{gf_name}")
                    anomalies_str = ", ".join(anomalies) if anomalies else "None"

                    new_detections.append((
                        icao, 'aircraft', callsign, 'aircraft', 'Unknown', 'Aircraft', 0, 0, 'None', anomalies_str,
                        '', 0, str(lat), str(lon), 0, '', str(alt), self.session_id
                    ))
                    self.cache[icao] = (lat, lon, callsign, alt, now, speed, heading, vert_rate, squawk)

                    # Asynchronously fetch aircraft info (if not in cache)
                    if not self.db.get_aircraft_info(icao):
                        threading.Thread(target=self._fetch_aircraft_info, args=(icao,), daemon=True).start()

            if new_detections:
                self.db.add_detection_batch(new_detections)
                logging.info(f'[SnoopR] Aircraft: added {len(new_detections)} new/updated')
        except (OSError, IOError, json.JSONDecodeError) as e:
            logging.error(f'[SnoopR] Aircraft file error: {e}')
        except Exception as e:
            logging.error(f'[SnoopR] Aircraft processing unexpected error: {e}')


class PersistenceAnalyzer(threading.Thread):
    def __init__(self, plugin, interval=300, analysis_days=7):
        super().__init__(daemon=True)
        self.plugin = plugin
        self.db = plugin.db
        self.interval = interval
        self.analysis_days = analysis_days
        self.stop_event = threading.Event()

    def run(self):
        while not self.stop_event.wait(self.interval):
            self.analyze_all()

    def stop(self):
        self.stop_event.set()

    def analyze_all(self):
        try:
            devices = self.db.get_recent_devices(days=self.analysis_days)
            for mac, device_type in devices:
                self.plugin.update_device_status(mac, device_type)
            logging.info(f'[SnoopR] Periodic analysis complete for {len(devices)} devices')
        except Exception as e:
            logging.error(f'[SnoopR] analyze_all error: {e}')


# ---------------------------------------------------------------------
# Web Handler
# ---------------------------------------------------------------------

HTML_PAGE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SnoopR - Advanced Surveillance Detection</title>
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <script src="https://unpkg.com/leaflet.heat@0.2.0/dist/leaflet-heat.js"></script>
    <style>
        body { font-family: Arial, sans-serif; margin: 0; padding: 20px; transition: background 0.3s, color 0.3s; }
        body.dark { background: #121212; color: #e0e0e0; }
        table { width: 100%; border-collapse: collapse; margin-bottom: 20px; }
        th, td { padding: 10px; text-align: left; border-bottom: 1px solid #444; }
        body.dark th, body.dark td { border-color: #555; }
        th { background: #f0f0f0; cursor: pointer; }
        body.dark th { background: #333; }
        tr:hover { background: #f5f5f5; }
        body.dark tr:hover { background: #333; }
        .low { background: #d0f0d0; }
        .med { background: #ffffd0; }
        .high { background: #ffd0d0; }
        body.dark .low { background: #1e3f1e; }
        body.dark .med { background: #3f3f1e; }
        body.dark .high { background: #4f1e1e; }
        #map { height: 600px; margin-top: 20px; border: 2px solid #444; }
        .controls { margin: 15px 0; }
        .btn { padding: 8px 16px; margin-right: 10px; cursor: pointer; background: #4CAF50; color: white; border: none; border-radius: 4px; }
        #search { padding: 8px; width: 300px; }
        #fixed-buttons { position: fixed; top: 10px; right: 10px; z-index: 1000; }
        .pagination { margin-top: 10px; }
        .pagination a { padding: 5px 10px; border: 1px solid #ccc; margin-right: 5px; text-decoration: none; }
        body.dark .pagination a { border-color: #555; color: #eee; }
        #alert-box { position: fixed; top: 10px; left: 10px; background: rgba(255,0,0,0.8); color: white; padding: 10px; border-radius: 5px; display: none; z-index: 2000; }
    </style>
</head>
<body>
    <div id="alert-box"></div>
    <div id="fixed-buttons">
        <button class="btn" onclick="document.body.classList.toggle('dark')">Dark Mode</button>
        <button class="btn" onclick="window.scrollTo({top: 0, behavior: 'smooth'})">Top</button>
        <button class="btn" onclick="window.scrollTo({top: document.body.scrollHeight, behavior: 'smooth'})">Bottom</button>
    </div>
    <h1>SnoopR - Advanced Surveillance Detection</h1>
    <input type="text" id="search" placeholder="Search MAC, Name, Vendor..." onkeyup="filterTable()">
    <div class="controls">
        <button class="btn" onclick="location.href='?filter_by=all'">All</button>
        <button class="btn" onclick="location.href='?filter_by=snoopers'">Snoopers</button>
        <button class="btn" onclick="location.href='?filter_by=high_persistence'">High Persistence</button>
        <button class="btn" onclick="location.href='?filter_by=bluetooth'">Bluetooth</button>
        <button class="btn" onclick="location.href='?filter_by=aircraft'">Aircraft</button>
        <button class="btn" onclick="location.href='?filter_by=clients'">Clients</button>
        <button class="btn" onclick="location.href='?export=kml'">Export KML</button>
    </div>
    <table id="networks-table">
        <thead>
            <tr>
                <th onclick="sortTable(0)">Device Type</th>
                <th onclick="sortTable(1)">MAC/ICAO</th>
                <th onclick="sortTable(2)">Name/Callsign</th>
                <th onclick="sortTable(3)">Vendor/Type</th>
                <th onclick="sortTable(4)">Persistence</th>
                <th onclick="sortTable(5)">Windows</th>
                <th onclick="sortTable(6)">Clusters</th>
                <th onclick="sortTable(7)">Sessions</th>
                <th>Snooper</th>
                <th onclick="sortTable(9)">Velocity (mph)</th>
                <th>Anomalies</th>
            </tr>
        </thead>
        <tbody>
            {% for net in networks %}
            <tr onclick="panTo({{ net.latitude }}, {{ net.longitude }})" class="{{ 'high' if net.persistence_score > 0.7 else 'med' if net.persistence_score > 0.4 else 'low' }}">
                <td>{{ net.device_type }}</td>
                <td>{{ net.mac }}</td>
                <td>{{ net.name }}</td>
                <td>{{ net.vendor }}</td>
                <td>{{ net.persistence_score }}</td>
                <td>{{ net.windows_hit }}</td>
                <td>{{ net.cluster_count }}</td>
                <td>{{ net.sessions_count }}</td>
                <td>{{ 'Yes' if net.is_snooper else 'No' }}</td>
                <td>{{ net.max_velocity | round(1) if net.max_velocity else 'N/A' }}</td>
                <td>{{ net.anomalies }}</td>
            </tr>
            {% endfor %}
        </tbody>
    </table>
    <div id="map"></div>
    <button class="btn" id="heatmap-toggle">Toggle Heatmap</button>
    <script>
        const networks = {{ networks | tojson }};
        const geofences = {{ geofences | tojson }};
        const map = L.map('map').setView({{ center | tojson }}, 13);
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png').addTo(map);
        const markers = [];
        const polylines = [];

        // Add geofences
        geofences.forEach(gf => {
            if (gf.type === 'circle') {
                L.circle([gf.params[0], gf.params[1]], {radius: gf.params[2], color: 'blue', fillOpacity: 0.1}).addTo(map).bindPopup(gf.name);
            } else if (gf.type === 'polygon') {
                L.polygon(gf.params, {color: 'blue', fillOpacity: 0.1}).addTo(map).bindPopup(gf.name);
            }
        });

        networks.forEach(net => {
            if (net.latitude && net.longitude) {
                let color = net.persistence_score > 0.7 ? 'red' : net.persistence_score > 0.4 ? 'orange' : 'green';
                if (net.device_type === 'aircraft' && net.anomalies !== 'None') color = 'purple';
                const radius = net.persistence_score * 10 + 5;
                const weight = net.persistence_score * 4 + 2;
                const marker = L.circleMarker([net.latitude, net.longitude], {color, radius})
                    .bindPopup(`<b>${net.mac}</b><br>Name: ${net.name}<br>Vendor: ${net.vendor}<br>Persistence: ${net.persistence_score}<br>Snooper: ${net.is_snooper}<br>Anomalies: ${net.anomalies}`);
                marker.addTo(map);
                if (net.path && net.path.length > 1) {
                    const poly = L.polyline(net.path.map(p => [p.latitude, p.longitude]), {color, weight, opacity: 0.8}).addTo(map);
                    polylines.push(poly);
                }
            }
        });
        const heatData = networks.filter(n => n.latitude).map(n => [n.latitude, n.longitude, n.persistence_score * n.sessions_count + 1]);
        const heatmap = L.heatLayer(heatData, {radius: 25, blur: 15});
        let heatmapOn = false;
        document.getElementById('heatmap-toggle').onclick = () => {
            heatmapOn = !heatmapOn;
            if (heatmapOn) map.addLayer(heatmap); else map.removeLayer(heatmap);
        };
        function panTo(lat, lon) {
            if (lat && lon) map.setView([lat, lon], 16);
        }
        function filterTable() {
            const term = document.getElementById('search').value.toLowerCase();
            const rows = document.querySelectorAll('#networks-table tbody tr');
            rows.forEach(row => {
                row.style.display = row.textContent.toLowerCase().includes(term) ? '' : 'none';
            });
        }
        let sortDirection = {};
        function sortTable(colIndex) {
            const table = document.getElementById('networks-table');
            const tbody = table.querySelector('tbody');
            const rows = Array.from(tbody.querySelectorAll('tr'));
            sortDirection[colIndex] = !sortDirection[colIndex] ?? true;
            const ascending = sortDirection[colIndex];
            rows.sort((a, b) => {
                let aVal = a.children[colIndex].textContent.trim();
                let bVal = b.children[colIndex].textContent.trim();
                if ([4,5,6,7,9].includes(colIndex)) {
                    aVal = aVal === 'N/A' ? -Infinity : parseFloat(aVal) || 0;
                    bVal = bVal === 'N/A' ? -Infinity : parseFloat(bVal) || 0;
                }
                if (aVal < bVal) return ascending ? -1 : 1;
                if (aVal > bVal) return ascending ? 1 : -1;
                return 0;
            });
            rows.forEach(row => tbody.appendChild(row));
        }
        // Alert stream
        const alertSource = new EventSource('/alerts');
        alertSource.onmessage = (e) => {
            const alert = JSON.parse(e.data);
            const box = document.getElementById('alert-box');
            box.innerHTML = alert.message;
            box.style.display = 'block';
            setTimeout(() => { box.style.display = 'none'; }, 5000);
        };
        // Counts stream
        const evtSource = new EventSource('/stream');
        evtSource.onmessage = (e) => {
            const counts = JSON.parse(e.data);
            console.log('Live counts:', counts);
        };
    </script>
</body>
</html>
'''


class WebHandler:
    def __init__(self, plugin):
        self.plugin = plugin
        self.ip_requests = {}
        self.alert_queue = deque(maxlen=100)  # store recent alerts for /alerts stream

    def add_alert(self, message):
        self.alert_queue.append({'time': datetime.now().isoformat(), 'message': message})

    def handle(self, path, request):
        ip = request.remote_addr or 'unknown'
        now = time.time()
        if ip not in self.ip_requests:
            self.ip_requests[ip] = []
        self.ip_requests[ip] = [t for t in self.ip_requests[ip] if now - t < 60]
        if len(self.ip_requests[ip]) >= 15:
            abort(429)
        self.ip_requests[ip].append(now)

        if path == '/stream':
            return self._stream_events(request)
        if path == '/alerts':
            return self._stream_alerts(request)

        if request.method == 'GET':
            sort_by = request.args.get('sort_by', 'persistence')
            filter_by = request.args.get('filter_by', 'all')
            if request.args.get('export') == 'kml':
                return self._export_kml()
            networks = self.plugin.db.get_all_networks(sort_by=sort_by, filter_by=filter_by, include_paths=True)
            center = [float(self.plugin.last_gps['latitude']), float(self.plugin.last_gps['longitude'])] if self.plugin.last_gps['latitude'] != '-' else [37.7749, -122.4194]
            # Prepare geofences for map
            geofences_json = []
            for gf in self.plugin.geofences:
                if gf.type == 'circle':
                    geofences_json.append({'name': gf.name, 'type': 'circle', 'params': gf.params})
                elif gf.type == 'polygon':
                    geofences_json.append({'name': gf.name, 'type': 'polygon', 'params': gf.params})
            return render_template_string(HTML_PAGE, networks=networks, center=center,
                                          sort_by=sort_by, filter_by=filter_by, geofences=geofences_json)
        return "Not Found", 404

    def _export_kml(self):
        networks = self.plugin.db.get_all_networks(include_paths=True)
        kml = '''<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
<Document>
    <Style id="green"><IconStyle><color>ff00ff00</color><scale>1.1</scale></IconStyle></Style>
    <Style id="yellow"><IconStyle><color>ff00ffff</color><scale>1.3</scale></IconStyle></Style>
    <Style id="red"><IconStyle><color>ff0000ff</color><scale>1.5</scale></IconStyle></Style>
    <Style id="path_high"><LineStyle><color>ff0000ff</color><width>4</width></LineStyle></Style>
    <Style id="path_med"><LineStyle><color>ff00aaff</color><width>3</width></LineStyle></Style>
'''
        for net in networks:
            if not net['latitude'] or not net['longitude']:
                continue
            score = net['persistence_score']
            style = 'red' if score > 0.7 else 'yellow' if score > 0.4 else 'green'
            path_style = 'path_high' if score > 0.7 else 'path_med' if score > 0.4 else None
            snooper_text = 'Yes' if net['is_snooper'] else 'No'
            anomalies = net.get('anomalies', '')
            desc = f"<![CDATA[<h3>{net['name']} ({net['mac']})</h3><b>Vendor:</b> {net['vendor']}<br><b>Type:</b> {net['device_type']}<br><b>Persistence:</b> {score:.3f}<br><b>Windows:</b> {net['windows_hit']}<br><b>Clusters:</b> {net['cluster_count']}<br><b>Sessions:</b> {net['sessions_count']}<br><b>Snooper:</b> {snooper_text}<br><b>Anomalies:</b> {anomalies}]]>"
            kml += f'<Placemark><name>{net["mac"]}</name><description>{desc}</description><styleUrl>#{style}</styleUrl><Point><coordinates>{net["longitude"]},{net["latitude"]},0</coordinates></Point></Placemark>'
            if 'path' in net and len(net['path']) > 1 and path_style:
                coords = ' '.join(f"{p['longitude']},{p['latitude']},0" for p in net['path'])
                kml += f'<Placemark><name>Trail: {net["mac"]}</name><styleUrl>#{path_style}</styleUrl><LineString><coordinates>{coords}</coordinates></LineString></Placemark>'
        kml += '</Document></kml>'
        return Response(kml, mimetype='application/vnd.google-earth.kml+xml',
                        headers={'Content-Disposition': 'attachment; filename=snoopr.kml'})

    def _stream_events(self, request):
        def event_stream():
            last_counts = None
            while not self.plugin.stop_event.is_set():
                counts = self.plugin.db.get_network_counts()
                if counts != last_counts:
                    yield f"data: {json.dumps(counts)}\n\n"
                    last_counts = counts
                time.sleep(5)
        return Response(stream_with_context(event_stream()), mimetype='text/event-stream')

    def _stream_alerts(self, request):
        def event_stream():
            last_index = 0
            while not self.plugin.stop_event.is_set():
                if len(self.alert_queue) > last_index:
                    # send new alerts
                    for i in range(last_index, len(self.alert_queue)):
                        alert = self.alert_queue[i]
                        yield f"data: {json.dumps(alert)}\n\n"
                    last_index = len(self.alert_queue)
                time.sleep(2)
        return Response(stream_with_context(event_stream()), mimetype='text/event-stream')


# ---------------------------------------------------------------------
# Helper functions for persistence analysis
# ---------------------------------------------------------------------

def calculate_distance_miles(lat1, lon1, lat2, lon2):
    return haversine_miles(lat1, lon1, lat2, lon2)


def get_cluster_count(gps_points, max_dist_miles=0.0621371):
    if not gps_points:
        return 0
    clusters = []
    for lat, lon in gps_points:
        point = (float(lat), float(lon))
        added = False
        for cluster in clusters:
            center_lat, center_lon = cluster['center']
            if calculate_distance_miles(center_lat, center_lon, point[0], point[1]) <= max_dist_miles:
                cluster['points'].append(point)
                pts = cluster['points']
                cluster['center'] = (sum(p[0] for p in pts)/len(pts), sum(p[1] for p in pts)/len(pts))
                added = True
                break
        if not added:
            clusters.append({'points': [point], 'center': point})
    return len(clusters)


def euclidean_distance(x1, y1, x2, y2):
    return sqrt((x2 - x1)**2 + (y2 - y1)**2)


def trilaterate(locations, distances, weights, mse_threshold, initial_guess=None):
    if not locations:
        return None, None
    if initial_guess is None:
        if distances:
            min_idx = min(range(len(distances)), key=distances.__getitem__)
            initial_guess = locations[min_idx]
        else:
            initial_guess = (0.0, 0.0)

    def objective(x):
        err = 0.0
        tot_w = sum(weights) or 1
        for loc, dist, w in zip(locations, distances, weights):
            calc = euclidean_distance(x[0], x[1], loc[0], loc[1])
            err += w * (calc - dist) ** 2
        return err / tot_w

    if HAS_SCIPY:
        try:
            result = minimize(objective, initial_guess, method='Nelder-Mead')
            est_pos = tuple(result.x)
            mse = result.fun
        except Exception:
            n = len(locations)
            est_pos = (sum(l[0] for l in locations)/n, sum(l[1] for l in locations)/n)
            mse = objective(est_pos)
    else:
        est_pos, mse = nelder_mead(objective, initial_guess)

    if mse > mse_threshold:
        n = len(locations)
        est_pos = (sum(l[0] for l in locations)/n, sum(l[1] for l in locations)/n)
        mse = objective(est_pos)
    return est_pos, mse


def nelder_mead(f, x_start, step=0.1, no_improve_thr=1e-6, no_improv_break=10, max_iter=0, alpha=1., gamma=2., rho=0.5, sigma=0.5):
    dim = len(x_start)
    prev_best = f(x_start)
    no_improv = 0
    res = [[list(x_start), prev_best]]
    for i in range(dim):
        x = list(x_start)
        x[i] += step
        score = f(x)
        res.append([x, score])
    iters = 0
    while True:
        res.sort(key=lambda x: x[1])
        best = res[0][1]
        if max_iter and iters >= max_iter:
            return res[0]
        iters += 1
        if best < prev_best - no_improve_thr:
            no_improv = 0
            prev_best = best
        else:
            no_improv += 1
        if no_improv >= no_improv_break:
            return res[0]
        x0 = [0.0] * dim
        for tup in res[:-1]:
            for i, c in enumerate(tup[0]):
                x0[i] += c / dim
        xr = [x0[i] + alpha * (x0[i] - res[-1][0][i]) for i in range(dim)]
        rscore = f(xr)
        if res[0][1] <= rscore < res[-2][1]:
            del res[-1]
            res.append([xr, rscore])
            continue
        if rscore < res[0][1]:
            xe = [x0[i] + gamma * (x0[i] - res[-1][0][i]) for i in range(dim)]
            escore = f(xe)
            if escore < rscore:
                del res[-1]
                res.append([xe, escore])
            else:
                del res[-1]
                res.append([xr, rscore])
            continue
        xc = [x0[i] + rho * (x0[i] - res[-1][0][i]) for i in range(dim)]
        cscore = f(xc)
        if cscore < res[-1][1]:
            del res[-1]
            res.append([xc, cscore])
            continue
        x1 = res[0][0]
        new_res = []
        for tup in res:
            redx = [x1[i] + sigma * (tup[0][i] - x1[i]) for i in range(dim)]
            score = f(redx)
            new_res.append([redx, score])
        res = new_res


# ---------------------------------------------------------------------
# Main Plugin Class
# ---------------------------------------------------------------------

class SnoopR(plugins.Plugin):
    __author__ = 'AlienMajik'
    __version__ = '6.0.0'
    __license__ = 'GPL3'
    __description__ = 'SnoopR: surveillance detection with WiFi/BLE/Aircraft, web UI, mesh, persistence scoring, geofencing, enhanced aircraft anomalies.'

    def __init__(self):
        self.options = {}
        self.ready = False
        self.lock = threading.Lock()
        self.db = None
        self.session_id = None
        self.mesh = None
        self.aircraft_thread = None
        self.persistence_thread = None
        self.stop_event = threading.Event()
        self.loop = None
        self.bleak_task = None
        self.web_handler = None

        self.last_gps = {'latitude': '-', 'longitude': '-', 'altitude': '-'}
        self.last_valid_gps = None
        self.vendor_cache = {}
        self.oui_db = {}
        self.bluetooth_company_db = {}
        self.counts_cache = {'wifi': 0, 'bluetooth': 0, 'aircraft': 0, 'snoopers': 0, 'high_persistence': 0}
        self.counts_last_update = 0
        self.counts_interval = 10

        self.whitelist_ssids = []
        self.whitelist_macs = []

        self.kalman_filters = {}

        self.detection_buffer = []
        self.buffer_lock = threading.Lock()
        self.buffer_max_size = 50
        self.last_buffer_flush = time.time()
        self.buffer_flush_interval = 2

        self.movement_threshold = 0.8
        self.time_threshold_minutes = 20

        # Aircraft thresholds (new)
        self.aircraft_high_altitude_threshold = 300
        self.aircraft_circling_radius = 500
        self.aircraft_circling_time = 120
        self.aircraft_rapid_descent_threshold = 3000  # ft/min
        self.aircraft_rapid_climb_threshold = 3000
        self.aircraft_max_speed_knots = 600
        self.aircraft_min_speed_knots = 50
        self.aircraft_enable_squawk_alerts = True

        # OpenSky
        self.opensky_username = None
        self.opensky_password = None

        # Geofences
        self.geofences = []  # list of Geofence objects

        self.aircraft_tracks = defaultdict(lambda: deque(maxlen=20))

    def _load_config(self):
        config = pwnagotchi.config.get('main', {}).get('plugins', {}).get('snoopr', {})
        self.options.update(config)

        base_dir = self.options.get('base_dir', '/root/snoopr')
        os.makedirs(base_dir, exist_ok=True)
        self.db_path = os.path.join(base_dir, 'snoopr.db')
        self.oui_db_path = self.options.get('oui_db_path', '/usr/share/wireshark/manuf')
        if not os.path.exists(self.oui_db_path):
            local_oui = os.path.join(base_dir, 'manuf')
            if os.path.exists(local_oui):
                self.oui_db_path = local_oui
            else:
                logging.warning(f'[SnoopR] OUI DB not found at {self.oui_db_path} and no local copy. Vendor lookup may be incomplete.')
        self.bt_company_db_path = self.options.get('bt_company_db_path', os.path.join(base_dir, 'company_identifiers.json'))
        self.aircraft_file = self.options.get('aircraft_file', '/root/aircraft.json')
        if not os.path.exists(self.aircraft_file):
            logging.warning(f'[SnoopR] Aircraft file {self.aircraft_file} not found. Aircraft tracking disabled.')

        self.scan_interval = self.options.get('scan_interval', 10)
        self.scan_duration = self.options.get('scan_duration', 5)
        self.bluetooth_enabled = self.options.get('bluetooth_enabled', True)
        self.bluetooth_device = self.options.get('bluetooth_device', 'hci0')
        self.log_without_gps = self.options.get('log_without_gps', False)
        self.prune_days = self.options.get('prune_days', 30)

        self.mesh_enabled = self.options.get('mesh_enabled', False)
        self.mesh_host = self.options.get('mesh_host', '0.0.0.0')
        self.mesh_port = self.options.get('mesh_port', 8888)
        self.mesh_peers = self.options.get('mesh_peers', [])
        self.mesh_key = self.options.get('mesh_key', '')
        if self.mesh_key and self.mesh_enabled:
            logging.warning('[SnoopR] Mesh encryption key stored in plaintext. Ensure config file permissions are restricted (e.g., chmod 600).')

        self.wigle_enabled = self.options.get('wigle_enabled', False)
        self.wigle_api_name = self.options.get('wigle_api_name', '')
        self.wigle_api_token = self.options.get('wigle_api_token', '')
        if self.wigle_enabled and (self.wigle_api_name or self.wigle_api_token):
            logging.warning('[SnoopR] WiGLE credentials stored in plaintext. Ensure config file permissions are restricted.')

        self.whitelist_ssids = self.options.get('whitelist_ssids', [])
        self.whitelist_macs = [mac.upper() for mac in self.options.get('whitelist_macs', [])]

        self.persistence_threshold = self.options.get('persistence_threshold', 0.7)
        self.triangulation_min_points = self.options.get('triangulation_min_points', 3)
        self.mse_threshold = self.options.get('mse_threshold', 100)
        self.movement_threshold = self.options.get('movement_threshold', 0.8)
        self.time_threshold_minutes = self.options.get('time_threshold_minutes', 20)

        # Aircraft thresholds
        self.aircraft_high_altitude_threshold = self.options.get('aircraft_high_altitude_threshold', 300)
        self.aircraft_circling_radius = self.options.get('aircraft_circling_radius', 500)
        self.aircraft_circling_time = self.options.get('aircraft_circling_time', 120)
        self.aircraft_rapid_descent_threshold = self.options.get('aircraft_rapid_descent_threshold', 3000)
        self.aircraft_rapid_climb_threshold = self.options.get('aircraft_rapid_climb_threshold', 3000)
        self.aircraft_max_speed_knots = self.options.get('aircraft_max_speed_knots', 600)
        self.aircraft_min_speed_knots = self.options.get('aircraft_min_speed_knots', 50)
        self.aircraft_enable_squawk_alerts = self.options.get('aircraft_enable_squawk_alerts', True)

        # OpenSky
        self.opensky_username = self.options.get('opensky_username', '')
        self.opensky_password = self.options.get('opensky_password', '')

        # Geofences: expect a list of dicts
        geofences_config = self.options.get('geofences', [])
        for gf in geofences_config:
            try:
                name = gf.get('name', 'Unnamed')
                ftype = gf.get('type')
                if ftype == 'circle':
                    params = (gf['lat'], gf['lon'], gf['radius'])
                    self.geofences.append(Geofence(name, 'circle', params))
                elif ftype == 'polygon':
                    params = gf['points']  # list of [lat,lon]
                    self.geofences.append(Geofence(name, 'polygon', params))
            except Exception as e:
                logging.error(f'[SnoopR] Invalid geofence config: {e}')

        self.analysis_days = self.options.get('analysis_days', 7)
        self.ui_enabled = self.options.get('ui_enabled', True)

    def _check_dependencies(self):
        missing = []
        if self.bluetooth_enabled and not HAS_BLEAK:
            missing.append('bleak')
        if self.mesh_enabled and not HAS_CRYPTO:
            missing.append('cryptography')
        if missing:
            logging.warning(f'[SnoopR] Missing optional packages: {", ".join(missing)}. Some features disabled.')

    def _load_oui_db(self):
        if not os.path.exists(self.oui_db_path):
            return
        try:
            with open(self.oui_db_path, 'r', encoding='utf-8', errors='ignore') as f:
                for line in f:
                    if '(hex)' in line:
                        parts = line.split('(hex)')
                        oui = parts[0].strip().replace('-', '').upper()
                        vendor = parts[-1].strip()
                        if len(oui) >= 6:
                            self.oui_db[oui[:6]] = vendor
            logging.info(f'[SnoopR] Loaded {len(self.oui_db)} OUIs')
        except (IOError, OSError) as e:
            logging.error(f'[SnoopR] OUI load error: {e}')

    def _load_bluetooth_company_db(self):
        if not os.path.exists(self.bt_company_db_path):
            logging.warning(f'[SnoopR] BT Company DB not found: {self.bt_company_db_path}')
            return
        try:
            with open(self.bt_company_db_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if isinstance(data, dict) and 'company_identifiers' in data:
                for entry in data['company_identifiers']:
                    self.bluetooth_company_db[entry['code']] = entry['name']
            elif isinstance(data, list):
                for entry in data:
                    if 'code' in entry and 'name' in entry:
                        self.bluetooth_company_db[entry['code']] = entry['name']
            logging.info(f'[SnoopR] Loaded {len(self.bluetooth_company_db)} BT Company IDs')
        except (IOError, json.JSONDecodeError) as e:
            logging.error(f'[SnoopR] BT Company DB load error: {e}')

    def _download_bt_company_db(self):
        try:
            import requests
            url = "https://raw.githubusercontent.com/NordicSemiconductor/bluetooth-numbers-database/master/v1/company_ids.json"
            resp = requests.get(url, timeout=30)
            resp.raise_for_status()
            with open(self.bt_company_db_path, 'w') as f:
                f.write(resp.text)
            logging.info("[SnoopR] Downloaded BT Company DB")
        except Exception as e:
            logging.error(f"[SnoopR] BT Company DB download failed: {e}")

    def _lookup_oui_vendor(self, mac):
        if not mac:
            return "Unknown"
        oui = mac.replace(":", "").upper()[:6]
        return self.oui_db.get(oui, "Unknown")

    def _lookup_bt_company(self, mfg_data):
        if not mfg_data or len(mfg_data) < 2:
            return "Unknown"
        try:
            cid = int.from_bytes(mfg_data[:2], 'little')
            return self.bluetooth_company_db.get(cid, f"Unknown (0x{cid:04X})")
        except Exception:
            return "Unknown"

    def _classify_device(self, name, mfg_data):
        if mfg_data:
            for data in mfg_data.values():
                company = self._lookup_bt_company(data)
                cl = company.lower()
                if "apple" in cl:
                    return "Apple Device"
                if "google" in cl:
                    return "Android/Google Device"
                if "samsung" in cl:
                    return "Samsung Device"
                if "microsoft" in cl:
                    return "Microsoft Device"
                if "fitbit" in cl:
                    return "Fitness Tracker"
        if name:
            ln = name.lower()
            if "apple" in ln or "airpods" in ln:
                return "Apple Device"
            if "samsung" in ln or "galaxy" in ln:
                return "Samsung Device"
            if "fitbit" in ln:
                return "Fitness Tracker"
            if "watch" in ln or "band" in ln:
                return "Wearable"
            if "speaker" in ln or "headphone" in ln:
                return "Audio Device"
        return "Unknown Device"

    def _detect_vulnerabilities(self, adv_data):
        vulns = []
        if adv_data.service_uuids and "00001800-0000-1000-8000-00805f9b34fb" in adv_data.service_uuids:
            vulns.append("Exposed Generic Access")
        return ", ".join(vulns) if vulns else "None"

    def _detect_anomalies(self, adv_data):
        anomalies = []
        if adv_data.service_uuids:
            uuids = set(adv_data.service_uuids)
            if "0000feaa-0000-1000-8000-00805f9b34fb" in uuids and "0000180a-0000-1000-8000-00805f9b34fb" in uuids:
                anomalies.append("Multiple beacon types")
        return ", ".join(anomalies) if anomalies else "None"

    def _detect_rogue(self, vendor, name):
        rogue_keywords = ["espressif", "tuya", "shenzhen", "ubiquiti", "alfa", "raspberry", "generic", "unknown", "xiaomi", "yeelink", "tp-link", "test", "demo", "private", "development", "nordic semiconductor"]
        score = 0
        if any(k in vendor.lower() for k in rogue_keywords):
            score += 1
        if name and any(k in name.lower() for k in ["test", "demo", "private", "default"]):
            score += 1
        return 1 if score >= 1 else 0

    def _detect_mesh(self, adv_data):
        mesh_uuids = {"00001827-0000-1000-8000-00805f9b34fb", "00001828-0000-1000-8000-00805f9b34fb"}
        return 1 if set(adv_data.service_uuids or []).intersection(mesh_uuids) else 0

    def _get_kalman(self, mac, device_type):
        key = (mac, device_type)
        if key not in self.kalman_filters:
            self.kalman_filters[key] = KalmanFilter()
        return self.kalman_filters[key]

    def _wigle_geolocate(self, ssid):
        if not self.wigle_enabled or not ssid:
            return None, None
        try:
            import requests
            auth = base64.b64encode(f"{self.wigle_api_name}:{self.wigle_api_token}".encode()).decode()
            headers = {'Authorization': f'Basic {auth}'}
            resp = requests.get(f"https://api.wigle.net/api/v2/network/search?ssid={ssid}", headers=headers, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                if data.get('results'):
                    first = data['results'][0]
                    return first.get('trilat'), first.get('trilong')
        except Exception as e:
            logging.debug(f'[SnoopR] WiGLE lookup failed for {ssid}: {e}')
        return None, None

    def _get_gps(self, agent):
        try:
            gps = agent.session()['gps']
            if gps and all(k in gps for k in ['Latitude', 'Longitude']):
                return gps
        except Exception:
            pass
        return None

    def _flush_detection_buffer(self):
        with self.buffer_lock:
            if not self.detection_buffer:
                return
            batch = self.detection_buffer.copy()
            self.detection_buffer.clear()
            self.last_buffer_flush = time.time()
        self.db.add_detection_batch(batch)
        logging.debug(f'[SnoopR] Flushed {len(batch)} detections')

    def _add_to_buffer(self, detection_tuple):
        with self.buffer_lock:
            self.detection_buffer.append(detection_tuple)
            if len(self.detection_buffer) >= self.buffer_max_size or (time.time() - self.last_buffer_flush) >= self.buffer_flush_interval:
                threading.Thread(target=self._flush_detection_buffer, daemon=True).start()

    def detect_aircraft_anomalies(self, icao, lat, lon, alt, callsign, timestamp, speed=None, heading=None, vert_rate=None, squawk=None):
        anomalies = []
        track = self.aircraft_tracks[icao]
        prev = track[-1] if track else None
        track.append((lat, lon, alt, timestamp, speed, heading, vert_rate, squawk))

        if alt != '-' and float(alt) < self.aircraft_high_altitude_threshold:
            anomalies.append("Low altitude")

        # Circling detection (needs at least 5 points)
        if len(track) >= 5:
            points = [(p[0], p[1]) for p in track]
            diameter = polygon_diameter(points)
            time_span = (track[-1][3] - track[0][3]).total_seconds()
            if time_span >= self.aircraft_circling_time and diameter <= self.aircraft_circling_radius:
                anomalies.append("Circling")

        # Vertical speed anomaly
        if vert_rate is not None:
            if vert_rate < -self.aircraft_rapid_descent_threshold:
                anomalies.append("Rapid descent")
            elif vert_rate > self.aircraft_rapid_climb_threshold:
                anomalies.append("Rapid climb")

        # Speed anomaly
        if speed is not None:
            if speed > self.aircraft_max_speed_knots:
                anomalies.append("Excessive speed")
            elif speed < self.aircraft_min_speed_knots:
                anomalies.append("Low speed")

        # Squawk emergency codes
        if self.aircraft_enable_squawk_alerts and squawk is not None:
            emergency = {"7500": "Hijack", "7600": "Radio failure", "7700": "Emergency"}
            if squawk in emergency:
                anomalies.append(f"Squawk {squawk} ({emergency[squawk]})")

        # Course deviation (if heading available)
        if heading is not None and prev is not None and prev[5] is not None:
            heading_change = abs(heading - prev[5])
            if heading_change > 180:
                heading_change = 360 - heading_change
            if heading_change > 30:  # sharp turn >30 deg
                anomalies.append("Sharp turn")

        return anomalies

    def update_device_status(self, mac, device_type):
        with self.db.db_lock:
            try:
                dets = self.db.get_detections_for_network(mac, device_type, limit=10000, days=self.analysis_days)
                if len(dets) < 3:
                    return
                rows = []
                for d in dets:
                    rows.append((
                        d['lat'] if d['lat'] is not None else '-',
                        d['lon'] if d['lon'] is not None else '-',
                        d['timestamp'],
                        d['rssi'],
                        d['alt']
                    ))
                if device_type == 'aircraft':
                    latest_alt = rows[-1][4]
                    if latest_alt != '-' and float(latest_alt) > self.aircraft_high_altitude_threshold:
                        return
                is_snooper_velocity = False
                max_velocity = 0.0
                prev_valid = None
                for row in rows:
                    lat, lon, ts = row[0], row[1], row[2]
                    if lat == '-' or lon == '-':
                        continue
                    if prev_valid:
                        dist = haversine(prev_valid[0], prev_valid[1], float(lat), float(lon))
                        t1 = prev_valid[2]
                        t2 = datetime.strptime(ts, '%Y-%m-%d %H:%M:%S')
                        seconds = (t2 - t1).total_seconds()
                        if seconds > 0 and seconds <= self.time_threshold_minutes * 60:
                            velocity = dist / seconds
                            max_velocity = max(max_velocity, velocity)
                            if dist > self.movement_threshold * 1609.34 or velocity > 1.5:
                                is_snooper_velocity = True
                    prev_valid = (float(lat), float(lon), datetime.strptime(ts, '%Y-%m-%d %H:%M:%S'))
                gps_detections = [(r[0], r[1], r[2]) for r in rows if r[0] != '-' and r[1] != '-']
                timestamps = [datetime.strptime(ts, '%Y-%m-%d %H:%M:%S') for _, _, ts in gps_detections]
                now = datetime.now()
                cluster_count = get_cluster_count([(lat, lon) for lat, lon, _ in gps_detections])
                weights = [0.4, 0.3, 0.2, 0.1]
                score = 0.0
                windows_hit = 0
                for i in range(4):
                    end_min = (i + 1) * 5
                    start_min = i * 5
                    start_time = now - timedelta(minutes=end_min)
                    end_time = now - timedelta(minutes=start_min)
                    if any(start_time <= ts < end_time for ts in timestamps):
                        score += weights[i]
                        windows_hit += 1
                score += 0.2 * max(0, windows_hit - 1)
                score += 0.1 * max(0, cluster_count - 1)
                score = min(1.0, score)
                is_snooper = 1 if (score >= self.persistence_threshold or is_snooper_velocity) else 0
                self.db.update_persistence(mac, device_type, score, windows_hit, cluster_count)
                self.db.update_snooper_status(mac, device_type, is_snooper)
                self.db.update_max_velocity(mac, device_type, max_velocity)
                if device_type in ['wifi', 'bluetooth']:
                    valid_dets = []
                    kf = KalmanFilter()
                    now = datetime.now()
                    for r in rows:
                        lat, lon, ts, rssi, alt = r
                        if lat != '-' and lon != '-' and rssi and -100 <= rssi <= -30:
                            filtered = kf.filter(rssi)
                            tx = self.options.get('tx_power_' + device_type, -20)
                            n = self.options.get('path_loss_n_' + device_type, 2.7)
                            dist = 10 ** ((tx - filtered) / (10 * n))
                            age = (now - datetime.strptime(ts, '%Y-%m-%d %H:%M:%S')).total_seconds() / 3600
                            valid_dets.append((float(lat), float(lon), float(alt or 0), dist, age))
                    if len(valid_dets) >= self.triangulation_min_points:
                        wts = [exp(-a) / max(d, 1) for _,_,_,d,a in valid_dets]
                        total = sum(wts) or 1
                        init_lat = sum(w * lat for w, (lat,_,_,_,_) in zip(wts, valid_dets)) / total
                        init_lon = sum(w * lon for w, (_,lon,_,_,_) in zip(wts, valid_dets)) / total
                        locations = [(d[0], d[1]) for d in valid_dets]
                        distances = [d[3] for d in valid_dets]
                        weights = [exp(-d[4]) for d in valid_dets]
                        pos, mse = trilaterate(locations, distances, weights, self.mse_threshold, initial_guess=(init_lat, init_lon))
                        if pos:
                            self.db.update_triangulated_position(mac, device_type, str(pos[0]), str(pos[1]), mse)
            except Exception as e:
                logging.error(f'[SnoopR] update_device_status error for {mac} ({device_type}): {e}')

    async def _bleak_scan_loop(self):
        while not self.stop_event.is_set():
            try:
                devices = await BleakScanner.discover(timeout=self.scan_duration, return_adv=True)
                for dev, adv in devices.values():
                    if not adv.rssi:
                        continue
                    mac = dev.address.upper()
                    if mac in self.whitelist_macs:
                        continue
                    name = dev.name or "Unknown"
                    if name in self.whitelist_ssids:
                        continue
                    vendor = self._lookup_oui_vendor(mac)
                    classification = self._classify_device(name, adv.manufacturer_data)
                    vulns = self._detect_vulnerabilities(adv)
                    anomalies = self._detect_anomalies(adv)
                    rogue = self._detect_rogue(vendor, name)
                    mesh = self._detect_mesh(adv)
                    kf = self._get_kalman(mac, 'bluetooth')
                    filtered_rssi = kf.filter(adv.rssi)
                    detection = (
                        mac, 'bluetooth', name, 'bluetooth', vendor, classification, rogue, mesh, vulns, anomalies,
                        '', adv.rssi, self.last_gps['latitude'], self.last_gps['longitude'], 0, '',
                        self.last_gps['altitude'], self.session_id
                    )
                    self._add_to_buffer(detection)
                logging.debug(f'[SnoopR] BLE scan complete, found {len(devices)} devices')
            except Exception as e:
                logging.error(f'[SnoopR] Bleak scan error: {e}')
            await asyncio.sleep(self.scan_interval)

    def _bleak_thread(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.loop.run_until_complete(self._bleak_scan_loop())

    def on_unfiltered_ap_list(self, agent, aps):
        if not self.ready:
            return
        gps = self._get_gps(agent)
        if gps and gps.get('Latitude') and gps.get('Longitude'):
            self.last_gps = {
                'latitude': str(gps['Latitude']),
                'longitude': str(gps['Longitude']),
                'altitude': str(gps.get('Altitude', '-'))
            }
            coords = (self.last_gps['latitude'], self.last_gps['longitude'])
        else:
            if not self.log_without_gps:
                return
            coords = ('-', '-')
        batch = []
        for ap in aps:
            mac = ap['mac']
            if mac in self.whitelist_macs:
                continue
            ssid = ap.get('hostname', '') or ''
            if ssid in self.whitelist_ssids:
                continue
            vendor = ap.get('vendor', 'Unknown')
            encryption = f"{ap.get('encryption','')}{ap.get('cipher','')}{ap.get('authentication','')}"
            rssi = ap['rssi']
            channel = ap.get('channel', 0)
            auth_mode = ap.get('authentication', '')
            lat, lon = coords
            if lat == '-' and ssid:
                lat_f, lon_f = self._wigle_geolocate(ssid)
                if lat_f and lon_f:
                    lat, lon = str(lat_f), str(lon_f)
                    logging.info(f'[SnoopR] WiGLE fallback for {ssid}: {lat},{lon}')
            kf = self._get_kalman(mac, 'wifi')
            filtered_rssi = kf.filter(rssi)
            detection_ap = (
                mac, 'wi-fi ap', ssid, 'wifi', vendor, 'WiFi AP', 0, 0, 'None', 'None',
                encryption, rssi, lat, lon, channel, auth_mode,
                self.last_gps['altitude'], self.session_id
            )
            batch.append(detection_ap)
            if 'clients' in ap:
                for client in ap['clients']:
                    c_mac = client if isinstance(client, str) else client.get('mac')
                    if not c_mac or c_mac in self.whitelist_macs:
                        continue
                    c_name = '' if isinstance(client, str) else client.get('hostname', '')
                    c_rssi = rssi if isinstance(client, str) else client.get('rssi', rssi)
                    kf_client = self._get_kalman(c_mac, 'wifi')
                    filtered_client_rssi = kf_client.filter(c_rssi)
                    detection_client = (
                        c_mac, 'wi-fi client', c_name, 'wifi', 'Unknown', 'WiFi Client', 0, 0, 'None', 'None',
                        encryption, c_rssi, lat, lon, channel, auth_mode,
                        self.last_gps['altitude'], self.session_id
                    )
                    batch.append(detection_client)
        if batch:
            self.db.add_detection_batch(batch)
            if self.mesh_enabled and self.mesh:
                for det in batch:
                    self.mesh.broadcast_detection({
                        'mac': det[0], 'type': det[1], 'name': det[2], 'device_type': det[3],
                        'encryption': det[10], 'signal_strength': det[11], 'latitude': det[12],
                        'longitude': det[13], 'channel': det[14], 'auth_mode': det[15],
                        'altitude': det[16], 'session_id': det[17]
                    })

    def on_loaded(self):
        logging.info('[SnoopR] Loading...')
        self._load_config()
        self._check_dependencies()
        self._load_oui_db()
        self._load_bluetooth_company_db()
        if not self.bluetooth_company_db and self.bluetooth_enabled:
            self._download_bt_company_db()
            self._load_bluetooth_company_db()

        self.db = Database(self.db_path)
        self.session_id = self.db.new_session()
        logging.info(f'[SnoopR] New session ID: {self.session_id}')

        self.aircraft_thread = AircraftProcessor(self, interval=30, cache_timeout=600)
        self.aircraft_thread.start()

        self.persistence_thread = PersistenceAnalyzer(self, interval=self.options.get('update_interval', 300), analysis_days=self.analysis_days)
        self.persistence_thread.start()

        if self.mesh_enabled:
            try:
                self.mesh = MeshNetwork(self.mesh_host, self.mesh_port, self.mesh_peers, self.mesh_key, HAS_CRYPTO)
                logging.info('[SnoopR] Mesh network initialized')
            except Exception as e:
                logging.error(f'[SnoopR] Mesh init failed: {e}')

        if self.bluetooth_enabled and HAS_BLEAK:
            self.bleak_task = threading.Thread(target=self._bleak_thread, daemon=True)
            self.bleak_task.start()
            logging.info('[SnoopR] Bleak BLE scanner started')

        self.web_handler = WebHandler(self)
        self.ready = True

    def on_unload(self, ui):
        logging.info('[SnoopR] Unloading...')
        self.stop_event.set()
        if self.bleak_task and self.bleak_task.is_alive():
            if self.loop:
                self.loop.call_soon_threadsafe(self.loop.stop)
            self.bleak_task.join(timeout=5)
        if self.aircraft_thread:
            self.aircraft_thread.stop()
            self.aircraft_thread.join(timeout=5)
        if self.persistence_thread:
            self.persistence_thread.stop()
            self.persistence_thread.join(timeout=5)
        self.db.prune_old_data(self.prune_days)
        self.db.disconnect()
        if self.mesh:
            self.mesh.close()
        self.ready = False

    def on_ui_setup(self, ui):
        if self.ui_enabled:
            ui.add_element('snoopr_wifi', LabeledValue(color=BLACK, label='WiFi:', value='0', position=(0, 90),
                                                       label_font=fonts.Small, text_font=fonts.Small))
            ui.add_element('snoopr_bt', LabeledValue(color=BLACK, label='BT:', value='0', position=(0, 100),
                                                     label_font=fonts.Small, text_font=fonts.Small))
            ui.add_element('snoopr_snoopers', LabeledValue(color=BLACK, label='Snoopers:', value='0', position=(0, 110),
                                                           label_font=fonts.Small, text_font=fonts.Small))
            ui.add_element('snoopr_persistence', LabeledValue(color=BLACK, label='High Pers:', value='0', position=(0, 120),
                                                              label_font=fonts.Small, text_font=fonts.Small))
            ui.add_element('snoopr_aircraft', LabeledValue(color=BLACK, label='Aircraft:', value='0', position=(0, 130),
                                                           label_font=fonts.Small, text_font=fonts.Small))

    def on_ui_update(self, ui):
        if self.ui_enabled and self.ready:
            now = time.time()
            if now - self.counts_last_update > self.counts_interval:
                self.counts_cache = self.db.get_network_counts()
                self.counts_last_update = now
            ui.set('snoopr_wifi', str(self.counts_cache['wifi']))
            ui.set('snoopr_bt', str(self.counts_cache['bluetooth']))
            ui.set('snoopr_snoopers', str(self.counts_cache['snoopers']))
            ui.set('snoopr_aircraft', str(self.counts_cache['aircraft']))
            ui.set('snoopr_persistence', str(self.counts_cache['high_persistence']))

    def on_webhook(self, path, request):
        if self.web_handler:
            return self.web_handler.handle(path, request)
        return "Not Found", 404

