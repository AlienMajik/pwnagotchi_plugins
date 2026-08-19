#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SnoopR v7.0.1 - Surveillance detection for Pwnagotchi.

Major correctness overhaul of 6.0.0. See CHANGELOG-v7.md for the full list.
Highlights:
  * All timestamps are handled in UTC end-to-end (persistence scoring, recent-device
    selection and pruning were previously silently broken outside UTC).
  * Analysis rows are iterated oldest-first, so velocity/movement actually computes.
  * Trilateration works in a local metre-plane instead of mixing degrees and metres.
  * OUI parser understands the Wireshark `manuf` format (the old parser loaded 0 entries,
    which in turn made _detect_rogue flag every device).
  * Threat alerts, mesh receive, filtered RSSI and OpenSky metadata are actually wired up.
  * OpenSky OAuth2 client-credentials flow (basic auth was retired 2026-03-18).
  * XSS-safe web UI, JSON data endpoint with pagination, bounded memory, no lock-holding
    during heavy analysis.
"""

import asyncio
import base64
import csv
import hashlib
import hmac
import html
import json
import logging
import os
import socket
import sqlite3
import struct
import threading
import time
from collections import OrderedDict, defaultdict, deque
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from math import atan2, cos, degrees, exp, radians, sin, sqrt
from threading import Lock

import requests

# Pwnagotchi imports
import pwnagotchi
import pwnagotchi.plugins as plugins
import pwnagotchi.ui.fonts as fonts
from flask import Response, abort, jsonify, render_template_string, stream_with_context
from pwnagotchi.ui.components import LabeledValue
from pwnagotchi.ui.view import BLACK

# Third-party (optional)
try:
    from bleak import BleakScanner
    HAS_BLEAK = True
except ImportError:
    HAS_BLEAK = False

try:
    from cryptography.hazmat.backends import default_backend
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    HAS_CRYPTO = True
except ImportError:
    HAS_CRYPTO = False

try:
    from scipy.optimize import minimize
    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False

SCHEMA_VERSION = 7
EARTH_R = 6371000.0
METERS_PER_MILE = 1609.344
MPS_TO_MPH = 2.236936
LOG = logging.getLogger(__name__)


# ---------------------------------------------------------------------
# Time helpers -- everything stored in the DB is UTC, naive, second precision.
# ---------------------------------------------------------------------

UTC = timezone.utc


def utcnow():
    return datetime.now(UTC)


def fmt_ts(dt=None):
    """Format a datetime the same way SQLite's CURRENT_TIMESTAMP does (UTC)."""
    dt = dt or utcnow()
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC).strftime('%Y-%m-%d %H:%M:%S')


def parse_ts(value):
    """Parse a DB timestamp (naive UTC) or ISO string into an aware UTC datetime."""
    if not value:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    text = str(value).strip()
    dt = None
    try:
        dt = datetime.fromisoformat(text.replace('Z', '+00:00'))
    except ValueError:
        for pattern in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%d'):
            try:
                dt = datetime.strptime(text[:len(pattern) + 4], pattern)
                break
            except ValueError:
                continue
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def cutoff_ts(days):
    return fmt_ts(utcnow() - timedelta(days=days))


# ---------------------------------------------------------------------
# Geometry helpers
# ---------------------------------------------------------------------

def haversine(lat1, lon1, lat2, lon2):
    """Great-circle distance in metres."""
    phi1, phi2 = radians(lat1), radians(lat2)
    dphi = radians(lat2 - lat1)
    dlambda = radians(lon2 - lon1)
    a = sin(dphi / 2) ** 2 + cos(phi1) * cos(phi2) * sin(dlambda / 2) ** 2
    return 2 * EARTH_R * atan2(sqrt(a), sqrt(1 - a))


def haversine_miles(lat1, lon1, lat2, lon2):
    return haversine(lat1, lon1, lat2, lon2) / METERS_PER_MILE


def project(lat, lon, lat0, lon0):
    """Equirectangular projection to a local metre plane centred on (lat0, lon0)."""
    x = radians(lon - lon0) * EARTH_R * cos(radians(lat0))
    y = radians(lat - lat0) * EARTH_R
    return x, y


def unproject(x, y, lat0, lon0):
    lat = lat0 + degrees(y / EARTH_R)
    denom = EARTH_R * cos(radians(lat0))
    lon = lon0 + (degrees(x / denom) if abs(denom) > 1e-9 else 0.0)
    return lat, lon


def cross(o, a, b):
    return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])


def convex_hull(points):
    points = sorted(set(points))
    if len(points) <= 2:
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
    """Max pairwise distance (metres) over the convex hull of (lat, lon) points."""
    hull = convex_hull(points) or list(points)
    if len(hull) < 2:
        return 0.0
    best = 0.0
    for i in range(len(hull)):
        for j in range(i + 1, len(hull)):
            d = haversine(hull[i][0], hull[i][1], hull[j][0], hull[j][1])
            if d > best:
                best = d
    return best


def point_in_polygon(lat, lon, polygon):
    """Ray casting. `polygon` is an ordered list of (lat, lon) pairs."""
    if not polygon or len(polygon) < 3:
        return False
    inside = False
    n = len(polygon)
    for i in range(n):
        lat1, lon1 = polygon[i]
        lat2, lon2 = polygon[(i + 1) % n]
        if (lat1 > lat) != (lat2 > lat):
            if abs(lat2 - lat1) > 1e-12:
                x_int = (lon2 - lon1) * (lat - lat1) / (lat2 - lat1) + lon1
                if lon < x_int:
                    inside = not inside
    return inside


# ---------------------------------------------------------------------
# MAC helpers
# ---------------------------------------------------------------------

def norm_mac(mac):
    if not mac:
        return ''
    return str(mac).strip().upper().replace('-', ':')


def mac_hex(mac):
    return norm_mac(mac).replace(':', '').replace('.', '')


def is_randomized_mac(mac):
    """Locally-administered bit set => randomised / private address."""
    h = mac_hex(mac)
    if len(h) < 2:
        return False
    try:
        return bool(int(h[:2], 16) & 0x02)
    except ValueError:
        return False


# ---------------------------------------------------------------------
# Small utilities
# ---------------------------------------------------------------------

class LRUDict(OrderedDict):
    """Bounded dict so long runs cannot leak memory."""

    def __init__(self, maxsize=4096, *args, **kwargs):
        self.maxsize = maxsize
        super().__init__(*args, **kwargs)

    def __setitem__(self, key, value):
        if key in self:
            super().__delitem__(key)
        super().__setitem__(key, value)
        while len(self) > self.maxsize:
            self.popitem(last=False)

    def get(self, key, default=None):
        if key in self:
            self.move_to_end(key)
            return self[key]
        return default


class KalmanFilter:
    """Simple scalar Kalman filter for RSSI smoothing."""

    def __init__(self, process_noise=0.008, measurement_noise=1.0,
                 initial_estimate=None, initial_certainty=1.0):
        self.mu = initial_estimate if initial_estimate is not None else -70.0
        self.sigma = initial_certainty
        self.R = process_noise
        self.Q = measurement_noise
        self.mu_bar = self.mu
        self.sigma_bar = self.sigma
        self.initialized = initial_estimate is not None
        self.last_used = time.time()

    def initialize(self, measurement):
        self.mu = float(measurement)
        self.sigma = 1.0
        self.initialized = True

    def predict(self):
        self.mu_bar = self.mu
        self.sigma_bar = self.sigma + self.R

    def update(self, measurement):
        K = self.sigma_bar / (self.sigma_bar + self.Q)
        self.mu = self.mu_bar + K * (float(measurement) - self.mu_bar)
        self.sigma = self.sigma_bar - K * self.sigma_bar

    def filter(self, measurement):
        self.last_used = time.time()
        if measurement is None:
            return self.mu
        if not self.initialized:
            self.initialize(measurement)
            return self.mu
        self.predict()
        self.update(measurement)
        return self.mu


def xml_escape(text):
    """Escape for XML text/attribute content (KML)."""
    if text is None:
        return ''
    return (str(text)
            .replace('&', '&amp;')
            .replace('<', '&lt;')
            .replace('>', '&gt;')
            .replace('"', '&quot;')
            .replace("'", '&apos;'))


def safe_float(value, default=None):
    try:
        if value is None or value == '-' or value == '':
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def valid_coords(lat, lon):
    """Reject nulls, the 0/0 null-island fix and out-of-range values."""
    lat_f, lon_f = safe_float(lat), safe_float(lon)
    if lat_f is None or lon_f is None:
        return None
    if abs(lat_f) < 1e-6 and abs(lon_f) < 1e-6:
        return None
    if not (-90.0 <= lat_f <= 90.0) or not (-180.0 <= lon_f <= 180.0):
        return None
    return lat_f, lon_f


# ---------------------------------------------------------------------
# Geofences
# ---------------------------------------------------------------------

class Geofence:
    """Circle: params = (lat, lon, radius_m). Polygon: params = [(lat, lon), ...]."""

    def __init__(self, name, fence_type, params):
        self.name = name
        self.type = fence_type
        self.params = params

    def contains(self, lat, lon):
        try:
            if self.type == 'circle':
                clat, clon, radius = self.params
                return haversine(clat, clon, lat, lon) <= radius
            if self.type == 'polygon':
                return point_in_polygon(lat, lon, self.params)
        except (TypeError, ValueError) as exc:
            LOG.error('[SnoopR] geofence %s eval error: %s', self.name, exc)
        return False

    def to_json(self):
        if self.type == 'circle':
            return {'name': self.name, 'type': 'circle',
                    'lat': self.params[0], 'lon': self.params[1], 'radius': self.params[2]}
        return {'name': self.name, 'type': 'polygon',
                'points': [[p[0], p[1]] for p in self.params]}

    @staticmethod
    def from_config(entry):
        name = entry.get('name', 'Unnamed')
        ftype = (entry.get('type') or '').lower()
        if ftype == 'circle':
            lat = float(entry['lat'])
            lon = float(entry['lon'])
            radius = float(entry['radius'])
            if not (-90 <= lat <= 90 and -180 <= lon <= 180 and radius > 0):
                raise ValueError('circle geofence out of range')
            return Geofence(name, 'circle', (lat, lon, radius))
        if ftype == 'polygon':
            pts = [(float(p[0]), float(p[1])) for p in entry['points']]
            if len(pts) < 3:
                raise ValueError('polygon needs >= 3 points')
            # Drop a duplicated closing vertex; the ray-cast wraps automatically.
            if pts[0] == pts[-1]:
                pts = pts[:-1]
            return Geofence(name, 'polygon', pts)
        raise ValueError('unknown geofence type %r' % ftype)


# ---------------------------------------------------------------------
# Database layer
# ---------------------------------------------------------------------

