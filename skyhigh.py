import logging
import os
import json
import time
from datetime import datetime, timedelta
import requests
from threading import Lock
from flask import render_template_string

import pwnagotchi.plugins as plugins
import pwnagotchi.ui.fonts as fonts
from pwnagotchi.ui.components import LabeledValue
from pwnagotchi.ui.view import BLACK

class SkyHigh(plugins.Plugin):
    __author__ = 'AlienMajik'
    __version__ = '1.0.0'
    __license__ = 'GPL3'
    __description__ = 'A plugin that fetches aircraft data from an API using GPS coordinates, logs it, prunes old entries, and provides a webhook with aircraft type and origin country visualization.'

    def __init__(self):
        self.options = {
            'timer': 60,  # Time interval in seconds for fetching new aircraft data
            'aircraft_file': '/root/handshakes/skyhigh_aircraft.json',  # File to store detected aircraft information
            'adsb_x_coord': 160,
            'adsb_y_coord': 80,
            'latitude': -66.273334,  # Default latitude (Flying Saucer)
            'longitude': 100.984166,  # Default longitude (Flying Saucer)
            'radius': 50,  # Radius in miles to fetch aircraft data
            'prune_minutes': 5  # Default pruning interval in minutes
        }
        self.last_fetch_time = 0
        self.data = {}
        self.data_lock = Lock()
        self.last_gps = {'latitude': None, 'longitude': None}  # To store last known GPS coordinates

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
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                aircrafts = self.parse_api_response(response.json())
                self.prune_old_data()
                with self.data_lock:
                    with open(self.options['aircraft_file'], 'w') as f:
                        json.dump(self.data, f)
                logging.debug("[SkyHigh] Fetch completed successfully.")
                return f"{len(aircrafts)} aircrafts detected"
            else:
                logging.error("[SkyHigh] API returned status code %d", response.status_code)
                return "Fetch error"
        except requests.exceptions.RequestException as e:
            logging.error("[SkyHigh] Error fetching data from API: %s", e)
            return "Fetch failed"

    def fetch_aircraft_metadata(self, icao24):
        """Fetch metadata for a specific aircraft using its ICAO24 code."""
        try:
            url = f"https://opensky-network.org/api/metadata/aircraft/icao/{icao24}"
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                data = response.json()
                model = data.get('model', 'Unknown')
                origin_country = data.get('registered', 'Unknown')
                db_flags = ', '.join(data.get('special_flags', []))  # DB flags like military, PIA, LAD
                is_helicopter = 'helicopter' in model.lower()
                return {
                    'model': model,
                    'origin_country': origin_country,
                    'db_flags': db_flags,
                    'is_helicopter': is_helicopter
                }
            else:
                logging.warning(f"[SkyHigh] Failed to fetch metadata for {icao24}: {response.status_code}")
                return None
        except requests.exceptions.RequestException as e:
            logging.error(f"[SkyHigh] Error fetching metadata for {icao24}: {e}")
            return None

    def parse_api_response(self, api_data):
        aircrafts = []
        if 'states' in api_data:
            for state in api_data['states']:
                icao24 = state[0]
                callsign = state[1].strip() if state[1] else "Unknown"
                latitude = state[6]
                longitude = state[5]
                altitude = state[7]
                with self.data_lock:
                    if icao24 not in self.data or 'model' not in self.data[icao24]:
                        metadata = self.fetch_aircraft_metadata(icao24)
                        if metadata:
                            self.data[icao24] = metadata
                        else:
                            self.data[icao24] = {'model': 'Unknown', 'origin_country': 'Unknown', 'db_flags': '', 'is_helicopter': False}
                        time.sleep(0.1)  # Small delay to avoid rate limits
                    self.data[icao24].update({
                        'callsign': callsign,
                        'latitude': latitude,
                        'longitude': longitude,
                        'altitude': altitude,
                        'last_seen': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    })
                aircrafts.append({
                    'icao24': icao24,
                    'callsign': callsign,
                    'latitude': latitude,
                    'longitude': longitude,
                    'altitude': altitude
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
                <th>DB Flags</th>
                <th>Type</th>
                <th>Latitude</th>
                <th>Longitude</th>
                <th>Altitude</th>
                <th>Last Seen</th>
            </tr>
        </thead>
        <tbody>
            {% for aircraft in aircrafts %}
            <tr>
                <td>{{ aircraft.callsign }}</td>
                <td>{{ aircraft.db_flags }}</td>
                <td>{{ aircraft.model }}</td>
                <td>{{ aircraft.latitude }}</td>
                <td>{{ aircraft.longitude }}</td>
                <td>{{ aircraft.altitude }}</td>
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

        aircrafts.forEach(function(aircraft) {
            if (aircraft.latitude && aircraft.longitude) {
                var marker = aircraft.is_helicopter
                    ? L.marker([aircraft.latitude, aircraft.longitude], { icon: helicopterIcon })
                    : L.marker([aircraft.latitude, aircraft.longitude]);
                marker.addTo(map).bindPopup(
                    `Callsign: ${aircraft.callsign}<br>Type: ${aircraft.model}<br>Altitude: ${aircraft.altitude} ft`
                );
            }
        });

        var bounds = aircrafts.map(a => [a.latitude, a.longitude]).filter(b => b[0] && b[1]);
        if (bounds.length > 0) {
            map.fitBounds(bounds);
        }
    </script>
</body>
</html>
'''
