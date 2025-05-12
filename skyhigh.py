import logging
import os
import json
import time
from datetime import datetime, timedelta
import requests
from threading import Lock
from flask import render_template_string, request, jsonify

import pwnagotchi.plugins as plugins
import pwnagotchi.ui.fonts as fonts
from pwnagotchi.ui.components import LabeledValue
from pwnagotchi.ui.view import BLACK

class SkyHigh(plugins.Plugin):
    __author__ = 'AlienMajik'
    __version__ = '1.0.9'
    __license__ = 'GPL3'
    __description__ = 'A plugin that fetches aircraft data from the OpenSky API using GPS coordinates, logs it, prunes old entries, and provides a webhook with aircraft type, flight path visualization, and enhanced iconography.'

    def __init__(self):
        self.options = {
            'timer': 60,  # Time interval in seconds for fetching new aircraft data
            'aircraft_file': '/root/handshakes/skyhigh_aircraft.json',  # File to store detected aircraft information
            'adsb_x_coord': 160,
            'adsb_y_coord': 80,
            'latitude': -66.273334,  # Default latitude (Flying Saucer)
            'longitude': 100.984166,  # Default longitude (Flying Saucer)
            'radius': 50,  # Radius in miles to fetch aircraft data
            'prune_minutes': 5,  # Default pruning interval in minutes
            'opensky_username': None,  # Optional OpenSky username for authenticated requests
            'opensky_password': None   # Optional OpenSky password for authenticated requests
        }
        self.last_fetch_time = 0
        self.data = {}
        self.data_lock = Lock()
        self.last_gps = {'latitude': None, 'longitude': None}
        self.credentials_valid = True
        self.flight_path_access = True
        self.metadata_access = True
        self.historical_positions = {}

    def on_loaded(self):
        logging.info("[SkyHigh] Plugin loaded.")
        if not os.path.exists(os.path.dirname(self.options['aircraft_file'])):
            os.makedirs(os.path.dirname(self.options['aircraft_file']))
        if not os.path.exists(self.options['aircraft_file']):
            with open(self.options['aircraft_file'], 'w') as f:
                json.dump({}, f)
        with open(self.options['aircraft_file'], 'r') as f:
            self.data = json.load(f)

    def on_ui_setup(self, ui):
        ui.add_element('SkyHigh', LabeledValue(color=BLACK,
                                              label='SkyHigh',
                                              value=" ",
                                              position=(self.options["adsb_x_coord"],
                                                        self.options["adsb_y_coord"]),
                                              label_font=fonts.Small,
                                              text_font=fonts.Small))

    def on_ui_update(self, ui):
        current_time = time.time()
        if current_time - self.last_fetch_time >= self.options['timer']:
            ui.set('SkyHigh', "Updating...")
            self.last_fetch_time = current_time
            result = self.fetch_aircraft_data()
            ui.set('SkyHigh', result)
        else:
            with self.data_lock:
                aircraft_count = len(self.data)
            minutes_ago = int((current_time - self.last_fetch_time) / 60)
            ui.set('SkyHigh', f"{aircraft_count} aircrafts (Last: {minutes_ago}m)")

    def fetch_aircraft_data(self):
        logging.debug("[SkyHigh] Fetching aircraft data from API...")
        try:
            lat, lon, radius = self.options['latitude'], self.options['longitude'], self.options['radius']
            lat_min, lat_max = lat - (radius / 69), lat + (radius / 69)
            lon_min, lon_max = lon - (radius / 69), lon + (radius / 69)
            url = f"https://opensky-network.org/api/states/all?lamin={lat_min}&lomin={lon_min}&lamax={lat_max}&lomax={lon_max}"
            
            headers = {}
            if self.options['opensky_username'] and self.options['opensky_password'] and self.credentials_valid:
                import base64
                auth_str = f"{self.options['opensky_username']}:{self.options['opensky_password']}"
                auth_encoded = base64.b64encode(auth_str.encode()).decode()
                headers['Authorization'] = f'Basic {auth_encoded}'
                logging.debug(f"[SkyHigh] Attempting authenticated request to {url}")
            
            response = requests.get(url, headers=headers if headers else None, timeout=10)
            
            if response.status_code == 200:
                aircrafts = self.parse_api_response(response.json())
                self.prune_old_data()
                with self.data_lock:
                    with open(self.options['aircraft_file'], 'w') as f:
                        json.dump(self.data, f)
                logging.debug("[SkyHigh] Fetch completed successfully.")
                return f"{len(aircrafts)} aircrafts detected"
            elif response.status_code == 401:
                logging.warning("[SkyHigh] Authentication failed for /states/all. Falling back to anonymous access.")
                self.credentials_valid = False
                response = requests.get(url, timeout=10)
                if response.status_code == 200:
                    aircrafts = self.parse_api_response(response.json())
                    self.prune_old_data()
                    with self.data_lock:
                        with open(self.options['aircraft_file'], 'w') as f:
                            json.dump(self.data, f)
                    logging.debug("[SkyHigh] Fetch completed successfully (anonymous).")
                    return f"{len(aircrafts)} aircrafts detected"
                else:
                    logging.error("[SkyHigh] Anonymous fetch failed with status code %d", response.status_code)
                    return "Fetch error"
            else:
                logging.error("[SkyHigh] API returned status code %d", response.status_code)
                return "Fetch error"
        except requests.exceptions.RequestException as e:
            logging.error("[SkyHigh] Error fetching data from API: %s", e)
            return "Fetch failed"

    def fetch_aircraft_metadata(self, icao24):
        """Fetch metadata for a specific aircraft using its ICAO24 code."""
        try:
            if not self.metadata_access:
                logging.warning(f"[SkyHigh] Metadata access unavailable for {icao24}. Attempting anonymous access.")
                response = requests.get(f"https://opensky-network.org/api/metadata/aircraft/icao/{icao24}", timeout=5)
                if response.status_code == 200:
                    data = response.json()
                    manufacturer = data.get('manufacturerName', '') or ''
                    model = data.get('model', 'Unknown') or 'Unknown'
                    registration = data.get('registration', 'Unknown') or 'Unknown'
                    db_flags = data.get('special_flags', []) or []
                    typecode = data.get('typecode', '') or ''

                    # Safely handle None values before calling lower()
                    manufacturer_lower = manufacturer.lower() if isinstance(manufacturer, str) else ''
                    model_lower = model.lower() if isinstance(model, str) else ''
                    typecode_lower = typecode.lower() if isinstance(typecode, str) else ''
                    db_flags_lower = ', '.join([flag.lower() for flag in db_flags if isinstance(flag, str)])

                    # Categorization based on manufacturer, model, typecode, and DB flags
                    is_helicopter = 'helicopter' in model_lower
                    is_commercial_jet = (
                        any(jet in manufacturer_lower for jet in ['airbus', 'boeing', 'embraer', 'bombardier']) or
                        any(model_lower.startswith(prefix) for prefix in ['a', 'b', 'e', 'crj', 'erj']) or
                        any(typecode_lower.startswith(prefix) for prefix in ['a', 'b', 'e', 'crj', 'erj'])
                    )
                    is_small_plane = (
                        any(small in manufacturer_lower for small in ['cessna', 'piper', 'beechcraft', 'cirrus']) or
                        any(model_lower.startswith(prefix) for prefix in ['c', 'p', 'be', 'sr']) or
                        any(typecode_lower.startswith(prefix) for prefix in ['c', 'p', 'be', 'sr'])
                    )
                    is_drone = 'drone' in model_lower or 'uav' in model_lower
                    is_glider = 'glider' in model_lower
                    is_military = 'military' in db_flags_lower

                    logging.debug(f"[SkyHigh] Metadata for {icao24}: manufacturer={manufacturer}, model={model}, typecode={typecode}, db_flags={db_flags_lower}, is_helicopter={is_helicopter}, is_commercial_jet={is_commercial_jet}, is_small_plane={is_small_plane}, is_drone={is_drone}, is_glider={is_glider}, is_military={is_military}")
                    return {
                        'model': model,
                        'registration': registration,
                        'db_flags': db_flags_lower,
                        'is_helicopter': is_helicopter,
                        'is_commercial_jet': is_commercial_jet,
                        'is_small_plane': is_small_plane,
                        'is_drone': is_drone,
                        'is_glider': is_glider,
                        'is_military': is_military
                    }
                else:
                    logging.error(f"[SkyHigh] Anonymous metadata fetch failed for {icao24}: {response.status_code}")
                    return None

            url = f"https://opensky-network.org/api/metadata/aircraft/icao/{icao24}"
            auth = None
            if self.options['opensky_username'] and self.options['opensky_password'] and self.credentials_valid:
                auth = (self.options['opensky_username'], self.options['opensky_password'])
                logging.debug(f"[SkyHigh] Using OpenSky credentials: username={self.options['opensky_username']}")
            else:
                logging.warning("[SkyHigh] OpenSky credentials not provided or invalid. Attempting anonymous metadata fetch.")
            
            response = requests.get(url, auth=auth, timeout=5)
            if response.status_code == 200:
                data = response.json()
                manufacturer = data.get('manufacturerName', '') or ''
                model = data.get('model', 'Unknown') or 'Unknown'
                registration = data.get('registration', 'Unknown') or 'Unknown'
                db_flags = data.get('special_flags', []) or []
                typecode = data.get('typecode', '') or ''

                # Safely handle None values before calling lower()
                manufacturer_lower = manufacturer.lower() if isinstance(manufacturer, str) else ''
                model_lower = model.lower() if isinstance(model, str) else ''
                typecode_lower = typecode.lower() if isinstance(typecode, str) else ''
                db_flags_lower = ', '.join([flag.lower() for flag in db_flags if isinstance(flag, str)])

                # Categorization based on manufacturer, model, typecode, and DB flags
                is_helicopter = 'helicopter' in model_lower
                is_commercial_jet = (
                    any(jet in manufacturer_lower for jet in ['airbus', 'boeing', 'embraer', 'bombardier']) or
                    any(model_lower.startswith(prefix) for prefix in ['a', 'b', 'e', 'crj', 'erj']) or
                    any(typecode_lower.startswith(prefix) for prefix in ['a', 'b', 'e', 'crj', 'erj'])
                )
                is_small_plane = (
                    any(small in manufacturer_lower for small in ['cessna', 'piper', 'beechcraft', 'cirrus']) or
                    any(model_lower.startswith(prefix) for prefix in ['c', 'p', 'be', 'sr']) or
                    any(typecode_lower.startswith(prefix) for prefix in ['c', 'p', 'be', 'sr'])
                )
                is_drone = 'drone' in model_lower or 'uav' in model_lower
                is_glider = 'glider' in model_lower
                is_military = 'military' in db_flags_lower

                logging.debug(f"[SkyHigh] Metadata for {icao24}: manufacturer={manufacturer}, model={model}, typecode={typecode}, db_flags={db_flags_lower}, is_helicopter={is_helicopter}, is_commercial_jet={is_commercial_jet}, is_small_plane={is_small_plane}, is_drone={is_drone}, is_glider={is_glider}, is_military={is_military}")
                return {
                    'model': model,
                    'registration': registration,
                    'db_flags': db_flags_lower,
                    'is_helicopter': is_helicopter,
                    'is_commercial_jet': is_commercial_jet,
                    'is_small_plane': is_small_plane,
                    'is_drone': is_drone,
                    'is_glider': is_glider,
                    'is_military': is_military
                }
            elif response.status_code == 401:
                self.credentials_valid = False
                self.metadata_access = False
                logging.warning("[SkyHigh] Invalid OpenSky credentials or insufficient permissions for metadata fetch. Falling back to anonymous access.")
                response = requests.get(url, timeout=5)
                if response.status_code == 200:
                    data = response.json()
                    manufacturer = data.get('manufacturerName', '') or ''
                    model = data.get('model', 'Unknown') or 'Unknown'
                    registration = data.get('registration', 'Unknown') or 'Unknown'
                    db_flags = data.get('special_flags', []) or []
                    typecode = data.get('typecode', '') or ''

                    # Safely handle None values before calling lower()
                    manufacturer_lower = manufacturer.lower() if isinstance(manufacturer, str) else ''
                    model_lower = model.lower() if isinstance(model, str) else ''
                    typecode_lower = typecode.lower() if isinstance(typecode, str) else ''
                    db_flags_lower = ', '.join([flag.lower() for flag in db_flags if isinstance(flag, str)])

                    # Categorization based on manufacturer, model, typecode, and DB flags
                    is_helicopter = 'helicopter' in model_lower
                    is_commercial_jet = (
                        any(jet in manufacturer_lower for jet in ['airbus', 'boeing', 'embraer', 'bombardier']) or
                        any(model_lower.startswith(prefix) for prefix in ['a', 'b', 'e', 'crj', 'erj']) or
                        any(typecode_lower.startswith(prefix) for prefix in ['a', 'b', 'e', 'crj', 'erj'])
                    )
                    is_small_plane = (
                        any(small in manufacturer_lower for small in ['cessna', 'piper', 'beechcraft', 'cirrus']) or
                        any(model_lower.startswith(prefix) for prefix in ['c', 'p', 'be', 'sr']) or
                        any(typecode_lower.startswith(prefix) for prefix in ['c', 'p', 'be', 'sr'])
                    )
                    is_drone = 'drone' in model_lower or 'uav' in model_lower
                    is_glider = 'glider' in model_lower
                    is_military = 'military' in db_flags_lower

                    logging.debug(f"[SkyHigh] Metadata for {icao24}: manufacturer={manufacturer}, model={model}, typecode={typecode}, db_flags={db_flags_lower}, is_helicopter={is_helicopter}, is_commercial_jet={is_commercial_jet}, is_small_plane={is_small_plane}, is_drone={is_drone}, is_glider={is_glider}, is_military={is_military}")
                    return {
                        'model': model,
                        'registration': registration,
                        'db_flags': db_flags_lower,
                        'is_helicopter': is_helicopter,
                        'is_commercial_jet': is_commercial_jet,
                        'is_small_plane': is_small_plane,
                        'is_drone': is_drone,
                        'is_glider': is_glider,
                        'is_military': is_military
                    }
                else:
                    logging.error(f"[SkyHigh] Anonymous metadata fetch failed for {icao24}: {response.status_code}")
                    return None
            else:
                logging.warning(f"[SkyHigh] Failed to fetch metadata for {icao24}: {response.status_code}")
                return None
        except requests.exceptions.RequestException as e:
            logging.error(f"[SkyHigh] Error fetching metadata for {icao24}: {e}")
            return None

    def fetch_flight_path(self, icao24):
        """Fetch flight path data for a specific aircraft."""
        try:
            if not self.credentials_valid:
                return {'error': 'OpenSky credentials invalid or insufficient permissions. Falling back to historical positions.'}

            if not self.flight_path_access:
                return {'error': 'Flight path access unavailable. Your OpenSky account lacks permissions for flight tracks. Using historical positions instead.'}

            time_ranges = [3600, 7200, 14400]
            headers = {}
            if self.options['opensky_username'] and self.options['opensky_password']:
                import base64
                auth_str = f"{self.options['opensky_username']}:{self.options['opensky_password']}"
                auth_encoded = base64.b64encode(auth_str.encode()).decode()
                headers['Authorization'] = f'Basic {auth_encoded}'
                logging.debug(f"[SkyHigh] Using OpenSky credentials: username={self.options['opensky_username']}")
            else:
                return {'error': 'Authentication credentials not provided'}

            for time_range in time_ranges:
                current_time = int(time.time())
                url = f"https://opensky-network.org/api/tracks/all?icao24={icao24}&time={current_time - time_range}"
                response = requests.get(url, headers=headers, timeout=5)
                
                if response.status_code == 200:
                    data = response.json()
                    if 'path' in data and data['path']:
                        return data
                elif response.status_code == 404:
                    logging.debug(f"[SkyHigh] No flight path data for {icao24} in the last {time_range} seconds")
                    continue
                elif response.status_code == 401:
                    self.flight_path_access = False
                    return {'error': 'Flight path access unavailable. Your OpenSky account lacks permissions for flight tracks. Using historical positions instead.'}
                else:
                    logging.warning(f"[SkyHigh] Failed to fetch flight path for {icao24}: {response.status_code}")
                    continue
            
            return {'error': 'No recent flight path data available'}
        except requests.exceptions.RequestException as e:
            logging.error(f"[SkyHigh] Error fetching flight path for {icao24}: {e}")
            return {'error': 'Network error'}

    def get_historical_path(self, icao24):
        """Retrieve historical positions for an aircraft to approximate its flight path."""
        with self.data_lock:
            if icao24 in self.historical_positions and len(self.historical_positions[icao24]) > 1:
                path = []
                for pos in self.historical_positions[icao24]:
                    path.append([int(pos['timestamp']), pos['latitude'], pos['longitude'], pos['baro_altitude'], pos['true_track'], False])
                return {'path': path}
            return {'error': 'Insufficient historical data to plot flight path'}

    def parse_api_response(self, api_data):
        aircrafts = []
        if 'states' in api_data and api_data['states'] is not None:
            for state in api_data['states']:
                icao24 = state[0]
                callsign = state[1].strip() if state[1] else "Unknown"
                latitude = state[6] if state[6] is not None else 'N/A'
                longitude = state[5] if state[5] is not None else 'N/A'
                baro_altitude = state[7] if state[7] is not None else 'N/A'
                geo_altitude = state[13] if state[13] is not None else 'N/A'
                velocity = state[9] if state[9] is not None else 'N/A'
                true_track = state[10] if state[10] is not None else 'N/A'
                vertical_rate = state[11] if state[11] is not None else 'N/A'
                on_ground = state[8]
                squawk = state[14] if state[14] is not None else 'N/A'
                timestamp = state[4] if state[4] is not None else int(time.time())
                
                with self.data_lock:
                    if latitude != 'N/A' and longitude != 'N/A':
                        position = {
                            'timestamp': timestamp,
                            'latitude': latitude,
                            'longitude': longitude,
                            'baro_altitude': baro_altitude,
                            'true_track': true_track
                        }
                        if icao24 not in self.historical_positions:
                            self.historical_positions[icao24] = []
                        self.historical_positions[icao24].append(position)
                        self.historical_positions[icao24] = self.historical_positions[icao24][-10:]

                    if icao24 not in self.data or 'model' not in self.data[icao24]:
                        metadata = self.fetch_aircraft_metadata(icao24)
                        if metadata:
                            if 'error' in metadata:
                                self.data[icao24] = {
                                    'model': 'Unknown',
                                    'registration': 'Unknown',
                                    'db_flags': '',
                                    'is_helicopter': False,
                                    'is_commercial_jet': False,
                                    'is_small_plane': False,
                                    'is_drone': False,
                                    'is_glider': False,
                                    'is_military': False
                                }
                            else:
                                self.data[icao24] = metadata
                        else:
                            self.data[icao24] = {
                                'model': 'Unknown',
                                'registration': 'Unknown',
                                'db_flags': '',
                                'is_helicopter': False,
                                'is_commercial_jet': False,
                                'is_small_plane': False,
                                'is_drone': False,
                                'is_glider': False,
                                'is_military': False
                            }
                        time.sleep(0.1)
                    self.data[icao24].update({
                        'callsign': callsign,
                        'latitude': latitude,
                        'longitude': longitude,
                        'baro_altitude': baro_altitude,
                        'geo_altitude': geo_altitude,
                        'velocity': velocity,
                        'true_track': true_track,
                        'vertical_rate': vertical_rate,
                        'on_ground': on_ground,
                        'squawk': squawk,
                        'last_seen': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    })
                aircrafts.append({
                    'icao24': icao24,
                    'callsign': callsign,
                    'latitude': latitude,
                    'longitude': longitude,
                    'baro_altitude': baro_altitude,
                    'geo_altitude': geo_altitude,
                    'velocity': velocity,
                    'true_track': true_track,
                    'vertical_rate': vertical_rate,
                    'on_ground': on_ground,
                    'squawk': squawk,
                    'is_helicopter': self.data[icao24].get('is_helicopter', False),
                    'is_commercial_jet': self.data[icao24].get('is_commercial_jet', False),
                    'is_small_plane': self.data[icao24].get('is_small_plane', False),
                    'is_drone': self.data[icao24].get('is_drone', False),
                    'is_glider': self.data[icao24].get('is_glider', False),
                    'is_military': self.data[icao24].get('is_military', False),
                    'model': self.data[icao24].get('model', 'Unknown'),
                    'registration': self.data[icao24].get('registration', 'Unknown'),
                    'db_flags': self.data[icao24].get('db_flags', '')
                })
        return aircrafts

    def prune_old_data(self):
        """Remove aircraft entries older than the configured prune_minutes interval."""
        prune_minutes = self.options.get('prune_minutes', 0)
        if prune_minutes <= 0:
            return
        now = datetime.now()
        cutoff = now - timedelta(minutes=prune_minutes)
        keys_to_remove = []
        with self.data_lock:
            for icao24, info in self.data.items():
                last_seen = datetime.strptime(info['last_seen'], '%Y-%m-%d %H:%M:%S')
                if last_seen < cutoff:
                    keys_to_remove.append(icao24)
            for key in keys_to_remove:
                del self.data[key]
                if key in self.historical_positions:
                    del self.historical_positions[key]
        logging.debug(f"[SkyHigh] Pruned {len(keys_to_remove)} old aircraft entries.")

    def on_webhook(self, path, request):
        if request.method == 'GET':
            if path == '/' or not path:
                try:
                    with open(self.options['aircraft_file'], 'r') as f:
                        aircraft_dict = json.load(f)
                    aircrafts = list(aircraft_dict.values())
                    center = [self.last_gps['latitude'] or self.options['latitude'], 
                              self.last_gps['longitude'] or self.options['longitude']]
                    return render_template_string(HTML_TEMPLATE, aircrafts=aircrafts, center=center)
                except (FileNotFoundError, json.JSONDecodeError):
                    aircrafts = []
                    center = [self.options['latitude'], self.options['longitude']]
                    return render_template_string(HTML_TEMPLATE, aircrafts=aircrafts, center=center)
            elif path.startswith('flightpath/'):
                icao24 = path.split('/')[-1]
                flight_path_data = self.fetch_flight_path(icao24)
                if 'error' in flight_path_data and 'Using historical positions' in flight_path_data['error']:
                    flight_path_data = self.get_historical_path(icao24)
                return jsonify(flight_path_data)
        return "Not found", 404

    def on_unload(self, ui):
        with ui._lock:
            ui.remove_element('SkyHigh')

HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SkyHigh - Aircraft Map</title>
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        table { width: 100%; border-collapse: collapse; }
        th, td { padding: 8px; text-align: left; border-bottom: 1px solid #ddd; }
        #map { height: 400px; margin-top: 20px; }
    </style>
</head>
<body>
    <h1>Aircraft Detected by SkyHigh</h1>
    <table>
        <thead>
            <tr>
                <th>Callsign</th>
                <th>Model</th>
                <th>Registration</th>
                <th>Latitude</th>
                <th>Longitude</th>
                <th>Baro Altitude</th>
                <th>Geo Altitude</th>
                <th>Velocity</th>
                <th>True Track</th>
                <th>Vertical Rate</th>
                <th>On Ground</th>
                <th>Squawk</th>
                <th>DB Flags</th>
                <th>Last Seen</th>
            </tr>
        </thead>
        <tbody>
            {% for aircraft in aircrafts %}
            <tr>
                <td>{{ aircraft.callsign }}</td>
                <td>{{ aircraft.model }}</td>
                <td>{{ aircraft.registration }}</td>
                <td>{{ aircraft.latitude }}</td>
                <td>{{ aircraft.longitude }}</td>
                <td>{{ aircraft.baro_altitude }}</td>
                <td>{{ aircraft.geo_altitude }}</td>
                <td>{{ aircraft.velocity }}</td>
                <td>{{ aircraft.true_track }}</td>
                <td>{{ aircraft.vertical_rate }}</td>
                <td>{{ 'Yes' if aircraft.on_ground else 'No' }}</td>
                <td>{{ aircraft.squawk }}</td>
                <td>{{ aircraft.db_flags }}</td>
                <td>{{ aircraft.last_seen }}</td>
            </tr>
            {% endfor %}
        </tbody>
    </table>
    <div id="map"></div>
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <script>
        var aircrafts = {{ aircrafts | tojson }};
        var center = {{ center | tojson }};
        var map = L.map('map').setView(center, 10);
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '© OpenStreetMap contributors'
        }).addTo(map);

        var helicopterIcon = L.icon({
            iconUrl: 'data:image/svg+xml;base64,' + btoa(`
                <svg xmlns="http://www.w3.org/2000/svg" width="30" height="30" viewBox="0 0 24 24" fill="red">
                    <path d="M3 11h18v2H3v-2zm18 4H3v2h18v-2zm-1-9h-2V3H6v3H4v2h16V6zm-8 12h-2v3H8v-3H6v-2h6v2z"/>
                </svg>
            `),
            iconSize: [30, 30],
            iconAnchor: [15, 15],
            popupAnchor: [0, -15]
        });

        var commercialJetIcon = L.icon({
            iconUrl: 'data:image/svg+xml;base64,' + btoa(`
                <svg xmlns="http://www.w3.org/2000/svg" width="30" height="30" viewBox="0 0 24 24" fill="blue">
                    <path d="M22 4h-2l-4 6h-4l-2-3H8l-2 3H2L0 4H0v16h2l2-3h4l2 3h2l2-3h4l4 3h2V4zm-8 12H8l-2 3H4l-2-3V6h2l2 3h4l2-3h4l-2 3h-2l-2-3h-2v10z"/>
                </svg>
            `),
            iconSize: [30, 30],
            iconAnchor: [15, 15],
            popupAnchor: [0, -15]
        });

        var smallPlaneIcon = L.icon({
            iconUrl: 'data:image/svg+xml;base64,' + btoa(`
                <svg xmlns="http://www.w3.org/2000/svg" width="30" height="30" viewBox="0 0 24 24" fill="yellow">
                    <path d="M20 4h-2l-3 5h-3l-2-3H8l-2 3H3l-3-5h-2v16h2l3-5h3l2 3h2l2-3h3l3 5h2V4zm-8 12H8l-2 3H4l-2-3V6h2l2 3h4l2-3h4l-2 3h-2l-2-3h-2v10z"/>
                </svg>
            `),
            iconSize: [30, 30],
            iconAnchor: [15, 15],
            popupAnchor: [0, -15]
        });

        var droneIcon = L.icon({
            iconUrl: 'data:image/svg+xml;base64,' + btoa(`
                <svg xmlns="http://www.w3.org/2000/svg" width="30" height="30" viewBox="0 0 24 24" fill="purple">
                    <path d="M12 2a10 10 0 00-8 4h4v4H4v4h4v4H2a10 10 0 0020 0h-6v-4h4v-4h-4V6h4a10 10 0 00-8-4zm0 2a8 8 0 016 3h-3v4h4v2h-4v4h3a8 8 0 01-12 0h3v-4H6v-2h4V6H7a8 8 0 015-3z"/>
                </svg>
            `),
            iconSize: [30, 30],
            iconAnchor: [15, 15],
            popupAnchor: [0, -15]
        });

        var gliderIcon = L.icon({
            iconUrl: 'data:image/svg+xml;base64,' + btoa(`
                <svg xmlns="http://www.w3.org/2000/svg" width="30" height="30" viewBox="0 0 24 24" fill="orange">
                    <path d="M22 4l-9 5-9-5-1 2 9 5v9l-3-2v-5h-2v5l-3 2v2l5-2v-7l9-5 1-2zm-11 9h2v-2h-2v2z"/>
                </svg>
            `),
            iconSize: [30, 30],
            iconAnchor: [15, 15],
            popupAnchor: [0, -15]
        });

        var militaryIcon = L.icon({
            iconUrl: 'data:image/svg+xml;base64,' + btoa(`
                <svg xmlns="http://www.w3.org/2000/svg" width="30" height="30" viewBox="0 0 24 24" fill="green">
                    <path d="M12 2L2 7v10l10 5 10-5V7l-10-5zm0 2.83l6.56 3.28v6.88L12 18.17l-6.56-3.28V8.11L12 4.83zm-1 3.17v6h2v-6h-2z"/>
                </svg>
            `),
            iconSize: [30, 30],
            iconAnchor: [15, 15],
            popupAnchor: [0, -15]
        });

        var flightPaths = {};

        function fetchFlightPath(icao24, marker) {
            fetch(`/plugins/skyhigh/flightpath/${icao24}`)
                .then(response => {
                    if (!response.ok) throw new Error('Failed to fetch flight path: ' + response.status);
                    return response.json();
                })
                .then(data => {
                    if (data.error) {
                        alert(data.error);
                        return;
                    }
                    if (data.path && data.path.length > 0) {
                        var pathCoords = data.path.map(point => [point[1], point[2]]);
                        if (flightPaths[icao24]) {
                            map.removeLayer(flightPaths[icao24]);
                            delete flightPaths[icao24];
                        } else {
                            flightPaths[icao24] = L.polyline(pathCoords, { color: 'blue', weight: 2 }).addTo(map);
                            map.fitBounds(flightPaths[icao24].getBounds());
                        }
                    } else {
                        alert('No recent flight path data available for this aircraft.');
                    }
                })
                .catch(error => {
                    console.error('Error fetching flight path:', error);
                    alert('Failed to retrieve flight path: ' + error.message);
                });
        }

        aircrafts.forEach(function(aircraft) {
            console.log("Aircraft:", aircraft.icao24, "Model:", aircraft.model, "is_helicopter:", aircraft.is_helicopter, "is_commercial_jet:", aircraft.is_commercial_jet, "is_small_plane:", aircraft.is_small_plane, "is_drone:", aircraft.is_drone, "is_glider:", aircraft.is_glider, "is_military:", aircraft.is_military);
            if (aircraft.latitude && aircraft.longitude && aircraft.latitude !== 'N/A' && aircraft.longitude !== 'N/A') {
                var marker;
                if (aircraft.is_military) {
                    marker = L.marker([aircraft.latitude, aircraft.longitude], { icon: militaryIcon });
                } else if (aircraft.is_helicopter) {
                    marker = L.marker([aircraft.latitude, aircraft.longitude], { icon: helicopterIcon });
                } else if (aircraft.is_commercial_jet) {
                    marker = L.marker([aircraft.latitude, aircraft.longitude], { icon: commercialJetIcon });
                } else if (aircraft.is_small_plane) {
                    marker = L.marker([aircraft.latitude, aircraft.longitude], { icon: smallPlaneIcon });
                } else if (aircraft.is_drone) {
                    marker = L.marker([aircraft.latitude, aircraft.longitude], { icon: droneIcon });
                } else if (aircraft.is_glider) {
                    marker = L.marker([aircraft.latitude, aircraft.longitude], { icon: gliderIcon });
                } else {
                    marker = L.marker([aircraft.latitude, aircraft.longitude]);
                }
                marker.addTo(map).bindPopup(
                    `Callsign: ${aircraft.callsign}<br>
                     Model: ${aircraft.model}<br>
                     Registration: ${aircraft.registration}<br>
                     Altitude: ${aircraft.baro_altitude} m<br>
                     Velocity: ${aircraft.velocity} m/s<br>
                     True Track: ${aircraft.true_track}°<br>
                     Squawk: ${aircraft.squawk}<br>
                     DB Flags: ${aircraft.db_flags}`
                );
                marker.on('click', function() {
                    fetchFlightPath(aircraft.icao24, marker);
                });
            }
        });

        var bounds = aircrafts.map(a => [a.latitude, a.longitude]).filter(b => b[0] && b[1] && b[0] !== 'N/A' && b[1] !== 'N/A');
        if (bounds.length > 0) {
            map.fitBounds(bounds);
        }
    </script>
</body>
</html>
'''