class Database:
    """SQLite wrapper. Every public method takes the lock for its own operation only;
    callers must never hold db_lock across long computations."""

    def __init__(self, path):
        self._path = path
        self._connection = None
        self.db_lock = threading.RLock()
        self._connect()

    # -- setup ---------------------------------------------------------
    def _connect(self):
        try:
            self._connection = sqlite3.connect(self._path, check_same_thread=False, timeout=30)
            self._connection.execute('PRAGMA journal_mode=WAL')
            self._connection.execute('PRAGMA synchronous=NORMAL')
            self._connection.execute('PRAGMA busy_timeout=30000')
            self._connection.execute('PRAGMA foreign_keys=ON')
            self._create_tables()
        except sqlite3.Error as exc:
            LOG.error('[SnoopR] DB connection failed: %s', exc)
            raise

    def _create_tables(self):
        with self._connection:
            self._connection.execute('''
                CREATE TABLE IF NOT EXISTS meta (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )''')
            self._connection.execute('''
                CREATE TABLE IF NOT EXISTS sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )''')
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
                    is_randomized INTEGER DEFAULT 0,
                    vulnerabilities TEXT DEFAULT '',
                    anomalies TEXT DEFAULT '',
                    is_snooper INTEGER DEFAULT 0,
                    snooper_reason TEXT DEFAULT '',
                    triangulated_lat TEXT,
                    triangulated_lon TEXT,
                    triangulated_mse REAL,
                    max_velocity REAL,
                    persistence_score REAL DEFAULT 0.0,
                    windows_hit INTEGER DEFAULT 0,
                    cluster_count INTEGER DEFAULT 0,
                    best_rssi INTEGER,
                    first_seen TEXT,
                    last_seen TEXT,
                    UNIQUE(mac, device_type)
                )''')
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
                )''')
            self._connection.execute('''
                CREATE TABLE IF NOT EXISTS aircraft_info (
                    icao24 TEXT PRIMARY KEY,
                    registration TEXT,
                    type TEXT,
                    owner TEXT,
                    status TEXT DEFAULT 'ok',
                    last_updated TEXT
                )''')
            for stmt in (
                'CREATE INDEX IF NOT EXISTS idx_det_net_ts ON detections(network_id, timestamp)',
                'CREATE INDEX IF NOT EXISTS idx_det_ts ON detections(timestamp)',
                'CREATE INDEX IF NOT EXISTS idx_det_session ON detections(session_id)',
                'CREATE INDEX IF NOT EXISTS idx_net_mac ON networks(mac)',
                'CREATE INDEX IF NOT EXISTS idx_net_last_seen ON networks(last_seen)',
                'CREATE INDEX IF NOT EXISTS idx_net_dtype ON networks(device_type)',
            ):
                self._connection.execute(stmt)
        self._migrate()

    def _migrate(self):
        cursor = self._connection.cursor()
        try:
            for col, col_type in (
                ('channel', 'INTEGER'),
                ('auth_mode', 'TEXT'),
                ('altitude', "TEXT DEFAULT '-'"),
                ('filtered_signal_strength', 'REAL'),
            ):
                try:
                    cursor.execute('ALTER TABLE detections ADD COLUMN %s %s' % (col, col_type))
                    LOG.info('[SnoopR] added detections.%s', col)
                except sqlite3.OperationalError:
                    pass

            for col, col_type in (
                ('triangulated_lat', 'TEXT'),
                ('triangulated_lon', 'TEXT'),
                ('triangulated_mse', 'REAL'),
                ('max_velocity', 'REAL'),
                ('vendor', "TEXT DEFAULT 'Unknown'"),
                ('persistence_score', 'REAL DEFAULT 0.0'),
                ('windows_hit', 'INTEGER DEFAULT 0'),
                ('cluster_count', 'INTEGER DEFAULT 0'),
                ('classification', "TEXT DEFAULT 'Unknown'"),
                ('is_rogue', 'INTEGER DEFAULT 0'),
                ('is_mesh', 'INTEGER DEFAULT 0'),
                ('is_randomized', 'INTEGER DEFAULT 0'),
                ('vulnerabilities', "TEXT DEFAULT ''"),
                ('anomalies', "TEXT DEFAULT ''"),
                ('snooper_reason', "TEXT DEFAULT ''"),
                ('best_rssi', 'INTEGER'),
                ('first_seen', 'TEXT'),
                ('last_seen', 'TEXT'),
            ):
                try:
                    cursor.execute('ALTER TABLE networks ADD COLUMN %s %s' % (col, col_type))
                    LOG.info('[SnoopR] added networks.%s', col)
                except sqlite3.OperationalError:
                    pass

            try:
                cursor.execute("ALTER TABLE aircraft_info ADD COLUMN status TEXT DEFAULT 'ok'")
            except sqlite3.OperationalError:
                pass

            # Older schemas allowed duplicate (mac, device_type) rows; enforce it now.
            try:
                cursor.execute('CREATE UNIQUE INDEX IF NOT EXISTS idx_net_unique '
                               'ON networks(mac, device_type)')
            except sqlite3.OperationalError as exc:
                LOG.warning('[SnoopR] could not add unique index on networks: %s '
                            '(duplicate rows present)', exc)

            cursor.execute('SELECT value FROM meta WHERE key = ?', ('schema_version',))
            row = cursor.fetchone()
            previous = int(row[0]) if row and str(row[0]).isdigit() else 0
            if previous < SCHEMA_VERSION:
                # Backfill last_seen/first_seen for pre-v7 rows so the recent-device
                # query does not skip them on the first run after upgrade.
                cursor.execute('''
                    UPDATE networks SET last_seen = (
                        SELECT MAX(d.timestamp) FROM detections d WHERE d.network_id = networks.id
                    ) WHERE last_seen IS NULL''')
                cursor.execute('''
                    UPDATE networks SET first_seen = (
                        SELECT MIN(d.timestamp) FROM detections d WHERE d.network_id = networks.id
                    ) WHERE first_seen IS NULL''')
                cursor.execute('INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)',
                               ('schema_version', str(SCHEMA_VERSION)))
                LOG.info('[SnoopR] schema migrated %s -> %s', previous, SCHEMA_VERSION)
            self._connection.commit()
        finally:
            cursor.close()

    def disconnect(self):
        with self.db_lock:
            if self._connection:
                try:
                    self._connection.commit()
                finally:
                    self._connection.close()
                    self._connection = None

    # -- writes --------------------------------------------------------
    def new_session(self):
        with self.db_lock, self._connection:
            cursor = self._connection.cursor()
            try:
                cursor.execute('INSERT INTO sessions DEFAULT VALUES')
                return cursor.lastrowid
            finally:
                cursor.close()

    def add_detection_batch(self, detections):
        """detections: iterable of Detection tuples (see Detection._fields)."""
        if not detections:
            return
        with self.db_lock:
            try:
                with self._connection:
                    cursor = self._connection.cursor()
                    try:
                        net_map = {}
                        for det in detections:
                            key = (det[0], det[3])
                            if key in net_map:
                                continue
                            cursor.execute('''
                                INSERT INTO networks
                                    (mac, type, name, device_type, vendor, classification,
                                     is_rogue, is_mesh, is_randomized, vulnerabilities, anomalies,
                                     first_seen, last_seen)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                                        CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                                ON CONFLICT(mac, device_type) DO UPDATE SET
                                    name = COALESCE(NULLIF(excluded.name, ''), networks.name),
                                    vendor = CASE WHEN excluded.vendor != 'Unknown'
                                                  THEN excluded.vendor ELSE networks.vendor END,
                                    classification = excluded.classification,
                                    is_rogue = excluded.is_rogue,
                                    is_mesh = excluded.is_mesh,
                                    is_randomized = excluded.is_randomized,
                                    vulnerabilities = excluded.vulnerabilities,
                                    anomalies = excluded.anomalies,
                                    last_seen = CURRENT_TIMESTAMP
                            ''', (det[0], det[1], det[2], det[3], det[4], det[5],
                                  det[6], det[7], det[8], det[9], det[10]))
                            cursor.execute(
                                'SELECT id FROM networks WHERE mac = ? AND device_type = ?', key)
                            row = cursor.fetchone()
                            if row:
                                net_map[key] = row[0]

                        rows = []
                        for det in detections:
                            net_id = net_map.get((det[0], det[3]))
                            if net_id is None:
                                continue
                            rows.append((det[18], net_id, det[11], det[12], det[13], det[14],
                                         det[17], det[15], det[16], det[19]))
                        cursor.executemany('''
                            INSERT INTO detections
                                (session_id, network_id, encryption, signal_strength,
                                 latitude, longitude, altitude, channel, auth_mode,
                                 filtered_signal_strength)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''', rows)

                        # Track the strongest RSSI ever seen; used to separate a device
                        # that follows you from one you merely drove past.
                        for det in detections:
                            rssi = det[12]
                            if rssi is None:
                                continue
                            cursor.execute('''
                                UPDATE networks SET best_rssi = MAX(COALESCE(best_rssi, -127), ?)
                                WHERE mac = ? AND device_type = ?''', (rssi, det[0], det[3]))
                        LOG.debug('[SnoopR] batch stored %d detections', len(rows))
                    finally:
                        cursor.close()
            except sqlite3.Error as exc:
                LOG.error('[SnoopR] add_detection_batch error: %s', exc)

    def _update(self, sql, params):
        with self.db_lock:
            try:
                with self._connection:
                    self._connection.execute(sql, params)
            except sqlite3.Error as exc:
                LOG.error('[SnoopR] update error (%s): %s', sql.split()[1:3], exc)

    def update_persistence(self, mac, device_type, score, windows_hit, cluster_count):
        self._update('UPDATE networks SET persistence_score = ?, windows_hit = ?, '
                     'cluster_count = ? WHERE mac = ? AND device_type = ?',
                     (score, windows_hit, cluster_count, mac, device_type))

    def update_snooper_status(self, mac, device_type, is_snooper, reason=''):
        self._update('UPDATE networks SET is_snooper = ?, snooper_reason = ? '
                     'WHERE mac = ? AND device_type = ?',
                     (int(is_snooper), reason, mac, device_type))

    def update_max_velocity(self, mac, device_type, max_velocity):
        self._update('UPDATE networks SET max_velocity = ? WHERE mac = ? AND device_type = ?',
                     (max_velocity, mac, device_type))

    def update_triangulated_position(self, mac, device_type, lat, lon, mse=None):
        self._update('UPDATE networks SET triangulated_lat = ?, triangulated_lon = ?, '
                     'triangulated_mse = ? WHERE mac = ? AND device_type = ?',
                     (lat, lon, mse, mac, device_type))

    def update_anomalies(self, mac, device_type, anomalies):
        self._update('UPDATE networks SET anomalies = ? WHERE mac = ? AND device_type = ?',
                     (anomalies, mac, device_type))

    def update_filtered_rssi_batch(self, pairs):
        """pairs: [(filtered_rssi, detection_id), ...]"""
        if not pairs:
            return
        with self.db_lock:
            try:
                with self._connection:
                    self._connection.executemany(
                        'UPDATE detections SET filtered_signal_strength = ? WHERE id = ?', pairs)
            except sqlite3.Error as exc:
                LOG.error('[SnoopR] update_filtered_rssi_batch error: %s', exc)

    # -- reads ---------------------------------------------------------
    def get_network_counts(self, persistence_threshold=0.85):
        with self.db_lock:
            try:
                cur = self._connection
                counts = {
                    'wifi': cur.execute(
                        "SELECT COUNT(*) FROM networks WHERE device_type='wifi'").fetchone()[0],
                    'bluetooth': cur.execute(
                        "SELECT COUNT(*) FROM networks WHERE device_type='bluetooth'").fetchone()[0],
                    'aircraft': cur.execute(
                        "SELECT COUNT(*) FROM networks WHERE device_type='aircraft'").fetchone()[0],
                    'snoopers': cur.execute(
                        'SELECT COUNT(*) FROM networks WHERE is_snooper=1').fetchone()[0],
                    'high_persistence': cur.execute(
                        'SELECT COUNT(*) FROM networks WHERE persistence_score >= ?',
                        (persistence_threshold,)).fetchone()[0],
                    'anomalous_aircraft': cur.execute(
                        "SELECT COUNT(*) FROM networks WHERE device_type='aircraft' "
                        "AND anomalies NOT IN ('', 'None')").fetchone()[0],
                }
                return counts
            except sqlite3.Error as exc:
                LOG.error('[SnoopR] get_network_counts error: %s', exc)
                return {'wifi': 0, 'bluetooth': 0, 'aircraft': 0, 'snoopers': 0,
                        'high_persistence': 0, 'anomalous_aircraft': 0}

    FILTERS = {
        'snoopers': 'n.is_snooper = 1',
        'bluetooth': "n.device_type = 'bluetooth'",
        'wifi': "n.device_type = 'wifi'",
        'aircraft': "n.device_type = 'aircraft'",
        'clients': "n.type = 'wi-fi client'",
        'anomalies': "n.anomalies NOT IN ('', 'None')",
        'randomized': 'n.is_randomized = 1',
    }
    SORTS = {
        'device_type': 'n.device_type ASC',
        'is_snooper': 'n.is_snooper DESC',
        'persistence': 'n.persistence_score DESC',
        'velocity': 'n.max_velocity DESC',
        'mac': 'n.mac ASC',
        'name': 'n.name ASC',
        'last_seen': 'n.last_seen DESC',
        'rssi': 'n.best_rssi DESC',
    }

    def count_networks(self, filter_by=None, persistence_threshold=0.85):
        where = ''
        params = []
        if filter_by == 'high_persistence':
            where = ' WHERE n.persistence_score >= ?'
            params.append(persistence_threshold)
        elif filter_by in self.FILTERS:
            where = ' WHERE ' + self.FILTERS[filter_by]
        with self.db_lock:
            try:
                return self._connection.execute(
                    'SELECT COUNT(*) FROM networks n' + where, params).fetchone()[0]
            except sqlite3.Error:
                return 0

    def get_all_networks(self, sort_by=None, filter_by=None, include_paths=False,
                         limit=200, offset=0, persistence_threshold=0.85,
                         path_limit=500, search=None):
        """Single query, no N+1: latest fix comes from a window function and trails are
        fetched in one extra query for the page's networks only."""
        with self.db_lock:
            try:
                query = '''
                    WITH latest AS (
                        SELECT network_id, latitude, longitude, signal_strength, timestamp,
                               ROW_NUMBER() OVER (PARTITION BY network_id
                                                  ORDER BY timestamp DESC) AS rn
                        FROM detections
                        WHERE latitude IS NOT NULL AND latitude != '-'
                          AND longitude IS NOT NULL AND longitude != '-'
                    ),
                    agg AS (
                        SELECT network_id,
                               MIN(timestamp) AS first_ts,
                               MAX(timestamp) AS last_ts,
                               COUNT(DISTINCT session_id) AS sessions_count,
                               COUNT(*) AS hits
                        FROM detections GROUP BY network_id
                    )
                    SELECT n.id, n.mac, n.type, n.name, n.device_type, n.vendor, n.classification,
                           datetime(a.first_ts, 'localtime'), datetime(a.last_ts, 'localtime'),
                           a.sessions_count, a.hits,
                           l.latitude, l.longitude,
                           n.is_snooper, n.snooper_reason,
                           n.triangulated_lat, n.triangulated_lon, n.triangulated_mse,
                           n.max_velocity, n.persistence_score, n.windows_hit, n.cluster_count,
                           n.anomalies, n.is_randomized, n.is_rogue, n.best_rssi,
                           ai.registration, ai.type, ai.owner
                    FROM networks n
                    JOIN agg a ON a.network_id = n.id
                    LEFT JOIN latest l ON l.network_id = n.id AND l.rn = 1
                    LEFT JOIN aircraft_info ai
                           ON n.device_type = 'aircraft' AND ai.icao24 = LOWER(n.mac)
                          AND ai.status = 'ok'
                    WHERE 1=1
                '''
                params = []
                if filter_by == 'high_persistence':
                    query += ' AND n.persistence_score >= ?'
                    params.append(persistence_threshold)
                elif filter_by in self.FILTERS:
                    query += ' AND ' + self.FILTERS[filter_by]
                if search:
                    query += (' AND (n.mac LIKE ? OR n.name LIKE ? OR n.vendor LIKE ?'
                              ' OR n.anomalies LIKE ?)')
                    like = '%%%s%%' % search
                    params.extend([like, like, like, like])
                query += ' ORDER BY ' + self.SORTS.get(sort_by, 'n.persistence_score DESC')
                query += ' LIMIT ? OFFSET ?'
                params.extend([int(limit), int(offset)])

                rows = self._connection.execute(query, params).fetchall()
                networks = []
                by_id = {}
                for row in rows:
                    (net_id, mac, type_, name, device_type, vendor, classification,
                     first_seen, last_seen, sessions_count, hits, last_lat, last_lon,
                     is_snooper, snooper_reason, tri_lat, tri_lon, tri_mse, max_velocity,
                     persistence, windows_hit, cluster_count, anomalies, is_randomized,
                     is_rogue, best_rssi, reg, ac_type, owner) = row
                    coords = valid_coords(tri_lat, tri_lon) or valid_coords(last_lat, last_lon)
                    net = {
                        'mac': mac,
                        'type': type_,
                        'name': name or 'Hidden',
                        'device_type': device_type,
                        'vendor': vendor or 'Unknown',
                        'classification': classification or 'Unknown',
                        'first_seen': first_seen,
                        'last_seen': last_seen,
                        'sessions_count': sessions_count or 0,
                        'hits': hits or 0,
                        'latitude': coords[0] if coords else None,
                        'longitude': coords[1] if coords else None,
                        'triangulated': bool(coords and valid_coords(tri_lat, tri_lon)),
                        'is_snooper': bool(is_snooper),
                        'snooper_reason': snooper_reason or '',
                        'triangulated_mse': round(tri_mse, 1) if tri_mse is not None else None,
                        'max_velocity_mph': (round(max_velocity * MPS_TO_MPH, 1)
                                             if max_velocity else None),
                        'persistence_score': round(float(persistence or 0.0), 3),
                        'windows_hit': windows_hit or 0,
                        'cluster_count': cluster_count or 0,
                        'anomalies': anomalies or 'None',
                        'is_randomized': bool(is_randomized),
                        'is_rogue': bool(is_rogue),
                        'best_rssi': best_rssi,
                        'registration': reg,
                        'aircraft_type': ac_type,
                        'owner': owner,
                    }
                    networks.append(net)
                    by_id[net_id] = net

                if include_paths and by_id:
                    placeholders = ','.join('?' * len(by_id))
                    path_rows = self._connection.execute('''
                        SELECT network_id, latitude, longitude,
                               datetime(timestamp, 'localtime'), signal_strength
                        FROM detections
                        WHERE network_id IN (%s)
                          AND latitude != '-' AND longitude != '-'
                        ORDER BY network_id, timestamp
                    ''' % placeholders, list(by_id.keys())).fetchall()
                    grouped = defaultdict(list)
                    for net_id, lat, lon, ts, rssi in path_rows:
                        coords = valid_coords(lat, lon)
                        if not coords or len(grouped[net_id]) >= path_limit:
                            continue
                        grouped[net_id].append({'latitude': coords[0], 'longitude': coords[1],
                                                'timestamp': ts, 'signal_strength': rssi})
                    for net_id, path in grouped.items():
                        if len(path) > 1:
                            by_id[net_id]['path'] = path
                return networks
            except sqlite3.Error as exc:
                LOG.error('[SnoopR] get_all_networks error: %s', exc)
                return []

    def get_detections_for_network(self, mac, device_type, limit=5000, days=None,
                                   ascending=True):
        """Rows come back oldest-first by default -- the analysis code depends on it."""
        with self.db_lock:
            try:
                query = '''
                    SELECT d.id, d.signal_strength, d.latitude, d.longitude, d.altitude,
                           d.timestamp, d.filtered_signal_strength, d.session_id
                    FROM detections d
                    JOIN networks n ON n.id = d.network_id
                    WHERE n.mac = ? AND n.device_type = ?
                '''
                params = [mac, device_type]
                if days:
                    query += ' AND d.timestamp >= ?'
                    params.append(cutoff_ts(days))
                # Take the most recent `limit` rows, then flip to chronological order.
                query += ' ORDER BY d.timestamp DESC LIMIT ?'
                params.append(int(limit))
                rows = self._connection.execute(query, params).fetchall()
            except sqlite3.Error as exc:
                LOG.error('[SnoopR] get_detections_for_network error: %s', exc)
                return []
        if ascending:
            rows = list(reversed(rows))
        return [{'id': r[0], 'rssi': r[1], 'lat': r[2], 'lon': r[3], 'alt': r[4],
                 'timestamp': r[5], 'filtered_rssi': r[6], 'session': r[7]} for r in rows]

    def get_recent_devices(self, days=7, exclude_types=('aircraft',)):
        with self.db_lock:
            try:
                query = 'SELECT mac, device_type FROM networks WHERE last_seen >= ?'
                params = [cutoff_ts(days)]
                if exclude_types:
                    query += ' AND device_type NOT IN (%s)' % ','.join('?' * len(exclude_types))
                    params.extend(exclude_types)
                return self._connection.execute(query, params).fetchall()
            except sqlite3.Error as exc:
                LOG.error('[SnoopR] get_recent_devices error: %s', exc)
                return []

    def get_network_meta(self, mac, device_type):
        with self.db_lock:
            try:
                row = self._connection.execute(
                    'SELECT is_randomized, best_rssi, is_snooper, name, vendor '
                    'FROM networks WHERE mac = ? AND device_type = ?',
                    (mac, device_type)).fetchone()
            except sqlite3.Error as exc:
                LOG.error('[SnoopR] get_network_meta error: %s', exc)
                return None
        if not row:
            return None
        return {'is_randomized': bool(row[0]), 'best_rssi': row[1],
                'is_snooper': bool(row[2]), 'name': row[3], 'vendor': row[4]}

    def get_aircraft_info(self, icao24):
        with self.db_lock:
            try:
                row = self._connection.execute(
                    'SELECT registration, type, owner, status, last_updated '
                    'FROM aircraft_info WHERE icao24 = ?', (icao24.lower(),)).fetchone()
                if row:
                    return {'registration': row[0], 'type': row[1], 'owner': row[2],
                            'status': row[3] or 'ok', 'last_updated': row[4]}
            except sqlite3.Error as exc:
                LOG.error('[SnoopR] get_aircraft_info error: %s', exc)
            return None

    def update_aircraft_info(self, icao24, info, status='ok'):
        self._update('''INSERT OR REPLACE INTO aircraft_info
                        (icao24, registration, type, owner, status, last_updated)
                        VALUES (?, ?, ?, ?, ?, ?)''',
                     (icao24.lower(), (info or {}).get('registration'), (info or {}).get('type'),
                      (info or {}).get('owner'), status, fmt_ts()))

    def prune_old_data(self, days, vacuum=False):
        if days is None or days < 1:
            LOG.warning('[SnoopR] prune_days=%s is invalid; skipping prune', days)
            return
        with self.db_lock:
            try:
                cutoff = cutoff_ts(days)
                with self._connection:
                    self._connection.execute('DELETE FROM detections WHERE timestamp < ?',
                                             (cutoff,))
                    self._connection.execute(
                        'DELETE FROM networks WHERE id NOT IN '
                        '(SELECT DISTINCT network_id FROM detections)')
                    self._connection.execute(
                        'DELETE FROM sessions WHERE id NOT IN '
                        '(SELECT DISTINCT session_id FROM detections)')
                    self._connection.execute(
                        "DELETE FROM aircraft_info WHERE status = 'notfound' AND last_updated < ?",
                        (cutoff_ts(7),))
                if vacuum:
                    # VACUUM cannot run inside a transaction.
                    self._connection.execute('VACUUM')
                LOG.info('[SnoopR] pruned data older than %s days (vacuum=%s)', days, vacuum)
            except sqlite3.Error as exc:
                LOG.error('[SnoopR] prune error: %s', exc)


# ---------------------------------------------------------------------
# Detection record
# ---------------------------------------------------------------------

DETECTION_FIELDS = (
    'mac', 'type', 'name', 'device_type', 'vendor', 'classification', 'is_rogue', 'is_mesh',
    'is_randomized', 'vulnerabilities', 'anomalies', 'encryption', 'signal_strength',
    'latitude', 'longitude', 'channel', 'auth_mode', 'altitude', 'session_id', 'filtered_rssi',
)


def make_detection(mac, type_, name, device_type, vendor='Unknown', classification='Unknown',
                   is_rogue=0, is_mesh=0, is_randomized=0, vulnerabilities='None',
                   anomalies='None', encryption='', signal_strength=None, latitude=None,
                   longitude=None, channel=0, auth_mode='', altitude='-', session_id=None,
                   filtered_rssi=None):
    return (norm_mac(mac) if device_type != 'aircraft' else str(mac).lower(),
            type_, name, device_type, vendor, classification, int(is_rogue), int(is_mesh),
            int(is_randomized), vulnerabilities, anomalies, encryption, signal_strength,
            latitude, longitude, channel, auth_mode, altitude, session_id, filtered_rssi)


# ---------------------------------------------------------------------
# Mesh network (authenticated, replay-protected)
# ---------------------------------------------------------------------

MESH_MAGIC = b'SNP7'
MESH_MAX_SKEW = 120  # seconds


class MeshNetwork:
    """UDP peer sharing. A pre-shared key is mandatory: every frame is HMAC-authenticated
    and, when `cryptography` is present, AES-GCM encrypted. Unauthenticated frames used to
    be inserted straight into the database."""

    def __init__(self, host_ip, port, peers, shared_key, has_crypto, allow_plaintext=False):
        if not shared_key:
            raise ValueError('mesh_key is required when mesh_enabled = true')
        self.host_ip = host_ip
        self.port = int(port)
        self.peers = list(peers or [])
        self.digest_key = hashlib.sha256(('snoopr-hmac|' + shared_key).encode()).digest()
        self.cipher_key = hashlib.sha256(('snoopr-aes|' + shared_key).encode()).digest()[:32]
        self.has_crypto = bool(has_crypto)
        self.allow_plaintext = allow_plaintext
        self.backend = default_backend() if self.has_crypto else None
        if not self.has_crypto:
            if not allow_plaintext:
                raise RuntimeError('cryptography not installed; install it or set '
                                   'mesh_allow_plaintext = true (payloads will be '
                                   'authenticated but not encrypted)')
            LOG.warning('[SnoopR] mesh payloads are authenticated but NOT encrypted '
                        '(cryptography missing)')
        self._seen_nonces = deque(maxlen=4096)
        self._seen_set = set()
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.bind((host_ip, self.port))
        self.socket.settimeout(1.0)

    # -- framing -------------------------------------------------------
    def _seal(self, plaintext):
        if self.has_crypto:
            iv = os.urandom(12)
            cipher = Cipher(algorithms.AES(self.cipher_key), modes.GCM(iv), backend=self.backend)
            enc = cipher.encryptor()
            body = enc.update(plaintext) + enc.finalize()
            payload = b'\x01' + iv + enc.tag + body
        else:
            payload = b'\x00' + plaintext
        header = MESH_MAGIC + struct.pack('!d', time.time()) + os.urandom(8)
        frame = header + payload
        return frame + hmac.new(self.digest_key, frame, hashlib.sha256).digest()[:16]

    def _open(self, frame):
        if len(frame) < 4 + 8 + 8 + 1 + 16:
            raise ValueError('frame too short')
        body, tag = frame[:-16], frame[-16:]
        expected = hmac.new(self.digest_key, body, hashlib.sha256).digest()[:16]
        if not hmac.compare_digest(tag, expected):
            raise ValueError('bad HMAC')
        if body[:4] != MESH_MAGIC:
            raise ValueError('bad magic')
        sent_at = struct.unpack('!d', body[4:12])[0]
        if abs(time.time() - sent_at) > MESH_MAX_SKEW:
            raise ValueError('stale frame')
        nonce = body[12:20]
        if nonce in self._seen_set:
            raise ValueError('replayed frame')
        if len(self._seen_nonces) == self._seen_nonces.maxlen:
            self._seen_set.discard(self._seen_nonces[0])
        self._seen_nonces.append(nonce)
        self._seen_set.add(nonce)
        payload = body[20:]
        if payload[:1] == b'\x01':
            if not self.has_crypto:
                raise ValueError('encrypted frame but no crypto backend')
            iv, gcm_tag, ct = payload[1:13], payload[13:29], payload[29:]
            cipher = Cipher(algorithms.AES(self.cipher_key), modes.GCM(iv, gcm_tag),
                            backend=self.backend)
            dec = cipher.decryptor()
            return dec.update(ct) + dec.finalize()
        if not self.allow_plaintext:
            raise ValueError('plaintext frame rejected')
        return payload[1:]

    # -- io ------------------------------------------------------------
    def broadcast_detections(self, detections):
        if not self.peers or not detections:
            return
        try:
            frame = self._seal(json.dumps(detections, separators=(',', ':')).encode('utf-8'))
        except Exception as exc:  # noqa: BLE001 - never let mesh break scanning
            LOG.error('[SnoopR] mesh seal failed: %s', exc)
            return
        if len(frame) > 60000:
            LOG.debug('[SnoopR] mesh frame too large (%d bytes), skipping', len(frame))
            return
        for peer in self.peers:
            try:
                self.socket.sendto(frame, (peer, self.port))
            except OSError as exc:
                LOG.debug('[SnoopR] mesh send to %s failed: %s', peer, exc)

    REQUIRED = ('mac', 'device_type')

    def _validate(self, item):
        if not isinstance(item, dict):
            return None
        if any(k not in item for k in self.REQUIRED):
            return None
        mac = str(item['mac'])[:32]
        device_type = str(item['device_type'])[:16]
        if device_type not in ('wifi', 'bluetooth', 'aircraft'):
            return None
        coords = valid_coords(item.get('latitude'), item.get('longitude'))
        rssi = item.get('signal_strength')
        if rssi is not None:
            try:
                rssi = max(-127, min(0, int(rssi)))
            except (TypeError, ValueError):
                rssi = None
        return make_detection(
            mac=mac, type_=str(item.get('type', device_type))[:32],
            name=str(item.get('name', ''))[:64], device_type=device_type,
            vendor=str(item.get('vendor', 'Unknown'))[:64],
            classification='Mesh peer',
            is_randomized=is_randomized_mac(mac) if device_type != 'aircraft' else 0,
            encryption=str(item.get('encryption', ''))[:64], signal_strength=rssi,
            latitude=str(coords[0]) if coords else '-',
            longitude=str(coords[1]) if coords else '-',
            channel=int(item.get('channel') or 0),
            auth_mode=str(item.get('auth_mode', ''))[:32],
            altitude=str(item.get('altitude', '-'))[:16])

    def receive_once(self, db, session_id):
        try:
            frame, addr = self.socket.recvfrom(65535)
        except (socket.timeout, BlockingIOError):
            return 0
        except OSError:
            return 0
        try:
            payload = json.loads(self._open(frame).decode('utf-8'))
        except Exception as exc:  # noqa: BLE001
            LOG.debug('[SnoopR] mesh frame from %s rejected: %s', addr[0], exc)
            return 0
        items = payload if isinstance(payload, list) else [payload]
        batch = []
        for item in items[:200]:
            det = self._validate(item)
            if det:
                batch.append(det[:18] + (session_id, det[19]))
        if batch:
            db.add_detection_batch(batch)
        return len(batch)

    def close(self):
        try:
            self.socket.close()
        except OSError:
            pass


class MeshReceiver(threading.Thread):
    """The 6.x code had a receive method that was never called."""

    def __init__(self, plugin):
        super().__init__(daemon=True, name='snoopr-mesh')
        self.plugin = plugin

    def run(self):
        while not self.plugin.stop_event.is_set():
            try:
                self.plugin.mesh.receive_once(self.plugin.db, self.plugin.session_id)
            except Exception as exc:  # noqa: BLE001
                LOG.error('[SnoopR] mesh receiver error: %s', exc)
                self.plugin.stop_event.wait(1.0)


# ---------------------------------------------------------------------
# OpenSky metadata client (OAuth2 client-credentials)
# ---------------------------------------------------------------------

OPENSKY_TOKEN_URL = ('https://auth.opensky-network.org/auth/realms/opensky-network/'
                     'protocol/openid-connect/token')
OPENSKY_META_URL = 'https://opensky-network.org/api/metadata/aircraft/icao/%s'


class OpenSkyClient:
    """Basic auth was retired on 2026-03-18; only the client-credentials flow works now.
    Tokens live ~30 minutes and are refreshed a minute early."""

    def __init__(self, client_id=None, client_secret=None, timeout=10):
        self.client_id = client_id or ''
        self.client_secret = client_secret or ''
        self.timeout = timeout
        self._token = None
        self._token_expiry = 0.0
        self._lock = Lock()
        self._session = requests.Session()
        self.endpoint_available = True

    @property
    def configured(self):
        return bool(self.client_id and self.client_secret)

    def _get_token(self):
        with self._lock:
            if self._token and time.time() < self._token_expiry:
                return self._token
            if not self.configured:
                return None
            try:
                resp = self._session.post(
                    OPENSKY_TOKEN_URL,
                    data={'grant_type': 'client_credentials',
                          'client_id': self.client_id,
                          'client_secret': self.client_secret},
                    headers={'Content-Type': 'application/x-www-form-urlencoded'},
                    timeout=self.timeout)
                if resp.status_code != 200:
                    LOG.warning('[SnoopR] OpenSky token request failed: HTTP %s',
                                resp.status_code)
                    self._token_expiry = time.time() + 300  # back off
                    return None
                data = resp.json()
                self._token = data.get('access_token')
                self._token_expiry = time.time() + max(60, int(data.get('expires_in', 1800)) - 60)
                return self._token
            except (requests.RequestException, ValueError) as exc:
                LOG.warning('[SnoopR] OpenSky token error: %s', exc)
                self._token_expiry = time.time() + 300
                return None

    def lookup(self, icao24):
        """Returns (info_dict_or_None, status) where status is 'ok'|'notfound'|'error'."""
        if not self.endpoint_available:
            return None, 'error'
        headers = {'User-Agent': 'SnoopR/7.0 (pwnagotchi plugin)'}
        token = self._get_token()
        if token:
            headers['Authorization'] = 'Bearer %s' % token
        try:
            resp = self._session.get(OPENSKY_META_URL % icao24.lower(),
                                     headers=headers, timeout=self.timeout)
        except requests.RequestException as exc:
            LOG.debug('[SnoopR] OpenSky lookup failed for %s: %s', icao24, exc)
            return None, 'error'
        if resp.status_code == 404:
            return None, 'notfound'
        if resp.status_code in (401, 403):
            LOG.warning('[SnoopR] OpenSky rejected credentials (HTTP %s). Create an API '
                        'client at opensky-network.org and set opensky_client_id / '
                        'opensky_client_secret.', resp.status_code)
            return None, 'error'
        if resp.status_code == 429:
            LOG.info('[SnoopR] OpenSky rate limited; backing off')
            self._token_expiry = min(self._token_expiry, time.time() + 60)
            return None, 'error'
        if resp.status_code != 200:
            if resp.status_code in (410, 501):
                LOG.warning('[SnoopR] OpenSky metadata endpoint unavailable (HTTP %s); '
                            'disabling lookups for this session. Use aircraft_db_csv for '
                            'offline metadata.', resp.status_code)
                self.endpoint_available = False
            return None, 'error'
        try:
            data = resp.json()
        except ValueError:
            return None, 'error'
        if not isinstance(data, dict) or not data:
            return None, 'notfound'
        return ({'registration': data.get('registration'),
                 'type': data.get('typecode') or data.get('model'),
                 'owner': data.get('owner') or data.get('operator')}, 'ok')


class LocalAircraftDB:
    """Offline fallback: a CSV with icao24,registration,typecode,owner-ish columns
    (the standard crowd-sourced aircraft database export)."""

    def __init__(self, path):
        self.path = path
        self.rows = {}
        self.load()

    def load(self):
        if not self.path or not os.path.exists(self.path):
            return
        try:
            with open(self.path, 'r', encoding='utf-8', errors='ignore', newline='') as handle:
                reader = csv.DictReader(handle)
                for row in reader:
                    key = (row.get('icao24') or row.get('icao') or row.get('ModeS') or '').lower()
                    if not key:
                        continue
                    self.rows[key.strip("'").strip()] = {
                        'registration': (row.get('registration') or row.get('Registration')
                                         or '').strip(),
                        'type': (row.get('typecode') or row.get('ICAOTypeCode')
                                 or row.get('model') or '').strip(),
                        'owner': (row.get('owner') or row.get('operator')
                                  or row.get('RegisteredOwners') or '').strip(),
                    }
            LOG.info('[SnoopR] loaded %d local aircraft records', len(self.rows))
        except (OSError, csv.Error) as exc:
            LOG.error('[SnoopR] aircraft CSV load failed: %s', exc)

    def lookup(self, icao24):
        return self.rows.get(icao24.lower())


# ---------------------------------------------------------------------
# Analysis helpers
# ---------------------------------------------------------------------

def grid_cluster_count(points, cell_meters=100.0):
    """O(n) spatial bucketing; the 6.x implementation was O(n^2) over every detection."""
    if not points:
        return 0, []
    lat0 = sum(p[0] for p in points) / len(points)
    lon_scale = max(cos(radians(lat0)), 1e-6)
    cells = {}
    for lat, lon in points:
        key = (int((lat * 111320.0) // cell_meters),
               int((lon * 111320.0 * lon_scale) // cell_meters))
        bucket = cells.setdefault(key, [0, 0.0, 0.0])
        bucket[0] += 1
        bucket[1] += lat
        bucket[2] += lon
    centres = [(b[1] / b[0], b[2] / b[0], b[0]) for b in cells.values()]
    return len(cells), centres


def euclidean(x1, y1, x2, y2):
    return sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)


def nelder_mead(f, x_start, step=1.0, no_improve_thr=1e-6, no_improv_break=20,
                max_iter=400, alpha=1.0, gamma=2.0, rho=0.5, sigma=0.5):
    dim = len(x_start)
    prev_best = f(x_start)
    no_improv = 0
    res = [[list(x_start), prev_best]]
    for i in range(dim):
        x = list(x_start)
        x[i] += step
        res.append([x, f(x)])
    iters = 0
    while True:
        res.sort(key=lambda item: item[1])
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
            res[-1] = [xr, rscore]
            continue
        if rscore < res[0][1]:
            xe = [x0[i] + gamma * (x0[i] - res[-1][0][i]) for i in range(dim)]
            escore = f(xe)
            res[-1] = [xe, escore] if escore < rscore else [xr, rscore]
            continue
        xc = [x0[i] + rho * (x0[i] - res[-1][0][i]) for i in range(dim)]
        cscore = f(xc)
        if cscore < res[-1][1]:
            res[-1] = [xc, cscore]
            continue
        x1 = res[0][0]
        res = [[[x1[i] + sigma * (tup[0][i] - x1[i]) for i in range(dim)], 0.0] for tup in res]
        for item in res:
            item[1] = f(item[0])


def trilaterate(samples, mse_threshold_m2=2500.0):
    """samples: [(lat, lon, distance_m, weight), ...].

    Everything is solved in a local metre plane. The 6.x version minimised a mixture of
    degrees (positions) and metres (path-loss distances), so results were meaningless.
    Returns (lat, lon, mse_m2) or (None, None, None).
    """
    samples = [s for s in samples if s[2] is not None and s[2] > 0]
    if len(samples) < 3:
        return None, None, None
    total_w = sum(s[3] for s in samples) or 1.0
    lat0 = sum(s[0] * s[3] for s in samples) / total_w
    lon0 = sum(s[1] * s[3] for s in samples) / total_w

    projected = []
    for lat, lon, dist, weight in samples:
        x, y = project(lat, lon, lat0, lon0)
        projected.append((x, y, dist, weight))

    def objective(vec):
        err = 0.0
        for x, y, dist, weight in projected:
            err += weight * (euclidean(vec[0], vec[1], x, y) - dist) ** 2
        return err / total_w

    # Start at the weighted centroid of the nearest few observations.
    nearest = sorted(projected, key=lambda p: p[2])[:max(3, len(projected) // 3)]
    guess = [sum(p[0] for p in nearest) / len(nearest),
             sum(p[1] for p in nearest) / len(nearest)]

    if HAS_SCIPY:
        try:
            result = minimize(objective, guess, method='Nelder-Mead',
                              options={'xatol': 0.5, 'fatol': 0.5, 'maxiter': 800})
            best, mse = list(result.x), float(result.fun)
        except Exception as exc:  # noqa: BLE001
            LOG.debug('[SnoopR] scipy trilateration failed (%s), falling back', exc)
            best, mse = nelder_mead(objective, guess, step=25.0)
    else:
        best, mse = nelder_mead(objective, guess, step=25.0)

    if mse > mse_threshold_m2:
        centroid = [sum(p[0] * p[3] for p in projected) / total_w,
                    sum(p[1] * p[3] for p in projected) / total_w]
        centroid_mse = objective(centroid)
        if centroid_mse < mse:
            best, mse = centroid, centroid_mse
        if mse > mse_threshold_m2:
            return None, None, mse

    lat, lon = unproject(best[0], best[1], lat0, lon0)
    if valid_coords(lat, lon) is None:
        return None, None, None
    return lat, lon, mse


# ---------------------------------------------------------------------
# Aircraft feed normalisation
# ---------------------------------------------------------------------

def normalise_aircraft_record(plane):
    """Accepts dump1090/readsb/tar1090/skyhigh field spellings."""
    if not isinstance(plane, dict):
        return None
    icao = (plane.get('icao24') or plane.get('hex') or plane.get('icao')
            or plane.get('ModeS') or '')
    icao = str(icao).strip().lower().lstrip('~')
    if not icao:
        return None

    lat = safe_float(plane.get('latitude', plane.get('lat')))
    lon = safe_float(plane.get('longitude', plane.get('lon')))

    raw_alt = plane.get('alt_baro', plane.get('altitude', plane.get('alt',
                        plane.get('alt_geom', plane.get('geom_alt')))))
    on_ground = False
    if isinstance(raw_alt, str) and raw_alt.strip().lower() == 'ground':
        alt, on_ground = 0.0, True
    else:
        alt = safe_float(raw_alt)
    if plane.get('on_ground') or plane.get('ground'):
        on_ground = True

    callsign = (plane.get('callsign') or plane.get('flight') or '').strip() or 'UNKNOWN'
    speed = safe_float(plane.get('gs', plane.get('speed', plane.get('velocity',
                       plane.get('tas')))))
    heading = safe_float(plane.get('track', plane.get('heading',
                         plane.get('true_track', plane.get('mag_heading')))))
    vert = safe_float(plane.get('baro_rate', plane.get('vert_rate',
                      plane.get('geom_rate', plane.get('vertical_rate')))))

    squawk = plane.get('squawk')
    if squawk is not None:
        try:
            squawk = str(int(squawk)).zfill(4) if not isinstance(squawk, str) else squawk.strip()
        except (TypeError, ValueError):
            squawk = str(squawk).strip()
        if not squawk.isdigit():
            squawk = None

    seen_pos = safe_float(plane.get('seen_pos', plane.get('seen')), None)
    return {'icao': icao, 'lat': lat, 'lon': lon, 'alt': alt, 'on_ground': on_ground,
            'callsign': callsign, 'speed': speed, 'heading': heading, 'vert_rate': vert,
            'squawk': squawk, 'seen_pos': seen_pos}


def iter_aircraft_payload(payload):
    """dump1090 emits {"now":..,"aircraft":[...]}; older tools emit a list or a dict-of-dicts."""
    if isinstance(payload, dict):
        for key in ('aircraft', 'states', 'planes', 'data'):
            value = payload.get(key)
            if isinstance(value, list):
                return value
        return list(payload.values())
    if isinstance(payload, list):
        return payload
    return []


# ---------------------------------------------------------------------
# Background threads
# ---------------------------------------------------------------------

class StoppableThread(threading.Thread):
    def __init__(self, plugin, interval, name):
        super().__init__(daemon=True, name=name)
        self.plugin = plugin
        self.interval = interval
        self.stop_event = threading.Event()

    def stop(self):
        self.stop_event.set()

    def run(self):
        while not self.stop_event.wait(self.interval):
            if self.plugin.stop_event.is_set():
                return
            try:
                self.tick()
            except Exception as exc:  # noqa: BLE001
                LOG.error('[SnoopR] %s error: %s', self.name, exc)

    def tick(self):
        raise NotImplementedError


class AircraftProcessor(StoppableThread):
    def __init__(self, plugin, interval=15, cache_timeout=600):
        super().__init__(plugin, interval, 'snoopr-aircraft')
        self.db = plugin.db
        self.cache_timeout = cache_timeout
        self.cache = LRUDict(maxsize=2048)
        self.last_mtime = 0.0
        self.warned_missing = False
        self.executor = ThreadPoolExecutor(max_workers=2,
                                           thread_name_prefix='snoopr-opensky')
        self.pending_lookups = set()
        self._lookup_lock = Lock()

    def stop(self):
        super().stop()
        self.executor.shutdown(wait=False)

    # -- metadata ------------------------------------------------------
    def _queue_lookup(self, icao):
        cached = self.db.get_aircraft_info(icao)
        if cached:
            last = parse_ts(cached.get('last_updated'))
            ttl = timedelta(days=30) if cached.get('status') == 'ok' else timedelta(days=7)
            if last and (utcnow() - last) < ttl:
                return
        with self._lookup_lock:
            if icao in self.pending_lookups or len(self.pending_lookups) > 64:
                return
            self.pending_lookups.add(icao)
        try:
            self.executor.submit(self._do_lookup, icao)
        except RuntimeError:
            with self._lookup_lock:
                self.pending_lookups.discard(icao)

    def _do_lookup(self, icao):
        try:
            local = self.plugin.local_aircraft_db.lookup(icao) if self.plugin.local_aircraft_db \
                else None
            if local and any(local.values()):
                self.db.update_aircraft_info(icao, local, 'ok')
                return
            if not self.plugin.opensky or not self.plugin.opensky.endpoint_available:
                return
            info, status = self.plugin.opensky.lookup(icao)
            if status == 'ok':
                self.db.update_aircraft_info(icao, info, 'ok')
            elif status == 'notfound':
                # Negative caching: 6.x retried unknown ICAOs on every single poll forever.
                self.db.update_aircraft_info(icao, {}, 'notfound')
        except Exception as exc:  # noqa: BLE001
            LOG.debug('[SnoopR] aircraft metadata lookup failed for %s: %s', icao, exc)
        finally:
            with self._lookup_lock:
                self.pending_lookups.discard(icao)

    # -- main loop -----------------------------------------------------
    def tick(self):
        path = self.plugin.aircraft_file
        if not path or not os.path.exists(path):
            if not self.warned_missing:
                LOG.warning('[SnoopR] aircraft file %s not present; aircraft tracking idle', path)
                self.warned_missing = True
            return
        self.warned_missing = False
        try:
            mtime = os.path.getmtime(path)
            if mtime <= self.last_mtime:
                return
            self.last_mtime = mtime
            with open(path, 'r', encoding='utf-8', errors='ignore') as handle:
                payload = json.load(handle)
        except (OSError, json.JSONDecodeError) as exc:
            LOG.error('[SnoopR] aircraft file error: %s', exc)
            return

        now = utcnow()
        batch = []
        for raw in iter_aircraft_payload(payload):
            plane = normalise_aircraft_record(raw)
            if not plane:
                continue
            coords = valid_coords(plane['lat'], plane['lon'])
            if not coords:
                continue
            lat, lon = coords
            icao = plane['icao']

            # Feed every position into the behavioural tracker. 6.x only called the
            # detector when the aircraft had moved >500 m, which made the <=500 m
            # circling test impossible to satisfy.
            anomalies = self.plugin.detect_aircraft_anomalies(plane, lat, lon, now)
            for fence in self.plugin.geofences:
                if fence.contains(lat, lon):
                    anomalies.append('Geofence:%s' % fence.name)

            cached = self.cache.get(icao)
            should_store = False
            if cached is None:
                should_store = True
            else:
                moved = haversine(cached['lat'], cached['lon'], lat, lon)
                if (moved > self.plugin.aircraft_move_threshold
                        or cached['callsign'] != plane['callsign']
                        or cached['alt'] != plane['alt']
                        or set(anomalies) != cached['anomalies']
                        or (now - cached['ts']).total_seconds() > self.cache_timeout):
                    should_store = True

            if not should_store:
                continue

            new_anomalies = set(anomalies) - (cached['anomalies'] if cached else set())
            self.cache[icao] = {'lat': lat, 'lon': lon, 'alt': plane['alt'],
                                'callsign': plane['callsign'], 'ts': now,
                                'anomalies': set(anomalies)}

            anomalies_str = ', '.join(sorted(set(anomalies))) if anomalies else 'None'
            alt_str = 'ground' if plane['on_ground'] else (
                str(int(plane['alt'])) if plane['alt'] is not None else '-')
            batch.append(make_detection(
                mac=icao, type_='aircraft', name=plane['callsign'], device_type='aircraft',
                vendor='Aircraft', classification='Aircraft', anomalies=anomalies_str,
                signal_strength=None, latitude=str(lat), longitude=str(lon),
                altitude=alt_str, session_id=self.plugin.session_id))
            self.db.update_anomalies(icao, 'aircraft', anomalies_str)

            for anomaly in new_anomalies:
                if self.plugin.is_alertable(anomaly):
                    self.plugin.raise_alert(
                        'aircraft', '%s (%s): %s' % (plane['callsign'], icao.upper(), anomaly),
                        {'icao': icao, 'lat': lat, 'lon': lon, 'anomaly': anomaly})

            self._queue_lookup(icao)

        if batch:
            self.db.add_detection_batch(batch)
            LOG.info('[SnoopR] aircraft: stored %d position updates', len(batch))


class PersistenceAnalyzer(StoppableThread):
    def __init__(self, plugin, interval=300, analysis_days=7):
        super().__init__(plugin, interval, 'snoopr-analysis')
        self.analysis_days = analysis_days

    def tick(self):
        started = time.time()
        devices = self.plugin.db.get_recent_devices(days=self.analysis_days)
        for mac, device_type in devices:
            if self.stop_event.is_set() or self.plugin.stop_event.is_set():
                return
            self.plugin.update_device_status(mac, device_type)
        LOG.info('[SnoopR] analysis pass: %d devices in %.1fs', len(devices),
                 time.time() - started)


class MaintenanceThread(StoppableThread):
    """Pruning used to happen only in on_unload, and VACUUM could hang shutdown."""

    def __init__(self, plugin, interval=3600):
        super().__init__(plugin, interval, 'snoopr-maintenance')
        self.passes = 0

    def tick(self):
        self.passes += 1
        self.plugin.db.prune_old_data(self.plugin.prune_days, vacuum=(self.passes % 24 == 0))
        self.plugin.evict_stale_state()
        counts = self.plugin.db.get_network_counts(self.plugin.persistence_threshold)
        self.plugin.counts_cache = counts


class CountsThread(StoppableThread):
    """Keeps the e-ink UI off the SQLite connection."""

    def __init__(self, plugin, interval=10):
        super().__init__(plugin, interval, 'snoopr-counts')

    def tick(self):
        self.plugin.counts_cache = self.plugin.db.get_network_counts(
            self.plugin.persistence_threshold)


class BufferFlusher(StoppableThread):
    """One flusher instead of spawning a thread per flush (which could race)."""

    def __init__(self, plugin, interval=2.0):
        super().__init__(plugin, interval, 'snoopr-flusher')

    def tick(self):
        self.plugin.flush_detection_buffer()


# ---------------------------------------------------------------------
# Web interface
# ---------------------------------------------------------------------

HTML_PAGE = '''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>SnoopR - Surveillance Detection</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script src="https://unpkg.com/leaflet.heat@0.2.0/dist/leaflet-heat.js"></script>
<style>
:root { color-scheme: light dark; }
body { font-family: system-ui, -apple-system, "Segoe UI", Arial, sans-serif; margin: 0;
       padding: 16px; background: #fafafa; color: #1a1a1a; }
body.dark { background: #121212; color: #e0e0e0; }
h1 { font-size: 1.4rem; margin: 0 0 12px; }
.bar { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; margin-bottom: 12px; }
.btn { padding: 7px 13px; cursor: pointer; background: #2f7d4f; color: #fff; border: none;
       border-radius: 4px; font-size: 0.85rem; }
.btn.active { background: #1b4d30; outline: 2px solid #9fd6b5; }
.btn.ghost { background: #555; }
input[type=text] { padding: 7px; border-radius: 4px; border: 1px solid #bbb; min-width: 220px; }
body.dark input[type=text] { background: #1e1e1e; color: #eee; border-color: #444; }
table { width: 100%; border-collapse: collapse; font-size: 0.85rem; }
th, td { padding: 7px 9px; text-align: left; border-bottom: 1px solid #ddd;
         white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 220px; }
body.dark th, body.dark td { border-color: #333; }
th { background: #ececec; cursor: pointer; position: sticky; top: 0; }
body.dark th { background: #262626; }
tbody tr { cursor: pointer; }
tr.low td { background: #eaf7ea; } tr.med td { background: #fffbe0; }
tr.high td { background: #fde8e8; }
body.dark tr.low td { background: #16301b; } body.dark tr.med td { background: #33300f; }
body.dark tr.high td { background: #3d1a1a; }
.tag { display: inline-block; padding: 1px 6px; border-radius: 10px; font-size: 0.72rem;
       background: #666; color: #fff; margin-right: 4px; }
.tag.warn { background: #b3261e; } .tag.rnd { background: #6750a4; }
#map { height: 62vh; min-height: 380px; margin-top: 14px; border-radius: 6px; }
#alert-box { position: fixed; top: 12px; left: 12px; background: rgba(179,38,30,.95);
             color: #fff; padding: 10px 14px; border-radius: 6px; display: none; z-index: 2000;
             max-width: 60vw; box-shadow: 0 2px 10px rgba(0,0,0,.4); }
#fixed { position: fixed; top: 12px; right: 12px; z-index: 1500; display: flex; gap: 6px; }
.meta { font-size: 0.8rem; opacity: .75; margin: 6px 0; }
.pop b { display: inline-block; min-width: 74px; }
.wrap { overflow-x: auto; max-height: 46vh; overflow-y: auto; }
</style>
</head>
<body>
<div id="alert-box" role="alert"></div>
<div id="fixed">
  <button class="btn ghost" id="toggle-dark">Dark</button>
  <button class="btn ghost" id="toggle-heat">Heatmap</button>
</div>
<h1>SnoopR &mdash; Surveillance Detection</h1>
<div class="bar">
  <input type="text" id="search" placeholder="Search MAC, name, vendor, anomaly...">
  <button class="btn" data-filter="all">All</button>
  <button class="btn" data-filter="snoopers">Snoopers</button>
  <button class="btn" data-filter="high_persistence">High persistence</button>
  <button class="btn" data-filter="anomalies">Anomalies</button>
  <button class="btn" data-filter="wifi">Wi-Fi</button>
  <button class="btn" data-filter="clients">Clients</button>
  <button class="btn" data-filter="bluetooth">Bluetooth</button>
  <button class="btn" data-filter="aircraft">Aircraft</button>
  <button class="btn" data-filter="randomized">Randomised</button>
  <button class="btn ghost" id="export-kml">Export KML</button>
</div>
<div class="meta" id="counts">Loading&hellip;</div>
<div class="wrap">
<table id="tbl">
<thead><tr>
  <th data-sort="device_type">Type</th>
  <th data-sort="mac">MAC / ICAO</th>
  <th data-sort="name">Name / Callsign</th>
  <th data-sort="">Vendor / Aircraft</th>
  <th data-sort="persistence">Persist.</th>
  <th data-sort="">Win</th>
  <th data-sort="">Clust.</th>
  <th data-sort="">Sess.</th>
  <th data-sort="rssi">Best RSSI</th>
  <th data-sort="is_snooper">Snooper</th>
  <th data-sort="velocity">Velocity (mph)</th>
  <th data-sort="">Anomalies</th>
  <th data-sort="last_seen">Last seen</th>
</tr></thead>
<tbody id="tbody"></tbody>
</table>
</div>
<div class="bar" id="pager"></div>
<div id="map"></div>
<script>
(function () {
  "use strict";
  var base = window.location.pathname.replace(/\\/?$/, "/");
  var state = { filter: "all", sort: "persistence", search: "", page: 0, size: 100 };
  var map = L.map("map").setView(INITIAL_CENTER, 13);
  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 19,
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
  }).addTo(map);
  var layer = L.layerGroup().addTo(map);
  var fenceLayer = L.layerGroup().addTo(map);
  var heat = null, heatOn = false;

  function el(tag, text, cls) {
    var node = document.createElement(tag);
    if (text !== undefined && text !== null) { node.textContent = String(text); }
    if (cls) { node.className = cls; }
    return node;
  }

  /* Popups are assembled with textContent, never innerHTML -- see note in WebHandler. */
  function popupFor(net) {
    var box = el("div", null, "pop");
    var rows = [
      ["MAC", net.mac], ["Name", net.name], ["Vendor", net.vendor],
      ["Class", net.classification], ["Persistence", net.persistence_score],
      ["Clusters", net.cluster_count], ["Best RSSI", net.best_rssi],
      ["Velocity", net.max_velocity_mph === null ? "n/a" : net.max_velocity_mph + " mph"],
      ["Snooper", net.is_snooper ? "YES - " + net.snooper_reason : "no"],
      ["Anomalies", net.anomalies], ["Position", net.triangulated ? "triangulated" : "last fix"],
      ["Last seen", net.last_seen]
    ];
    if (net.registration) { rows.push(["Reg", net.registration]); }
    if (net.aircraft_type) { rows.push(["Type", net.aircraft_type]); }
    if (net.owner) { rows.push(["Owner", net.owner]); }
    rows.forEach(function (row) {
      if (row[1] === null || row[1] === undefined || row[1] === "") { return; }
      var line = el("div");
      line.appendChild(el("b", row[0] + ":"));
      line.appendChild(document.createTextNode(" " + row[1]));
      box.appendChild(line);
    });
    return box;
  }

  function colourFor(net) {
    if (net.device_type === "aircraft") {
      return (net.anomalies && net.anomalies !== "None") ? "#7b2ff7" : "#0a84ff";
    }
    if (net.is_snooper) { return "#c62828"; }
    if (net.persistence_score > 0.7) { return "#e65100"; }
    if (net.persistence_score > 0.4) { return "#f9a825"; }
    return "#2e7d32";
  }

  function render(data) {
    var tbody = document.getElementById("tbody");
    tbody.textContent = "";
    layer.clearLayers();
    var heatPoints = [];

    data.networks.forEach(function (net) {
      var tr = el("tr");
      tr.className = net.persistence_score > 0.7 ? "high"
                   : (net.persistence_score > 0.4 ? "med" : "low");
      var vendor = net.device_type === "aircraft"
        ? [net.registration, net.aircraft_type, net.owner].filter(Boolean).join(" / ") || "Unknown"
        : net.vendor;
      [net.device_type, net.mac, net.name, vendor, net.persistence_score, net.windows_hit,
       net.cluster_count, net.sessions_count,
       net.best_rssi === null ? "-" : net.best_rssi,
       net.is_snooper ? "Yes" : "No",
       net.max_velocity_mph === null ? "-" : net.max_velocity_mph,
       net.anomalies, net.last_seen].forEach(function (value, idx) {
        var td = el("td", value);
        if (idx === 1 && net.is_randomized) { td.appendChild(el("span", "rnd", "tag rnd")); }
        if (idx === 9 && net.is_snooper) { td.title = net.snooper_reason; }
        tr.appendChild(td);
      });
      if (net.latitude !== null && net.longitude !== null) {
        tr.addEventListener("click", function () { map.setView([net.latitude, net.longitude], 17); });
      }
      tbody.appendChild(tr);

      if (net.latitude === null || net.longitude === null) { return; }
      var colour = colourFor(net);
      L.circleMarker([net.latitude, net.longitude], {
        color: colour, radius: 5 + net.persistence_score * 7, weight: 2, fillOpacity: 0.55
      }).bindPopup(popupFor(net)).addTo(layer);
      if (net.path && net.path.length > 1) {
        L.polyline(net.path.map(function (p) { return [p.latitude, p.longitude]; }),
                   { color: colour, weight: 2 + net.persistence_score * 3, opacity: 0.75 })
          .addTo(layer);
      }
      heatPoints.push([net.latitude, net.longitude,
                       net.persistence_score * (net.sessions_count || 1) + 1]);
    });

    if (heat) { map.removeLayer(heat); }
    heat = L.heatLayer(heatPoints, { radius: 25, blur: 15 });
    if (heatOn) { map.addLayer(heat); }

    fenceLayer.clearLayers();
    (data.geofences || []).forEach(function (fence) {
      var shape = fence.type === "circle"
        ? L.circle([fence.lat, fence.lon], { radius: fence.radius, color: "#1565c0", fillOpacity: 0.08 })
        : L.polygon(fence.points, { color: "#1565c0", fillOpacity: 0.08 });
      shape.bindPopup(el("div", fence.name)).addTo(fenceLayer);
    });

    var pager = document.getElementById("pager");
    pager.textContent = "";
    var pages = Math.max(1, Math.ceil(data.total / state.size));
    var info = el("span", "Page " + (state.page + 1) + " of " + pages +
                          " (" + data.total + " devices)", "meta");
    var prev = el("button", "Prev", "btn ghost");
    var next = el("button", "Next", "btn ghost");
    prev.disabled = state.page === 0;
    next.disabled = state.page + 1 >= pages;
    prev.addEventListener("click", function () { state.page -= 1; load(); });
    next.addEventListener("click", function () { state.page += 1; load(); });
    pager.appendChild(prev); pager.appendChild(next); pager.appendChild(info);
  }

  function load() {
    var url = base + "data.json?filter_by=" + encodeURIComponent(state.filter) +
      "&sort_by=" + encodeURIComponent(state.sort) +
      "&search=" + encodeURIComponent(state.search) +
      "&limit=" + state.size + "&offset=" + (state.page * state.size);
    fetch(url, { headers: { "Accept": "application/json" } })
      .then(function (r) { return r.json(); })
      .then(function (data) { render(data); paintCounts(data.counts); })
      .catch(function (err) { console.error("SnoopR load failed", err); });
  }

  document.querySelectorAll("[data-filter]").forEach(function (button) {
    button.addEventListener("click", function () {
      document.querySelectorAll("[data-filter]").forEach(function (b) {
        b.classList.remove("active");
      });
      button.classList.add("active");
      state.filter = button.getAttribute("data-filter");
      state.page = 0;
      load();
    });
  });
  document.querySelectorAll("th[data-sort]").forEach(function (th) {
    var key = th.getAttribute("data-sort");
    if (!key) { return; }
    th.addEventListener("click", function () { state.sort = key; state.page = 0; load(); });
  });
  var timer = null;
  document.getElementById("search").addEventListener("input", function (evt) {
    clearTimeout(timer);
    var value = evt.target.value;
    timer = setTimeout(function () { state.search = value; state.page = 0; load(); }, 300);
  });
  document.getElementById("toggle-dark").addEventListener("click", function () {
    document.body.classList.toggle("dark");
  });
  document.getElementById("toggle-heat").addEventListener("click", function () {
    heatOn = !heatOn;
    if (heat) { heatOn ? map.addLayer(heat) : map.removeLayer(heat); }
  });
  document.getElementById("export-kml").addEventListener("click", function () {
    window.location.href = base + "export.kml?filter_by=" + encodeURIComponent(state.filter);
  });

  function showAlert(message) {
    var box = document.getElementById("alert-box");
    box.textContent = message;
    box.style.display = "block";
    clearTimeout(box._t);
    box._t = setTimeout(function () { box.style.display = "none"; }, 8000);
  }

  function paintCounts(c) {
    if (!c) { return; }
    document.getElementById("counts").textContent =
      "Wi-Fi " + c.wifi + " | BT " + c.bluetooth + " | Aircraft " + c.aircraft +
      " | Snoopers " + c.snoopers + " | High persistence " + c.high_persistence +
      " | Anomalous aircraft " + c.anomalous_aircraft;
  }

  var pollMs = 60000, timerHandle = null;
  function schedule() {
    if (timerHandle) { clearInterval(timerHandle); }
    timerHandle = setInterval(load, pollMs);
  }

  /* SSE is optional: the pwnagotchi web server is a single shared Flask instance, so
     the dashboard must stay usable when live updates are off or the stream drops. */
  if (SSE_ENABLED) {
    var events = new EventSource(base + "events");
    var failures = 0;
    events.addEventListener("counts", function (evt) {
      failures = 0;
      paintCounts(JSON.parse(evt.data));
    });
    events.addEventListener("alert", function (evt) {
      var alert = JSON.parse(evt.data);
      showAlert("[" + alert.kind + "] " + alert.message);
    });
    events.onerror = function () {
      failures += 1;
      if (failures >= 3) {
        events.close();
        pollMs = 20000;
        schedule();
        console.warn("SnoopR: live stream unavailable, falling back to polling");
      }
    };
  } else {
    pollMs = 20000;
  }

  load();
  schedule();
}());
</script>
</body>
</html>
'''


class WebHandler:
    """Serves the dashboard shell, a paginated JSON endpoint, KML export and one SSE
    stream. Device data is never interpolated into HTML: the client builds every cell and
    popup with textContent, because a hostile SSID used to execute in the operator's
    browser via the old bindPopup template literals."""

    SSE_PATHS = ('events', 'stream', 'alerts')

    def __init__(self, plugin):
        self.plugin = plugin
        self.ip_requests = {}
        self._rate_lock = Lock()
        self.alerts = deque(maxlen=200)
        self.alert_seq = 0
        self._alert_lock = Lock()
        self._streams = 0
        self._stream_lock = Lock()

    # -- alerts --------------------------------------------------------
    def add_alert(self, kind, message, extra=None):
        with self._alert_lock:
            self.alert_seq += 1
            self.alerts.append({'id': self.alert_seq, 'kind': kind, 'message': message,
                                'time': fmt_ts(), 'extra': extra or {}})
            return self.alert_seq

    def _alerts_since(self, last_id):
        with self._alert_lock:
            return [a for a in self.alerts if a['id'] > last_id]

    # -- rate limiting -------------------------------------------------
    def _rate_limited(self, ip):
        now = time.time()
        with self._rate_lock:
            if len(self.ip_requests) > 512:
                for key in [k for k, v in self.ip_requests.items() if not v or now - v[-1] > 300]:
                    self.ip_requests.pop(key, None)
            hits = [t for t in self.ip_requests.get(ip, []) if now - t < 60]
            hits.append(now)
            self.ip_requests[ip] = hits
            return len(hits) > self.plugin.rate_limit_per_minute

    # -- routing -------------------------------------------------------
    def handle(self, path, request):
        route = (path or '').strip('/').lower()
        if route in ('index', 'index.html'):
            route = ''
        ip = request.remote_addr or 'unknown'

        if route in self.SSE_PATHS:
            if not self.plugin.sse_enabled:
                return 'Live updates are disabled (sse_enabled = false)', 404
            return self._stream(route)
        if self._rate_limited(ip):
            abort(429)
        if route == 'data.json':
            return self._data(request)
        if route in ('export.kml', 'kml'):
            return self._export_kml(request)
        if route == '':
            if request.args.get('export') == 'kml':
                return self._export_kml(request)
            page = (HTML_PAGE
                    .replace('INITIAL_CENTER', json.dumps(self.plugin.map_center()))
                    .replace('SSE_ENABLED', 'true' if self.plugin.sse_enabled else 'false'))
            return render_template_string(page)
        return 'Not Found', 404

    def _data(self, request):
        args = request.args
        try:
            limit = max(1, min(500, int(args.get('limit', 100))))
            offset = max(0, int(args.get('offset', 0)))
        except ValueError:
            limit, offset = 100, 0
        filter_by = args.get('filter_by', 'all')
        sort_by = args.get('sort_by', 'persistence')
        search = (args.get('search') or '').strip()[:64] or None
        networks = self.plugin.db.get_all_networks(
            sort_by=sort_by, filter_by=filter_by, include_paths=True,
            limit=limit, offset=offset,
            persistence_threshold=self.plugin.persistence_threshold,
            path_limit=self.plugin.max_path_points, search=search)
        total = self.plugin.db.count_networks(filter_by, self.plugin.persistence_threshold)
        return jsonify({
            'networks': networks,
            'total': total,
            'geofences': [g.to_json() for g in self.plugin.geofences],
            'counts': self.plugin.counts_cache,
            'center': self.plugin.map_center(),
        })

    def _export_kml(self, request):
        filter_by = request.args.get('filter_by', 'all')
        networks = self.plugin.db.get_all_networks(
            filter_by=filter_by, include_paths=True, limit=5000,
            persistence_threshold=self.plugin.persistence_threshold,
            path_limit=self.plugin.max_path_points)
        parts = ['<?xml version="1.0" encoding="UTF-8"?>',
                 '<kml xmlns="http://www.opengis.net/kml/2.2"><Document>',
                 '<name>SnoopR export</name>',
                 '<Style id="green"><IconStyle><color>ff00ff00</color></IconStyle></Style>',
                 '<Style id="yellow"><IconStyle><color>ff00ffff</color></IconStyle></Style>',
                 '<Style id="red"><IconStyle><color>ff0000ff</color></IconStyle></Style>',
                 '<Style id="purple"><IconStyle><color>fff72f7b</color></IconStyle></Style>',
                 '<Style id="path_high"><LineStyle><color>ff0000ff</color>'
                 '<width>4</width></LineStyle></Style>',
                 '<Style id="path_med"><LineStyle><color>ff00aaff</color>'
                 '<width>3</width></LineStyle></Style>']
        for fence in self.plugin.geofences:
            if fence.type == 'polygon':
                coords = ' '.join('%s,%s,0' % (p[1], p[0]) for p in fence.params)
                parts.append('<Placemark><name>%s</name><Polygon><outerBoundaryIs><LinearRing>'
                             '<coordinates>%s</coordinates></LinearRing></outerBoundaryIs>'
                             '</Polygon></Placemark>' % (xml_escape(fence.name), coords))
        for net in networks:
            if net['latitude'] is None or net['longitude'] is None:
                continue
            score = net['persistence_score']
            anomalous = net['anomalies'] not in ('', 'None')
            if net['device_type'] == 'aircraft':
                style = 'purple' if anomalous else 'green'
            else:
                style = 'red' if score > 0.7 else ('yellow' if score > 0.4 else 'green')
            # Escaped rather than wrapped in CDATA: an SSID containing ']]>' broke the file.
            desc = xml_escape(
                '%s (%s) | vendor: %s | type: %s | persistence: %.3f | windows: %s | '
                'clusters: %s | sessions: %s | snooper: %s%s | anomalies: %s' % (
                    net['name'], net['mac'], net['vendor'], net['device_type'], score,
                    net['windows_hit'], net['cluster_count'], net['sessions_count'],
                    'yes' if net['is_snooper'] else 'no',
                    (' (%s)' % net['snooper_reason']) if net['snooper_reason'] else '',
                    net['anomalies']))
            parts.append('<Placemark><name>%s</name><description>%s</description>'
                         '<styleUrl>#%s</styleUrl><Point><coordinates>%s,%s,0</coordinates>'
                         '</Point></Placemark>' % (xml_escape(net['mac']), desc, style,
                                                   net['longitude'], net['latitude']))
            path = net.get('path')
            if path and len(path) > 1 and (score > 0.4 or net['is_snooper']):
                coords = ' '.join('%s,%s,0' % (p['longitude'], p['latitude']) for p in path)
                parts.append('<Placemark><name>Trail %s</name><styleUrl>#%s</styleUrl>'
                             '<LineString><tessellate>1</tessellate><coordinates>%s'
                             '</coordinates></LineString></Placemark>' % (
                                 xml_escape(net['mac']),
                                 'path_high' if score > 0.7 else 'path_med', coords))
        parts.append('</Document></kml>')
        return Response('\n'.join(parts),
                        mimetype='application/vnd.google-earth.kml+xml',
                        headers={'Content-Disposition': 'attachment; filename=snoopr.kml'})

    def _stream(self, route):
        with self._stream_lock:
            if self._streams >= self.plugin.max_sse_clients:
                abort(503)
            self._streams += 1

        want_counts = route in ('events', 'stream')
        want_alerts = route in ('events', 'alerts')

        def generate():
            last_counts = None
            last_alert = self.alert_seq if route == 'alerts' else 0
            last_beat = 0.0
            try:
                while not self.plugin.stop_event.is_set():
                    if want_counts:
                        counts = self.plugin.counts_cache
                        if counts != last_counts:
                            yield 'event: counts\ndata: %s\n\n' % json.dumps(counts)
                            last_counts = dict(counts)
                    if want_alerts:
                        for alert in self._alerts_since(last_alert):
                            last_alert = alert['id']
                            yield 'event: alert\ndata: %s\n\n' % json.dumps(alert)
                    if time.time() - last_beat > 20:
                        last_beat = time.time()
                        yield ': keepalive\n\n'
                    time.sleep(1.0)
            finally:
                with self._stream_lock:
                    self._streams -= 1

        return Response(stream_with_context(generate()), mimetype='text/event-stream',
                        headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no',
                                 'Connection': 'keep-alive'})


# ---------------------------------------------------------------------
# Main plugin
# ---------------------------------------------------------------------

class SnoopR(plugins.Plugin):
    __author__ = 'AlienMajik'
    __version__ = '7.0.1'
    __license__ = 'GPL3'
    __description__ = ('SnoopR: Wi-Fi/BLE/ADS-B surveillance detection with geofencing, '
                       'aircraft anomaly detection, trilateration, mesh sharing and a '
                       'live web UI.')

    ALERT_KEYWORDS = {
        'squawk': ('squawk',),
        'geofence': ('geofence',),
        'circling': ('circling',),
        'rapid': ('rapid descent', 'rapid climb'),
        'speed': ('excessive speed', 'low speed'),
        'low_altitude': ('low altitude',),
        'turn': ('sharp turn',),
        'snooper': ('snooper',),
    }

    def __init__(self):
        self.options = {}
        self.ready = False
        self.db = None
        self.session_id = None
        self.mesh = None
        self.mesh_receiver = None
        self.web_handler = None
        self.opensky = None
        self.local_aircraft_db = None
        self.stop_event = threading.Event()
        self.loop = None
        self.threads = []
        self.bleak_task = None
        self._ble_adapter_mode = None

        self.last_gps = {'latitude': '-', 'longitude': '-', 'altitude': '-'}
        self.last_gps_at = 0.0
        self.oui_db = {24: {}, 28: {}, 36: {}}
        self.bluetooth_company_db = {}
        self.kalman_filters = LRUDict(maxsize=8192)
        self.aircraft_tracks = LRUDict(maxsize=2048)
        self.wigle_cache = LRUDict(maxsize=512)
        self.counts_cache = {'wifi': 0, 'bluetooth': 0, 'aircraft': 0, 'snoopers': 0,
                             'high_persistence': 0, 'anomalous_aircraft': 0}

        self.detection_buffer = []
        self.buffer_lock = threading.Lock()
        self.buffer_max_size = 200
        self.geofences = []
        self.whitelist_ssids = set()
        self.whitelist_macs = set()

    # -----------------------------------------------------------------
    # Configuration
    # -----------------------------------------------------------------
    def _opt(self, key, default=None, legacy=None):
        if key in self.options:
            return self.options[key]
        if legacy and legacy in self.options:
            return self.options[legacy]
        return default

    def _load_config(self):
        try:
            config = pwnagotchi.config.get('main', {}).get('plugins', {}).get('snoopr', {}) or {}
        except Exception:  # noqa: BLE001 - config may not be ready in odd images
            config = {}
        self.options.update(config)

        base_dir = self._opt('base_dir', '/root/snoopr')
        base_dir = self._ensure_writable_dir(base_dir, '/home/pi/snoopr')
        self.base_dir = base_dir
        self.db_path = os.path.join(base_dir, 'snoopr.db')

        self.oui_db_path = self._opt('oui_db_path', '/usr/share/wireshark/manuf')
        if not os.path.exists(self.oui_db_path):
            for candidate in ('/usr/share/wireshark/manuf', '/usr/share/ieee-data/oui.txt',
                              os.path.join(base_dir, 'manuf')):
                if os.path.exists(candidate):
                    self.oui_db_path = candidate
                    break
        self.bt_company_db_path = self._opt(
            'bt_company_db_path', os.path.join(base_dir, 'company_identifiers.json'))
        self.aircraft_file = self._resolve_aircraft_file(self._opt('aircraft_file'))
        self.aircraft_db_csv = self._opt('aircraft_db_csv', '')

        self.scan_interval = float(self._opt('scan_interval', 10))
        self.scan_duration = float(self._opt('scan_duration', 5))
        self.bluetooth_enabled = bool(self._opt('bluetooth_enabled', True))
        self.bluetooth_device = self._opt('bluetooth_device', 'hci0')
        self.log_without_gps = bool(self._opt('log_without_gps', False))
        self.gps_max_age = float(self._opt('gps_max_age', 60))
        self.prune_days = int(self._opt('prune_days', 30))
        self.prune_interval_hours = float(self._opt('prune_interval_hours', 6))

        self.mesh_enabled = bool(self._opt('mesh_enabled', False))
        self.mesh_host = self._opt('mesh_host', '0.0.0.0')
        self.mesh_port = int(self._opt('mesh_port', 8888))
        self.mesh_peers = list(self._opt('mesh_peers', []) or [])
        self.mesh_key = self._opt('mesh_key', '') or ''
        self.mesh_allow_plaintext = bool(self._opt('mesh_allow_plaintext', False))
        if self.mesh_enabled and self.mesh_key:
            LOG.warning('[SnoopR] mesh_key is stored in plaintext in config.toml; '
                        'restrict permissions (chmod 600).')

        self.wigle_enabled = bool(self._opt('wigle_enabled', False))
        self.wigle_api_name = self._opt('wigle_api_name', '')
        self.wigle_api_token = self._opt('wigle_api_token', '')
        if self.wigle_enabled and (self.wigle_api_name or self.wigle_api_token):
            LOG.warning('[SnoopR] WiGLE credentials are stored in plaintext in config.toml; '
                        'restrict permissions (chmod 600).')

        self.whitelist_ssids = {str(s).casefold() for s in self._opt('whitelist_ssids', [])}
        self.whitelist_macs = {norm_mac(m) for m in self._opt('whitelist_macs', []) if m}

        self.persistence_threshold = float(self._opt('persistence_threshold', 0.85))
        self.triangulation_min_points = int(self._opt('triangulation_min_points', 8))
        self.movement_threshold = float(self._opt('movement_threshold', 0.8))  # miles
        self.time_threshold_minutes = float(self._opt('time_threshold_minutes', 20))
        self.min_rssi_for_movement = int(self._opt('min_rssi_for_movement', -70))
        self.max_plausible_velocity_mph = float(self._opt('max_plausible_velocity_mph', 200))
        self.flag_randomized_snoopers = bool(self._opt('flag_randomized_snoopers', False))
        # A stationary unit cannot separate "a tail" from "the neighbours", so movement
        # corroboration is required by default. Set false for fixed counter-surveillance
        # installs, where persistence alone becomes the trigger (6.x behaviour).
        self.require_movement_for_snooper = bool(
            self._opt('require_movement_for_snooper', True))
        self.analysis_days = int(self._opt('analysis_days', 7))
        self.analysis_row_limit = int(self._opt('analysis_row_limit', 4000))
        self.update_interval = float(self._opt('update_interval', 300))
        self.persistence_window_minutes = float(self._opt('persistence_window_minutes', 5))
        self.persistence_windows = int(self._opt('persistence_windows', 4))

        # mse_threshold used to be compared against a degrees/metres mixture; the new
        # figure is a real mean-square error in m^2 (2500 == 50 m RMS).
        mse = self._opt('mse_threshold_m2')
        if mse is None:
            legacy = float(self._opt('mse_threshold', 0) or 0)
            mse = legacy if legacy >= 500 else 2500.0
            if 0 < legacy < 500:
                LOG.warning('[SnoopR] legacy mse_threshold=%s ignored; using %s m^2. '
                            'Set mse_threshold_m2 to override.', legacy, mse)
        self.mse_threshold_m2 = float(mse)

        self.tx_power = {'wifi': float(self._opt('tx_power_wifi', -20)),
                         'bluetooth': float(self._opt('tx_power_bt', -20))}
        self.path_loss_n = {'wifi': float(self._opt('path_loss_n_wifi', 2.7)),
                            'bluetooth': float(self._opt('path_loss_n_bt', 2.7))}

        # Aircraft thresholds. The old name said "high" but the test is for LOW altitude.
        self.aircraft_low_altitude_threshold = float(self._opt(
            'aircraft_low_altitude_threshold', 3000, legacy='aircraft_high_altitude_threshold'))
        self.aircraft_circling_radius = float(self._opt('aircraft_circling_radius', 1500))
        self.aircraft_circling_time = float(self._opt('aircraft_circling_time', 120))
        self.aircraft_rapid_descent_threshold = float(
            self._opt('aircraft_rapid_descent_threshold', 3000))
        self.aircraft_rapid_climb_threshold = float(
            self._opt('aircraft_rapid_climb_threshold', 3000))
        self.aircraft_max_speed_knots = float(self._opt('aircraft_max_speed_knots', 600))
        self.aircraft_min_speed_knots = float(self._opt('aircraft_min_speed_knots', 50))
        self.aircraft_enable_squawk_alerts = bool(
            self._opt('aircraft_enable_squawk_alerts', True))
        self.aircraft_move_threshold = float(self._opt('aircraft_move_threshold', 300))
        self.aircraft_interval = float(self._opt('aircraft_interval', 15))

        self.opensky_client_id = self._opt('opensky_client_id', '')
        self.opensky_client_secret = self._opt('opensky_client_secret', '')
        if not self.opensky_client_id and self._opt('opensky_username'):
            LOG.warning('[SnoopR] opensky_username/password are no longer accepted by '
                        'OpenSky (basic auth retired 2026-03-18). Create an API client and '
                        'set opensky_client_id / opensky_client_secret.')

        self.alert_on = set(self._opt('alert_on', ['squawk', 'geofence', 'circling',
                                                   'rapid', 'snooper']))
        self.rate_limit_per_minute = int(self._opt('rate_limit_per_minute', 120))
        # Pwnagotchi's Flask server is a single dev-server instance shared by the whole
        # web UI. Long-lived SSE connections are cheap but not free; keep the cap low and
        # allow disabling them entirely (the dashboard falls back to polling).
        self.sse_enabled = bool(self._opt('sse_enabled', True))
        self.max_sse_clients = int(self._opt('max_sse_clients', 2))
        self.max_path_points = int(self._opt('max_path_points', 300))

        self.ui_enabled = bool(self._opt('ui_enabled', True))
        self.ui_x = int(self._opt('ui_x', 0))
        self.ui_y = int(self._opt('ui_y', 90))
        self.ui_line_height = int(self._opt('ui_line_height', 10))
        self.ui_elements = list(self._opt('ui_elements',
                                          ['wifi', 'bt', 'aircraft', 'snoopers', 'persistence']))

        self.geofences = []
        for entry in self._opt('geofences', []) or []:
            try:
                self.geofences.append(Geofence.from_config(entry))
            except (KeyError, ValueError, TypeError) as exc:
                LOG.error('[SnoopR] invalid geofence %r: %s', entry, exc)
        if self.geofences:
            LOG.info('[SnoopR] loaded %d geofence(s)', len(self.geofences))

    @staticmethod
    def _ensure_writable_dir(preferred, fallback):
        """Newer jayofelony images run through a venv and have moved user data out of
        /root; fall back rather than dying at load time."""
        for candidate in (preferred, fallback):
            if not candidate:
                continue
            try:
                os.makedirs(candidate, exist_ok=True)
                probe = os.path.join(candidate, '.snoopr-write-test')
                with open(probe, 'w', encoding='utf-8') as handle:
                    handle.write('ok')
                os.remove(probe)
                if candidate != preferred:
                    LOG.warning('[SnoopR] base_dir %s is not writable; using %s',
                                preferred, candidate)
                return candidate
            except OSError as exc:
                LOG.warning('[SnoopR] cannot use base_dir %s: %s', candidate, exc)
        raise RuntimeError('no writable base_dir (tried %s, %s)' % (preferred, fallback))

    AIRCRAFT_FILE_CANDIDATES = (
        '/home/pi/handshakes/skyhigh_aircraft.json',
        '/root/handshakes/skyhigh_aircraft.json',
        '/home/pi/aircraft.json',
        '/root/aircraft.json',
    )

    def _resolve_aircraft_file(self, configured):
        """2.9.3+ moved handshakes to /home/pi/handshakes, so the old /root defaults
        silently produce an idle aircraft thread. Probe the known locations."""
        if configured:
            if os.path.exists(configured):
                return configured
            for candidate in self.AIRCRAFT_FILE_CANDIDATES:
                if os.path.exists(candidate):
                    LOG.warning('[SnoopR] aircraft_file %s not found; using %s instead',
                                configured, candidate)
                    return candidate
            LOG.warning('[SnoopR] aircraft_file %s not found and no feed at any known '
                        'location; aircraft tracking will idle until it appears',
                        configured)
            return configured
        for candidate in self.AIRCRAFT_FILE_CANDIDATES:
            if os.path.exists(candidate):
                LOG.info('[SnoopR] using aircraft feed %s', candidate)
                return candidate
        return self.AIRCRAFT_FILE_CANDIDATES[0]

    def _check_dependencies(self):
        missing = []
        if self.bluetooth_enabled and not HAS_BLEAK:
            missing.append('bleak (BLE scanning disabled)')
        if self.mesh_enabled and not HAS_CRYPTO:
            missing.append('cryptography (mesh encryption)')
        if not HAS_SCIPY:
            LOG.info('[SnoopR] scipy not present; using the pure-Python solver')
        if missing:
            import sys
            LOG.warning('[SnoopR] missing optional packages: %s', ', '.join(missing))
            LOG.warning('[SnoopR] install them into the interpreter pwnagotchi actually '
                        'uses: %s -m pip install <pkg>  (recent images run from a venv, so '
                        'a plain "sudo pip3 install" lands somewhere else)', sys.executable)

    # -----------------------------------------------------------------
    # Vendor databases
    # -----------------------------------------------------------------
    def _load_oui_db(self):
        """Understands both the Wireshark `manuf` format and IEEE `oui.txt`.
        The 6.x parser only handled `oui.txt`, so against the documented
        wireshark-common path it loaded zero entries."""
        path = self.oui_db_path
        if not path or not os.path.exists(path):
            LOG.warning('[SnoopR] OUI database not found (%s); vendor lookup limited', path)
            return
        loaded = 0
        try:
            with open(path, 'r', encoding='utf-8', errors='ignore') as handle:
                for line in handle:
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue
                    if '(hex)' in line:  # IEEE oui.txt
                        head, _, tail = line.partition('(hex)')
                        prefix = head.strip().replace('-', '').replace(':', '').upper()
                        vendor = tail.strip()
                        if len(prefix) >= 6 and vendor:
                            self.oui_db[24][prefix[:6]] = vendor
                            loaded += 1
                        continue
                    parts = line.split('\t')
                    if len(parts) < 2:
                        parts = line.split(None, 2)
                    if len(parts) < 2:
                        continue
                    prefix, _, mask = parts[0].partition('/')
                    prefix = prefix.replace(':', '').replace('-', '').replace('.', '').upper()
                    vendor = (parts[2].strip() if len(parts) > 2 and parts[2].strip()
                              else parts[1].strip())
                    if not prefix or not vendor:
                        continue
                    bits = int(mask) if mask.isdigit() else 24
                    bucket = 36 if bits >= 36 else (28 if bits >= 28 else 24)
                    nibbles = bucket // 4
                    if len(prefix) >= nibbles:
                        self.oui_db[bucket][prefix[:nibbles]] = vendor
                        loaded += 1
            LOG.info('[SnoopR] loaded %d OUI entries from %s', loaded, path)
        except OSError as exc:
            LOG.error('[SnoopR] OUI load error: %s', exc)

    def _lookup_oui_vendor(self, mac):
        if not mac:
            return 'Unknown'
        if is_randomized_mac(mac):
            return 'Randomised (private address)'
        digits = mac_hex(mac)
        for bits, nibbles in ((36, 9), (28, 7), (24, 6)):
            if len(digits) >= nibbles:
                vendor = self.oui_db[bits].get(digits[:nibbles])
                if vendor:
                    return vendor
        return 'Unknown'

    def _load_bluetooth_company_db(self):
        if not os.path.exists(self.bt_company_db_path):
            return False
        try:
            with open(self.bt_company_db_path, 'r', encoding='utf-8') as handle:
                data = json.load(handle)
            entries = data.get('company_identifiers', []) if isinstance(data, dict) else data
            for entry in entries or []:
                if isinstance(entry, dict) and 'code' in entry and 'name' in entry:
                    try:
                        self.bluetooth_company_db[int(entry['code'])] = entry['name']
                    except (TypeError, ValueError):
                        continue
            LOG.info('[SnoopR] loaded %d Bluetooth company IDs', len(self.bluetooth_company_db))
            return bool(self.bluetooth_company_db)
        except (OSError, json.JSONDecodeError) as exc:
            LOG.error('[SnoopR] Bluetooth company DB load error: %s', exc)
            return False

    def _download_bt_company_db(self):
        """Runs off the boot path: 6.x blocked on_loaded for up to 30 s."""
        url = ('https://raw.githubusercontent.com/NordicSemiconductor/'
               'bluetooth-numbers-database/master/v1/company_ids.json')
        try:
            resp = requests.get(url, timeout=30)
            resp.raise_for_status()
            tmp = self.bt_company_db_path + '.tmp'
            with open(tmp, 'w', encoding='utf-8') as handle:
                handle.write(resp.text)
            os.replace(tmp, self.bt_company_db_path)
            LOG.info('[SnoopR] downloaded Bluetooth company database')
            self._load_bluetooth_company_db()
        except (requests.RequestException, OSError) as exc:
            LOG.error('[SnoopR] Bluetooth company DB download failed: %s', exc)

    def _lookup_bt_company(self, company_id):
        """bleak already parses manufacturer_data into {company_id: payload}; 6.x re-parsed
        the payload's first two bytes as the ID."""
        if company_id is None:
            return 'Unknown'
        return self.bluetooth_company_db.get(int(company_id),
                                             'Unknown (0x%04X)' % int(company_id))

    # -----------------------------------------------------------------
    # BLE classification
    # -----------------------------------------------------------------
    def _classify_device(self, name, manufacturer_data):
        for company_id in (manufacturer_data or {}):
            company = self._lookup_bt_company(company_id).lower()
            if 'apple' in company:
                return 'Apple Device'
            if 'google' in company:
                return 'Android/Google Device'
            if 'samsung' in company:
                return 'Samsung Device'
            if 'microsoft' in company:
                return 'Microsoft Device'
            if 'fitbit' in company or 'garmin' in company:
                return 'Fitness Tracker'
            if 'tile' in company or 'chipolo' in company:
                return 'Item Tracker'
        lowered = (name or '').lower()
        for needle, label in (('airtag', 'Item Tracker'), ('tile', 'Item Tracker'),
                              ('airpods', 'Apple Device'), ('apple', 'Apple Device'),
                              ('galaxy', 'Samsung Device'), ('samsung', 'Samsung Device'),
                              ('fitbit', 'Fitness Tracker'), ('watch', 'Wearable'),
                              ('band', 'Wearable'), ('speaker', 'Audio Device'),
                              ('headphone', 'Audio Device'), ('buds', 'Audio Device'),
                              ('cam', 'Camera'), ('gopro', 'Camera')):
            if needle in lowered:
                return label
        return 'Unknown Device'

    @staticmethod
    def _service_uuids(adv):
        return {str(u).lower() for u in (getattr(adv, 'service_uuids', None) or [])}

    def _detect_vulnerabilities(self, adv):
        vulns = []
        uuids = self._service_uuids(adv)
        if '00001800-0000-1000-8000-00805f9b34fb' in uuids:
            vulns.append('Exposed Generic Access')
        if '0000fd6f-0000-1000-8000-00805f9b34fb' in uuids:
            vulns.append('Exposure Notification beacon')
        return ', '.join(vulns) if vulns else 'None'

    def _detect_ble_anomalies(self, adv, mac):
        anomalies = []
        uuids = self._service_uuids(adv)
        if {'0000feaa-0000-1000-8000-00805f9b34fb',
                '0000180a-0000-1000-8000-00805f9b34fb'} <= uuids:
            anomalies.append('Multiple beacon types')
        if '0000fd5a-0000-1000-8000-00805f9b34fb' in uuids:
            anomalies.append('Find-My style tracker')
        if is_randomized_mac(mac) and (getattr(adv, 'manufacturer_data', None) or {}):
            pass  # normal for phones; not an anomaly on its own
        return ', '.join(anomalies) if anomalies else 'None'

    @staticmethod
    def _detect_rogue(vendor, name):
        """'Unknown' is deliberately NOT a signal any more: with the broken OUI parser it
        matched every device on the air."""
        keywords = ('espressif', 'tuya', 'shenzhen', 'alfa', 'raspberry', 'nordic semiconductor')
        name_keywords = ('test', 'demo', 'default', 'pineapple', 'wifi-pineapple', 'evil')
        score = 0
        if vendor and any(k in vendor.lower() for k in keywords):
            score += 1
        if name and any(k in name.lower() for k in name_keywords):
            score += 1
        return 1 if score >= 1 else 0

    def _detect_mesh(self, adv):
        mesh_uuids = {'00001827-0000-1000-8000-00805f9b34fb',
                      '00001828-0000-1000-8000-00805f9b34fb'}
        return 1 if self._service_uuids(adv) & mesh_uuids else 0

    def _get_kalman(self, mac, device_type):
        key = (mac, device_type)
        kf = self.kalman_filters.get(key)
        if kf is None:
            kf = KalmanFilter()
            self.kalman_filters[key] = kf
        return kf

    # -----------------------------------------------------------------
    # GPS + buffering
    # -----------------------------------------------------------------
    def _update_gps(self, agent):
        try:
            session = agent.session() or {}
            gps = session.get('gps') or {}
        except Exception:  # noqa: BLE001
            return False
        coords = valid_coords(gps.get('Latitude'), gps.get('Longitude'))
        if not coords:
            return False
        self.last_gps = {'latitude': str(coords[0]), 'longitude': str(coords[1]),
                         'altitude': str(gps.get('Altitude', '-'))}
        self.last_gps_at = time.time()
        return True

    def gps_fresh(self):
        return (self.last_gps['latitude'] != '-'
                and (time.time() - self.last_gps_at) <= self.gps_max_age)

    def current_coords(self):
        if self.gps_fresh():
            return self.last_gps['latitude'], self.last_gps['longitude']
        return '-', '-'

    def map_center(self):
        coords = valid_coords(self.last_gps['latitude'], self.last_gps['longitude'])
        return [coords[0], coords[1]] if coords else [37.7749, -122.4194]

    def add_to_buffer(self, detection):
        with self.buffer_lock:
            self.detection_buffer.append(detection)
            full = len(self.detection_buffer) >= self.buffer_max_size
        if full:
            self.flush_detection_buffer()

    def flush_detection_buffer(self):
        with self.buffer_lock:
            if not self.detection_buffer:
                return
            batch = self.detection_buffer
            self.detection_buffer = []
        self.db.add_detection_batch(batch)
        if self.mesh:
            self.mesh.broadcast_detections([
                {'mac': d[0], 'type': d[1], 'name': d[2], 'device_type': d[3], 'vendor': d[4],
                 'encryption': d[11], 'signal_strength': d[12], 'latitude': d[13],
                 'longitude': d[14], 'channel': d[15], 'auth_mode': d[16], 'altitude': d[17]}
                for d in batch[:100]])

    # -----------------------------------------------------------------
    # Alerts
    # -----------------------------------------------------------------
    def is_alertable(self, anomaly):
        lowered = str(anomaly).lower()
        for category, needles in self.ALERT_KEYWORDS.items():
            if category in self.alert_on and any(n in lowered for n in needles):
                return True
        return False

    def raise_alert(self, kind, message, extra=None):
        LOG.warning('[SnoopR] ALERT (%s): %s', kind, message)
        if self.web_handler:
            self.web_handler.add_alert(kind, message, extra)

    # -----------------------------------------------------------------
    # Aircraft behavioural analysis
    # -----------------------------------------------------------------
    def detect_aircraft_anomalies(self, plane, lat, lon, now):
        icao = plane['icao']
        track = self.aircraft_tracks.get(icao)
        if track is None:
            track = deque(maxlen=60)
            self.aircraft_tracks[icao] = track
        previous = track[-1] if track else None
        track.append({'lat': lat, 'lon': lon, 'alt': plane['alt'], 'ts': now,
                      'speed': plane['speed'], 'heading': plane['heading'],
                      'vert_rate': plane['vert_rate'], 'squawk': plane['squawk'],
                      'on_ground': plane['on_ground']})

        anomalies = []
        alt = plane['alt']
        airborne = not plane['on_ground'] and (alt is None or alt > 50)

        if airborne and alt is not None and alt < self.aircraft_low_altitude_threshold:
            anomalies.append('Low altitude')

        # Circling: convex-hull diameter over the recent window.
        window = [p for p in track
                  if (now - p['ts']).total_seconds() <= self.aircraft_circling_time * 3]
        if airborne and len(window) >= 5:
            span = (window[-1]['ts'] - window[0]['ts']).total_seconds()
            if span >= self.aircraft_circling_time:
                diameter = polygon_diameter([(p['lat'], p['lon']) for p in window])
                if diameter <= self.aircraft_circling_radius:
                    anomalies.append('Circling')

        vert = plane['vert_rate']
        if vert is not None and airborne:
            if vert < -self.aircraft_rapid_descent_threshold:
                anomalies.append('Rapid descent')
            elif vert > self.aircraft_rapid_climb_threshold:
                anomalies.append('Rapid climb')

        speed = plane['speed']
        if speed is not None and airborne:
            if speed > self.aircraft_max_speed_knots:
                anomalies.append('Excessive speed')
            elif speed < self.aircraft_min_speed_knots:
                anomalies.append('Low speed')

        squawk = plane['squawk']
        if self.aircraft_enable_squawk_alerts and squawk:
            emergency = {'7500': 'Hijack', '7600': 'Radio failure', '7700': 'Emergency'}
            if squawk in emergency:
                anomalies.append('Squawk %s (%s)' % (squawk, emergency[squawk]))

        heading = plane['heading']
        if (airborne and heading is not None and previous
                and previous.get('heading') is not None):
            gap = (now - previous['ts']).total_seconds()
            if 0 < gap <= 60:
                change = abs(heading - previous['heading']) % 360
                if change > 180:
                    change = 360 - change
                if change > 30:
                    anomalies.append('Sharp turn')

        return anomalies

    # -----------------------------------------------------------------
    # Device analysis
    # -----------------------------------------------------------------
    def update_device_status(self, mac, device_type):
        """No DB lock is held here: 6.x held db_lock across the whole analysis
        (including the optimiser), blocking every scan write and web request."""
        if device_type == 'aircraft':
            return
        try:
            rows = self.db.get_detections_for_network(
                mac, device_type, limit=self.analysis_row_limit,
                days=self.analysis_days, ascending=True)
            if len(rows) < 3:
                return
            meta = self.db.get_network_meta(mac, device_type) or {}

            fixes = []
            for row in rows:
                coords = valid_coords(row['lat'], row['lon'])
                ts = parse_ts(row['timestamp'])
                if coords and ts:
                    fixes.append({'lat': coords[0], 'lon': coords[1], 'ts': ts,
                                  'rssi': row['rssi'], 'id': row['id'],
                                  'session': row['session']})

            # --- movement / velocity (rows are chronological now) ---
            max_velocity = 0.0
            close_fixes = [f for f in fixes
                           if f['rssi'] is not None and f['rssi'] >= self.min_rssi_for_movement]
            previous = None
            for fix in fixes:
                if previous is not None:
                    seconds = (fix['ts'] - previous['ts']).total_seconds()
                    if 0 < seconds <= self.time_threshold_minutes * 60:
                        distance = haversine(previous['lat'], previous['lon'],
                                             fix['lat'], fix['lon'])
                        velocity = distance / seconds
                        if velocity * MPS_TO_MPH <= self.max_plausible_velocity_mph:
                            max_velocity = max(max_velocity, velocity)
                previous = fix

            # A device is "following" only if it was seen CLOSE (strong RSSI) at points
            # far apart in space and time. Driving past a stationary AP produces distance
            # but only at weak signal, which used to flag every AP as a snooper.
            separation_miles = 0.0
            followed = False
            if len(close_fixes) >= 2:
                separation = polygon_diameter([(f['lat'], f['lon']) for f in close_fixes])
                separation_miles = separation / METERS_PER_MILE
                span = (close_fixes[-1]['ts'] - close_fixes[0]['ts']).total_seconds()
                followed = (separation_miles >= self.movement_threshold and span >= 300)

            # --- persistence score ---
            now = utcnow()
            timestamps = [f['ts'] for f in fixes] or [parse_ts(r['timestamp']) for r in rows]
            timestamps = [t for t in timestamps if t]
            weights = ([0.4, 0.3, 0.2, 0.1] if self.persistence_windows == 4
                       else [1.0 / self.persistence_windows] * self.persistence_windows)
            score = 0.0
            windows_hit = 0
            for index in range(self.persistence_windows):
                start = now - timedelta(minutes=self.persistence_window_minutes * (index + 1))
                end = now - timedelta(minutes=self.persistence_window_minutes * index)
                if any(start <= ts < end for ts in timestamps):
                    score += weights[index]
                    windows_hit += 1
            cluster_count, _ = grid_cluster_count([(f['lat'], f['lon']) for f in fixes])
            # Only zones where the device was actually CLOSE count towards the score.
            # Counting every GPS cell inflated the score for any AP you drove slowly past.
            close_clusters, _ = grid_cluster_count([(f['lat'], f['lon']) for f in close_fixes])
            sessions = len({f['session'] for f in fixes if f['session'] is not None})
            score += 0.2 * max(0, windows_hit - 1)
            score += 0.1 * max(0, close_clusters - 1)
            score = min(1.0, score)

            # Being visible for a long time is not evidence of surveillance: a stationary
            # unit sees its own neighbourhood constantly. A tail is a device seen at close
            # range in more than one place, or in more than one session.
            reasons = []
            if followed:
                reasons.append('tracked across %.1f mi at >= %d dBm'
                               % (separation_miles, self.min_rssi_for_movement))
            if (score >= self.persistence_threshold and close_clusters >= 2 and sessions >= 2):
                reasons.append('persistence %.2f across %d close-range zones / %d sessions'
                               % (score, close_clusters, sessions))
            if not self.require_movement_for_snooper and score >= self.persistence_threshold:
                reasons.append('persistence %.2f' % score)
            if meta.get('is_randomized') and not self.flag_randomized_snoopers and not followed:
                # Randomised BLE addresses rotate every ~15 min, so persistence alone is
                # not evidence of anything.
                reasons = []
            is_snooper = bool(reasons)
            reason_text = '; '.join(reasons)

            self.db.update_persistence(mac, device_type, score, windows_hit, cluster_count)
            self.db.update_max_velocity(mac, device_type, max_velocity)
            if is_snooper != bool(meta.get('is_snooper')):
                self.db.update_snooper_status(mac, device_type, is_snooper, reason_text)
                if is_snooper and 'snooper' in self.alert_on:
                    label = meta.get('name') or mac
                    self.raise_alert('snooper', 'Possible tail: %s (%s) - %s'
                                     % (label, mac, reason_text),
                                     {'mac': mac, 'device_type': device_type})
            elif is_snooper:
                self.db.update_snooper_status(mac, device_type, True, reason_text)

            # --- trilateration + filtered RSSI backfill ---
            if device_type not in ('wifi', 'bluetooth'):
                return
            kf = KalmanFilter()
            samples = []
            filtered_updates = []
            tx = self.tx_power.get(device_type, -20.0)
            loss = self.path_loss_n.get(device_type, 2.7)
            for fix in fixes:
                rssi = fix['rssi']
                if rssi is None or not (-100 <= rssi <= -20):
                    continue
                filtered = kf.filter(rssi)
                filtered_updates.append((round(filtered, 2), fix['id']))
                distance = 10 ** ((tx - filtered) / (10.0 * loss))
                if not (0.1 <= distance <= 2000):
                    continue
                age_hours = max(0.0, (now - fix['ts']).total_seconds() / 3600.0)
                samples.append((fix['lat'], fix['lon'], distance,
                                exp(-age_hours / 24.0) / max(distance, 1.0)))
            if filtered_updates:
                self.db.update_filtered_rssi_batch(filtered_updates)
            if len(samples) < self.triangulation_min_points:
                return
            spread = polygon_diameter([(s[0], s[1]) for s in samples])
            if spread < 10.0:
                return  # all observations from one spot: no geometry to solve
            lat, lon, mse = trilaterate(samples, self.mse_threshold_m2)
            if lat is not None:
                self.db.update_triangulated_position(mac, device_type, str(lat), str(lon), mse)
        except Exception as exc:  # noqa: BLE001
            LOG.error('[SnoopR] update_device_status failed for %s (%s): %s',
                      mac, device_type, exc)

    def evict_stale_state(self):
        cutoff = time.time() - 3600
        stale = [key for key, kf in list(self.kalman_filters.items())
                 if kf.last_used < cutoff]
        for key in stale:
            self.kalman_filters.pop(key, None)
        if stale:
            LOG.debug('[SnoopR] evicted %d idle Kalman filters', len(stale))

    # -----------------------------------------------------------------
    # WiGLE fallback
    # -----------------------------------------------------------------
    def _wigle_geolocate(self, ssid):
        if not self.wigle_enabled or not ssid or not self.wigle_api_name:
            return None
        cached = self.wigle_cache.get(ssid)
        if cached is not None:
            return cached or None
        try:
            auth = base64.b64encode(
                ('%s:%s' % (self.wigle_api_name, self.wigle_api_token)).encode()).decode()
            resp = requests.get('https://api.wigle.net/api/v2/network/search',
                                params={'ssid': ssid, 'resultsPerPage': 1},
                                headers={'Authorization': 'Basic %s' % auth}, timeout=10)
            if resp.status_code == 200:
                results = (resp.json() or {}).get('results') or []
                if results:
                    coords = valid_coords(results[0].get('trilat'), results[0].get('trilong'))
                    self.wigle_cache[ssid] = coords or False
                    return coords
            elif resp.status_code == 429:
                LOG.info('[SnoopR] WiGLE rate limit reached; disabling for this session')
                self.wigle_enabled = False
        except (requests.RequestException, ValueError) as exc:
            LOG.debug('[SnoopR] WiGLE lookup failed for %s: %s', ssid, exc)
        self.wigle_cache[ssid] = False
        return None

    # -----------------------------------------------------------------
    # Scanners
    # -----------------------------------------------------------------
    async def _ble_discover(self):
        """bluetooth_device was accepted in config but never passed to bleak, so a
        configured hci1 was ignored. bleak >= 0.20 wants bluez={'adapter': ...}; the
        older `adapter=` kwarg is deprecated and slated for removal."""
        kwargs = {'timeout': self.scan_duration, 'return_adv': True}
        adapter = (self.bluetooth_device or '').strip()
        if not adapter:
            return await BleakScanner.discover(**kwargs)
        if self._ble_adapter_mode is None:
            self._ble_adapter_mode = 'bluez'
            try:
                import bleak as _bleak
                parts = str(getattr(_bleak, '__version__', '0')).split('.')
                if (int(parts[0]), int(parts[1] if len(parts) > 1 else 0)) < (0, 20):
                    self._ble_adapter_mode = 'adapter'
            except (ImportError, ValueError, IndexError):
                pass
            LOG.info('[SnoopR] BLE adapter %s selected via %s kwarg',
                     adapter, self._ble_adapter_mode)
        if self._ble_adapter_mode == 'bluez':
            kwargs['bluez'] = {'adapter': adapter}
        else:
            kwargs['adapter'] = adapter
        try:
            return await BleakScanner.discover(**kwargs)
        except TypeError as exc:
            LOG.warning('[SnoopR] bleak rejected the %s adapter kwarg (%s); '
                        'falling back to the default adapter',
                        self._ble_adapter_mode, exc)
            self.bluetooth_device = ''
            return await BleakScanner.discover(timeout=self.scan_duration, return_adv=True)

    async def _bleak_scan_loop(self):
        while not self.stop_event.is_set():
            try:
                devices = await self._ble_discover()
                lat, lon = self.current_coords()
                if lat == '-' and not self.log_without_gps:
                    await asyncio.sleep(self.scan_interval)
                    continue
                for device, adv in devices.values():
                    rssi = getattr(adv, 'rssi', None)
                    if rssi is None:
                        continue
                    mac = norm_mac(device.address)
                    if mac in self.whitelist_macs:
                        continue
                    name = (getattr(adv, 'local_name', None) or device.name or '')
                    if name.casefold() in self.whitelist_ssids:
                        continue
                    manufacturer_data = getattr(adv, 'manufacturer_data', None) or {}
                    randomized = is_randomized_mac(mac)
                    vendor = self._lookup_oui_vendor(mac)
                    if vendor.startswith('Unknown') and manufacturer_data:
                        vendor = self._lookup_bt_company(next(iter(manufacturer_data)))
                    kf = self._get_kalman(mac, 'bluetooth')
                    self.add_to_buffer(make_detection(
                        mac=mac, type_='bluetooth', name=name or 'Unknown',
                        device_type='bluetooth', vendor=vendor,
                        classification=self._classify_device(name, manufacturer_data),
                        is_rogue=self._detect_rogue(vendor, name),
                        is_mesh=self._detect_mesh(adv), is_randomized=randomized,
                        vulnerabilities=self._detect_vulnerabilities(adv),
                        anomalies=self._detect_ble_anomalies(adv, mac),
                        signal_strength=int(rssi), latitude=lat, longitude=lon,
                        altitude=self.last_gps['altitude'], session_id=self.session_id,
                        filtered_rssi=round(kf.filter(rssi), 2)))
                LOG.debug('[SnoopR] BLE sweep: %d devices', len(devices))
            except asyncio.CancelledError:
                return
            except Exception as exc:  # noqa: BLE001
                LOG.error('[SnoopR] BLE scan error: %s', exc)
            await asyncio.sleep(self.scan_interval)

    def _bleak_thread(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        try:
            self.loop.run_until_complete(self._bleak_scan_loop())
        except Exception as exc:  # noqa: BLE001
            LOG.error('[SnoopR] BLE loop terminated: %s', exc)
        finally:
            try:
                self.loop.close()
            except Exception:  # noqa: BLE001
                pass

    def on_unfiltered_ap_list(self, agent, aps):
        if not self.ready:
            return
        self._update_gps(agent)
        lat, lon = self.current_coords()
        if lat == '-' and not self.log_without_gps:
            return

        for ap in aps or []:
            mac = norm_mac(ap.get('mac'))
            if not mac or mac in self.whitelist_macs:
                continue
            ssid = ap.get('hostname') or ''
            if ssid.casefold() in self.whitelist_ssids:
                continue
            rssi = ap.get('rssi')
            ap_lat, ap_lon = lat, lon
            if ap_lat == '-' and ssid and ssid != '<hidden>':
                coords = self._wigle_geolocate(ssid)
                if coords:
                    ap_lat, ap_lon = str(coords[0]), str(coords[1])
            vendor = ap.get('vendor') or self._lookup_oui_vendor(mac)
            encryption = '%s%s%s' % (ap.get('encryption', ''), ap.get('cipher', ''),
                                     ap.get('authentication', ''))
            channel = ap.get('channel', 0) or 0
            auth_mode = ap.get('authentication', '') or ''
            kf = self._get_kalman(mac, 'wifi')
            self.add_to_buffer(make_detection(
                mac=mac, type_='wi-fi ap', name=ssid, device_type='wifi', vendor=vendor,
                classification='WiFi AP', is_rogue=self._detect_rogue(vendor, ssid),
                is_randomized=is_randomized_mac(mac), encryption=encryption,
                signal_strength=rssi, latitude=ap_lat, longitude=ap_lon, channel=channel,
                auth_mode=auth_mode, altitude=self.last_gps['altitude'],
                session_id=self.session_id,
                filtered_rssi=round(kf.filter(rssi), 2) if rssi is not None else None))

            for client in ap.get('clients') or []:
                client_mac = norm_mac(client if isinstance(client, str) else client.get('mac'))
                if not client_mac or client_mac in self.whitelist_macs:
                    continue
                client_name = '' if isinstance(client, str) else (client.get('hostname') or '')
                client_rssi = rssi if isinstance(client, str) else client.get('rssi', rssi)
                client_kf = self._get_kalman(client_mac, 'wifi')
                self.add_to_buffer(make_detection(
                    mac=client_mac, type_='wi-fi client', name=client_name, device_type='wifi',
                    vendor=self._lookup_oui_vendor(client_mac), classification='WiFi Client',
                    is_randomized=is_randomized_mac(client_mac), encryption=encryption,
                    signal_strength=client_rssi, latitude=ap_lat, longitude=ap_lon,
                    channel=channel, auth_mode=auth_mode,
                    altitude=self.last_gps['altitude'], session_id=self.session_id,
                    filtered_rssi=(round(client_kf.filter(client_rssi), 2)
                                   if client_rssi is not None else None)))

    # -----------------------------------------------------------------
    # Lifecycle
    # -----------------------------------------------------------------
    def on_loaded(self):
        LOG.info('[SnoopR] loading v%s', self.__version__)
        try:
            self._load_config()
            self._check_dependencies()
            self._load_oui_db()

            if not self._load_bluetooth_company_db() and self.bluetooth_enabled:
                threading.Thread(target=self._download_bt_company_db, daemon=True,
                                 name='snoopr-btdb').start()

            self.db = Database(self.db_path)
            self.session_id = self.db.new_session()
            self.counts_cache = self.db.get_network_counts(self.persistence_threshold)
            LOG.info('[SnoopR] session %s started', self.session_id)

            if self.opensky_client_id and self.opensky_client_secret:
                self.opensky = OpenSkyClient(self.opensky_client_id, self.opensky_client_secret)
            else:
                self.opensky = OpenSkyClient()  # anonymous, heavily rate limited
            if self.aircraft_db_csv:
                self.local_aircraft_db = LocalAircraftDB(self.aircraft_db_csv)

            self.web_handler = WebHandler(self)

            self.threads = [
                AircraftProcessor(self, interval=self.aircraft_interval),
                PersistenceAnalyzer(self, interval=self.update_interval,
                                    analysis_days=self.analysis_days),
                MaintenanceThread(self, interval=self.prune_interval_hours * 3600),
                CountsThread(self, interval=10),
                BufferFlusher(self, interval=2.0),
            ]
            for thread in self.threads:
                thread.start()

            if self.mesh_enabled:
                try:
                    self.mesh = MeshNetwork(self.mesh_host, self.mesh_port, self.mesh_peers,
                                            self.mesh_key, HAS_CRYPTO,
                                            self.mesh_allow_plaintext)
                    self.mesh_receiver = MeshReceiver(self)
                    self.mesh_receiver.start()
                    LOG.info('[SnoopR] mesh listening on %s:%s with %d peer(s)',
                             self.mesh_host, self.mesh_port, len(self.mesh_peers))
                except (ValueError, RuntimeError, OSError) as exc:
                    LOG.error('[SnoopR] mesh disabled: %s', exc)
                    self.mesh = None

            if self.bluetooth_enabled and HAS_BLEAK:
                self.bleak_task = threading.Thread(target=self._bleak_thread, daemon=True,
                                                   name='snoopr-ble')
                self.bleak_task.start()
                LOG.info('[SnoopR] BLE scanner started')

            self.ready = True
            LOG.info('[SnoopR] ready')
        except Exception as exc:  # noqa: BLE001
            LOG.error('[SnoopR] failed to load: %s', exc, exc_info=True)
            self.ready = False

    def on_unload(self, ui):
        LOG.info('[SnoopR] unloading')
        self.ready = False
        self.stop_event.set()
        for thread in self.threads:
            thread.stop()
        if self.bleak_task and self.bleak_task.is_alive() and self.loop:
            try:
                self.loop.call_soon_threadsafe(self.loop.stop)
            except RuntimeError:
                pass
            self.bleak_task.join(timeout=5)
        for thread in self.threads:
            thread.join(timeout=5)
        try:
            self.flush_detection_buffer()
        except Exception as exc:  # noqa: BLE001
            LOG.error('[SnoopR] final flush failed: %s', exc)
        if self.mesh:
            self.mesh.close()
        if self.mesh_receiver:
            self.mesh_receiver.join(timeout=3)
        if self.db:
            # Pruning (and VACUUM) happens in MaintenanceThread, not here: it used to be
            # able to hang shutdown for minutes on a large database.
            self.db.disconnect()
        if ui:
            for key in ('snoopr_wifi', 'snoopr_bt', 'snoopr_aircraft', 'snoopr_snoopers',
                        'snoopr_persistence'):
                try:
                    ui.remove_element(key)
                except Exception:  # noqa: BLE001
                    pass
        LOG.info('[SnoopR] unloaded')

    UI_LABELS = {'wifi': ('snoopr_wifi', 'WiFi:'), 'bt': ('snoopr_bt', 'BT:'),
                 'aircraft': ('snoopr_aircraft', 'Air:'),
                 'snoopers': ('snoopr_snoopers', 'Snoop:'),
                 'persistence': ('snoopr_persistence', 'Pers:')}

    def on_ui_setup(self, ui):
        if not self.ui_enabled:
            return
        y = self.ui_y
        try:
            height = ui.height()
        except Exception:  # noqa: BLE001
            height = 0
        for name in self.ui_elements:
            entry = self.UI_LABELS.get(name)
            if not entry:
                continue
            key, label = entry
            if height and y > height - self.ui_line_height:
                LOG.warning('[SnoopR] UI element %s would overflow the display; skipped', key)
                continue
            ui.add_element(key, LabeledValue(color=BLACK, label=label, value='0',
                                             position=(self.ui_x, y),
                                             label_font=fonts.Small, text_font=fonts.Small))
            y += self.ui_line_height

    def on_ui_update(self, ui):
        if not (self.ui_enabled and self.ready):
            return
        counts = self.counts_cache  # refreshed by CountsThread, never queried from here
        mapping = {'wifi': counts.get('wifi', 0), 'bt': counts.get('bluetooth', 0),
                   'aircraft': counts.get('aircraft', 0),
                   'snoopers': counts.get('snoopers', 0),
                   'persistence': counts.get('high_persistence', 0)}
        for name, value in mapping.items():
            entry = self.UI_LABELS.get(name)
            if entry and name in self.ui_elements:
                try:
                    ui.set(entry[0], str(value))
                except Exception:  # noqa: BLE001
                    pass

    def on_webhook(self, path, request):
        if not self.web_handler:
            return 'SnoopR is still starting up', 503
        try:
            return self.web_handler.handle(path, request)
        except Exception as exc:  # noqa: BLE001
            if exc.__class__.__name__ == 'HTTPException':
                raise
            LOG.error('[SnoopR] webhook error on %r: %s', path, exc)
            return 'Internal error', 500
