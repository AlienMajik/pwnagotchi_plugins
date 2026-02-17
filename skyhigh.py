import logging
import os
import json
import time
import threading
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
import requests
from flask import render_template_string, request, Response

import pwnagotchi.plugins as plugins
import pwnagotchi.ui.fonts as fonts
from pwnagotchi.ui.components import LabeledValue
from pwnagotchi.ui.view import BLACK

# ---------------------------------------------------------------------
# HTML TEMPLATE (unchanged, includes type filter)
# ---------------------------------------------------------------------
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SkyHigh - Aircraft Map</title>
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    <style>
        body { font-family: Arial, sans-serif; margin: 10px; }
        h1 { margin-bottom: 10px; }
        .controls { margin-bottom: 8px; }
        table { width: 100%; border-collapse: collapse; font-size: 13px; }
        th, td { padding: 6px; text-align: left; border-bottom: 1px solid #ddd; }
        #map { height: 400px; margin-top: 10px; }
        @media (max-width:600px) {
            #map { height: 250px; }
            table, thead, tbody, th, td, tr { display: block; }
            tr { margin-bottom: 8px; }
        }
        .warn { color: red; font-weight: bold; }
    </style>
</head>
<body>
    <h1>SkyHigh: Aircraft Map</h1>
    <div class="controls">
        <form id="filterForm">
            Filter:
            <input type="text" name="callsign" placeholder="Callsign">
            <input type="text" name="model" placeholder="Model">
            Altitude: <input type="number" name="min_alt" placeholder="Min" style="width:70px">
            - <input type="number" name="max_alt" placeholder="Max" style="width:70px">
            <select name="type">
                <option value="">All types</option>
                <option value="mil">Military</option>
                <option value="heli">Helicopter</option>
                <option value="jet">Commercial Jet</option>
                <option value="ga">Small plane (GA)</option>
                <option value="drone">Drone</option>
                <option value="glider">Glider</option>
                <option value="other">Other</option>
            </select>
            <button type="submit">Apply</button>
            <a href="/plugins/skyhigh/export/csv" target="_blank">Export CSV</a>
            <a href="/plugins/skyhigh/export/kml" target="_blank">Export KML</a>
        </form>
        <span class="warn" id="warnMsg"></span>
    </div>
    <table id="aircraftTable">
        <thead>
            <tr>
                <th>Callsign</th>
                <th>Model</th>
                <th>Reg</th>
                <th>Lat</th>
                <th>Lon</th>
                <th>Alt</th>
                <th>Type</th>
                <th>Speed</th>
                <th>Last Seen</th>
            </tr>
        </thead>
        <tbody>
            {% for a in aircrafts %}
            <tr data-type="{{ a.type_key }}">
                <td>{{a.callsign}}</td>
                <td>{{a.model}}</td>
                <td>{{a.registration}}</td>
                <td>{{a.latitude}}</td>
                <td>{{a.longitude}}</td>
                <td>{{a.baro_altitude}}</td>
                <td>
                    {% if a.is_military %}Mil{% elif a.is_drone %}Drone
                    {% elif a.is_helicopter %}Heli{% elif a.is_commercial_jet %}Jet
                    {% elif a.is_small_plane %}GA{% elif a.is_glider %}Glider
                    {% else %}Other{% endif %}
                </td>
                <td>{{a.velocity}}</td>
                <td>{{a.last_seen_str}}</td>
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
        L.tileLayer('{{ tile_url }}', {
            attribution: '© OpenStreetMap contributors'
        }).addTo(map);

        var icons = {
            'mil': L.icon({
                iconUrl: 'data:image/svg+xml;base64,' + btoa(`
                    <svg xmlns="http://www.w3.org/2000/svg" width="30" height="30" viewBox="0 0 24 24" fill="green">
                        <path d="M12 2L2 7v10l10 5 10-5V7l-10-5zm0 2.83l6.56 3.28v6.88L12 18.17l-6.56-3.28V8.11L12 4.83zm-1 3.17v6h2v-6h-2z"/>
                    </svg>
                `),
                iconSize: [30, 30],
                iconAnchor: [15, 15],
                popupAnchor: [0, -15]
            }),
            'heli': L.icon({
                iconUrl: 'data:image/svg+xml;base64,' + btoa(`
                    <svg xmlns="http://www.w3.org/2000/svg" width="30" height="30" viewBox="0 0 24 24" fill="red">
                        <path d="M3 11h18v2H3v-2zm18 4H3v2h18v-2zm-1-9h-2V3H6v3H4v2h16V6zm-8 12h-2v3H8v-3H6v-2h6v2z"/>
                    </svg>
                `),
                iconSize: [30, 30],
                iconAnchor: [15, 15],
                popupAnchor: [0, -15]
            }),
            'jet': L.icon({
                iconUrl: 'data:image/svg+xml;base64,' + btoa(`
                    <svg xmlns="http://www.w3.org/2000/svg" width="30" height="30" viewBox="0 0 24 24" fill="blue">
                        <path d="M22 4h-2l-4 6h-4l-2-3H8l-2 3H2L0 4H0v16h2l2-3h4l2 3h2l2-3h4l4 3h2V4zm-8 12H8l-2 3H4l-2-3V6h2l2 3h4l2-3h4l-2 3h-2l-2-3h-2v10z"/>
                    </svg>
                `),
                iconSize: [30, 30],
                iconAnchor: [15, 15],
                popupAnchor: [0, -15]
            }),
            'ga': L.icon({
                iconUrl: 'data:image/svg+xml;base64,' + btoa(`
                    <svg xmlns="http://www.w3.org/2000/svg" width="30" height="30" viewBox="0 0 24 24" fill="yellow">
                        <path d="M20 4h-2l-3 5h-3l-2-3H8l-2 3H3l-3-5h-2v16h2l3-5h3l2 3h2l2-3h3l3 5h2V4zm-8 12H8l-2 3H4l-2-3V6h2l2 3h4l2-3h4l-2 3h-2l-2-3h-2v10z"/>
                    </svg>
                `),
                iconSize: [30, 30],
                iconAnchor: [15, 15],
                popupAnchor: [0, -15]
            }),
            'drone': L.icon({
                iconUrl: 'data:image/svg+xml;base64,' + btoa(`
                    <svg xmlns="http://www.w3.org/2000/svg" width="30" height="30" viewBox="0 0 24 24" fill="purple">
                        <path d="M12 2a10 10 0 00-8 4h4v4H4v4h4v4H2a10 10 0 0020 0h-6v-4h4v-4h-4V6h4a10 10 0 00-8-4zm0 2a8 8 0 016 3h-3v4h4v2h-4v4h3a8 8 0 01-12 0h3v-4H6v-2h4V6H7a8 8 0 015-3z"/>
                    </svg>
                `),
                iconSize: [30, 30],
                iconAnchor: [15, 15],
                popupAnchor: [0, -15]
            }),
            'glider': L.icon({
                iconUrl: 'data:image/svg+xml;base64,' + btoa(`
                    <svg xmlns="http://www.w3.org/2000/svg" width="30" height="30" viewBox="0 0 24 24" fill="orange">
                        <path d="M22 4l-9 5-9-5-1 2 9 5v9l-3-2v-5h-2v5l-3 2v2l5-2v-7l9-5 1-2zm-11 9h2v-2h-2v2z"/>
                    </svg>
                `),
                iconSize: [30, 30],
                iconAnchor: [15, 15],
                popupAnchor: [0, -15]
            }),
            'default': L.icon({
                iconUrl: 'data:image/svg+xml;base64,' + btoa(`
                    <svg xmlns="http://www.w3.org/2000/svg" width="30" height="30" viewBox="0 0 24 24" fill="gray">
                        <path d="M21 16v-2l-8-5V3.5a1.5 1.5 0 00-3 0V9l-8 5v2l8-2.5V19l-2 1.5V22l3.5-1 3.5 1v-1.5l-2-1.5v-5.5l8 2.5z"/>
                    </svg>
                `),
                iconSize: [30, 30],
                iconAnchor: [15, 15],
                popupAnchor: [0, -15]
            })
        };

        // Store markers for later filtering
        var markers = [];

        aircrafts.forEach(function(ac) {
            if (ac.latitude && ac.longitude && ac.latitude != "N/A" && ac.longitude != "N/A") {
                var key = ac.type_key || 'default';
                var marker = L.marker([ac.latitude, ac.longitude], {icon: icons[key]}).addTo(map);
                marker.bindPopup(
                    `<b>${ac.callsign}</b> [${ac.model}]<br>
                     Reg: ${ac.registration}<br>
                     Alt: ${ac.baro_altitude} m<br>
                     Speed: ${ac.velocity} m/s<br>
                     Seen: ${ac.last_seen_str}`);
                markers.push({ marker: marker, type: key, callsign: ac.callsign.toLowerCase(), model: ac.model.toLowerCase(), alt: parseFloat(ac.baro_altitude) || 0 });
            }
        });

        var bounds = markers.map(m => m.marker.getLatLng());
        if (bounds.length > 0) map.fitBounds(bounds);

        // Filtering logic for table and markers
        document.getElementById('filterForm').onsubmit = function(e) {
            e.preventDefault();
            var callsign = this.callsign.value.toLowerCase();
            var model = this.model.value.toLowerCase();
            var min_alt = parseFloat(this.min_alt.value) || -9999;
            var max_alt = parseFloat(this.max_alt.value) || 99999;
            var type = this.type.value;

            // Filter table rows
            var rows = document.querySelectorAll('#aircraftTable tbody tr');
            rows.forEach(function(row) {
                var tds = row.children;
                var c = tds[0].innerText.toLowerCase();
                var m = tds[1].innerText.toLowerCase();
                var a = parseFloat(tds[5].innerText) || 0;
                var rowType = row.dataset.type || '';
                var show = (!callsign || c.includes(callsign)) &&
                           (!model || m.includes(model)) &&
                           a >= min_alt && a <= max_alt &&
                           (!type || rowType === type);
                row.style.display = show ? '' : 'none';
            });

            // Filter map markers
            markers.forEach(function(item) {
                var show = (!callsign || item.callsign.includes(callsign)) &&
                           (!model || item.model.includes(model)) &&
                           item.alt >= min_alt && item.alt <= max_alt &&
                           (!type || item.type === type);
                if (show) {
                    if (!map.hasLayer(item.marker)) item.marker.addTo(map);
                } else {
                    if (map.hasLayer(item.marker)) map.removeLayer(item.marker);
                }
            });
        };
    </script>
</body>
</html>
'''

# ---------------------------------------------------------------------
# Classification patterns (used for type detection)
# ---------------------------------------------------------------------
TYPE_PATTERNS = {
    'helicopter': ['helicopter', 'as ', 'ec ', 'bell', 'robinson', 'airbus helicopter'],
    'commercial_jet': ['airbus', 'boeing', 'embraer', 'bombardier', 'a320', 'b737', 'b747', 'b757', 'b767', 'b777', 'b787', 'crj', 'erj'],
    'small_plane': ['cessna', 'piper', 'beechcraft', 'cirrus', 'diamond', 'mooney', 'c152', 'c172', 'pa28', 'sr22'],
    'drone': ['drone', 'uav', 'unmanned'],
    'glider': ['glider', 'sailplane', 'schleicher', 'ls4'],
    'military': ['military', 'fighter', 'c130', 'kc135', 'f16', 'f22', 'f35', 'c17', 'ah64', 'ch47']
}


class SkyHigh(plugins.Plugin):
    __author__ = 'AlienMajik (enhanced by community)'
    __version__ = '2.0.0'
    __license__ = 'GPL3'
    __description__ = 'Advanced aircraft/ADS‑B plugin with robust type detection, filtering, export, and caching.'

    METADATA_CACHE_FILE = '/root/handshakes/skyhigh_metadata.json'

    def __init__(self):
        # Default configuration (will be merged with user settings in on_loaded)
        self.options = {
            'timer': 60,
            'aircraft_file': '/root/handshakes/skyhigh_aircraft.json',
            'adsb_x_coord': 160,
            'adsb_y_coord': 80,
            'latitude': -66.273334,
            'longitude': 100.984166,
            'radius': 50,
            'prune_minutes': 5,
            'opensky_username': None,
            'opensky_password': None,
            'blocklist': [],
            'allowlist': [],
            'metadata_cache_expiry_days': 7,
            'disable_metadata': False,
            'map_tile_url': 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png'
        }
        self.last_fetch_time = 0
        self.data = {}               # icao24 -> aircraft info
        self.data_lock = threading.RLock()
        self.metadata_cache = {}      # icao24 -> metadata dict + timestamp
        self.metadata_lock = threading.RLock()
        self.historical_positions = {}
        self.error_message = ""
        self.web_ui_last_update = ""
        self._stop_event = threading.Event()
        self.fetch_thread = None

    # -----------------------------------------------------------------
    # Plugin lifecycle methods
    # -----------------------------------------------------------------
    def on_loaded(self):
        """Called when the plugin is loaded. Merge defaults with user config."""
        # Merge with defaults to guarantee all keys exist (safety net)
        defaults = {
            'timer': 60,
            'aircraft_file': '/root/handshakes/skyhigh_aircraft.json',
            'adsb_x_coord': 160,
            'adsb_y_coord': 80,
            'latitude': -66.273334,
            'longitude': 100.984166,
            'radius': 50,
            'prune_minutes': 5,
            'opensky_username': None,
            'opensky_password': None,
            'blocklist': [],
            'allowlist': [],
            'metadata_cache_expiry_days': 7,
            'disable_metadata': False,
            'map_tile_url': 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png'
        }
        self.options = {**defaults, **self.options}   # user values override defaults

        logging.info("[SkyHigh] Plugin loaded with options: %s", self.options)

        # Ensure necessary directories exist
        os.makedirs(os.path.dirname(self.options['aircraft_file']), exist_ok=True)
        os.makedirs(os.path.dirname(self.METADATA_CACHE_FILE), exist_ok=True)

        self.load_metadata_cache()
        self._load_data_file()

        self._stop_event.clear()
        self.fetch_thread = threading.Thread(target=self._fetch_loop, daemon=True)
        self.fetch_thread.start()

    def _load_data_file(self):
        """Load previously saved aircraft data from disk."""
        try:
            with open(self.options['aircraft_file'], 'r') as f:
                self.data = json.load(f)
        except Exception:
            self.data = {}

    def on_unload(self, ui):
        """Clean up when plugin is unloaded."""
        self._stop_event.set()
        if ui:
            with ui._lock:
                ui.remove_element('SkyHigh')
        self.save_metadata_cache()

    def on_ui_setup(self, ui):
        """Add the SkyHigh element to the display."""
        ui.add_element('SkyHigh', LabeledValue(
            color=BLACK,
            label='SkyHigh',
            value=" ",
            position=(self.options["adsb_x_coord"], self.options["adsb_y_coord"]),
            label_font=fonts.Small,
            text_font=fonts.Small
        ))

    def on_ui_update(self, ui):
        """Update the displayed aircraft count and error status."""
        with self.data_lock:
            aircraft_count = len(self.data)
        ui.set('SkyHigh', f"{aircraft_count} aircraft (Last: {self.web_ui_last_update}){(' - ERROR: '+self.error_message) if self.error_message else ''}")

    # -----------------------------------------------------------------
    # Background fetch loop
    # -----------------------------------------------------------------
    def _fetch_loop(self):
        """Background thread that periodically fetches new aircraft data."""
        while not self._stop_event.is_set():
            try:
                self.fetch_aircraft_data()
                self.web_ui_last_update = datetime.now().strftime("%H:%M:%S")
                self.error_message = ""
            except Exception as e:
                self.error_message = str(e)
                logging.error(f"[SkyHigh] Background fetch error: {e}")
            time.sleep(self.options['timer'])

    # -----------------------------------------------------------------
    # Metadata cache handling
    # -----------------------------------------------------------------
    def load_metadata_cache(self):
        """Load cached metadata from disk."""
        try:
            with open(self.METADATA_CACHE_FILE, 'r') as f:
                self.metadata_cache = json.load(f)
        except Exception:
            self.metadata_cache = {}

    def save_metadata_cache(self):
        """Save metadata cache to disk."""
        try:
            with open(self.METADATA_CACHE_FILE, 'w') as f:
                json.dump(self.metadata_cache, f)
        except Exception:
            pass

    def _is_metadata_expired(self, entry):
        """Check if a metadata cache entry is older than expiry_days."""
        expiry_days = self.options.get('metadata_cache_expiry_days', 7)
        if 'fetch_time' not in entry:
            return True
        fetch_time = datetime.fromtimestamp(entry['fetch_time'])
        return datetime.now() - fetch_time > timedelta(days=expiry_days)

    # -----------------------------------------------------------------
    # OpenSky API calls
    # -----------------------------------------------------------------
    def fetch_aircraft_data(self):
        """Fetch live aircraft positions from OpenSky Network."""
        lat, lon, radius = self._get_current_coords()
        # Approximate degree conversion (1 degree ≈ 69 miles)
        lat_min = lat - (radius / 69.0)
        lat_max = lat + (radius / 69.0)
        lon_min = lon - (radius / 69.0)
        lon_max = lon + (radius / 69.0)

        url = f"https://opensky-network.org/api/states/all?lamin={lat_min}&lomin={lon_min}&lamax={lat_max}&lomax={lon_max}"

        headers = {}
        if self.options['opensky_username'] and self.options['opensky_password']:
            import base64
            auth_str = f"{self.options['opensky_username']}:{self.options['opensky_password']}"
            auth_encoded = base64.b64encode(auth_str.encode()).decode()
            headers['Authorization'] = f'Basic {auth_encoded}'

        try:
            response = requests.get(url, headers=headers or None, timeout=15)
            if response.status_code == 200:
                api_data = response.json()
                if not api_data or 'states' not in api_data:
                    logging.error("[SkyHigh] API response missing 'states' key.")
                    return
                aircrafts = self._parse_and_store(api_data)
                self.prune_old_data()
                with self.data_lock:
                    with open(self.options['aircraft_file'], 'w') as f:
                        json.dump(self.data, f, indent=2)
                logging.info(f"[SkyHigh] Fetched {len(aircrafts)} aircraft")
            elif response.status_code == 401:
                self.error_message = "OpenSky authentication failed (401)."
                raise Exception("OpenSky authentication failed.")
            elif response.status_code == 429:
                self.error_message = "OpenSky rate-limited (429)."
                raise Exception("OpenSky rate-limited.")
            else:
                raise Exception(f"OpenSky API error: {response.status_code}")
        except Exception as e:
            self.error_message = str(e)
            raise

    def _parse_and_store(self, api_data: Dict[str, Any]) -> List[Dict]:
        """Convert OpenSky states to internal format and store in self.data."""
        aircrafts = []
        blocklist = set(self.options.get('blocklist', []))
        allowlist = set(self.options.get('allowlist', []))

        if 'states' not in api_data or not api_data['states']:
            return aircrafts

        for state in api_data['states']:
            icao24 = state[0]
            if blocklist and icao24 in blocklist:
                continue
            if allowlist and icao24 not in allowlist:
                continue

            callsign = state[1].strip() if state[1] else "Unknown"
            lat = state[6] if state[6] is not None else 'N/A'
            lon = state[5] if state[5] is not None else 'N/A'
            baro_altitude = state[7] if state[7] is not None else 'N/A'
            velocity = state[9] if state[9] is not None else 'N/A'
            last_contact = state[4] if state[4] is not None else int(time.time())   # epoch seconds

            # Store a short history of positions (optional)
            with self.data_lock:
                if lat != 'N/A' and lon != 'N/A':
                    pos = {
                        'timestamp': last_contact,
                        'latitude': lat,
                        'longitude': lon,
                        'baro_altitude': baro_altitude
                    }
                    self.historical_positions.setdefault(icao24, []).append(pos)
                    self.historical_positions[icao24] = self.historical_positions[icao24][-10:]

            # Get metadata (cached or fresh)
            if self.options.get('disable_metadata', False):
                meta = self._default_metadata()
            else:
                meta = self.get_aircraft_metadata(icao24)

            # Determine type key for web UI filtering
            type_key = self._get_type_key(meta)

            info = {
                **meta,
                'callsign': callsign,
                'latitude': lat,
                'longitude': lon,
                'baro_altitude': baro_altitude,
                'velocity': velocity,
                'last_contact': last_contact,                # epoch for pruning
                'last_seen_str': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),  # human friendly
                'icao24': icao24,
                'type_key': type_key
            }
            with self.data_lock:
                self.data[icao24] = info
            aircrafts.append(info)

        return aircrafts

    def _get_type_key(self, meta: Dict) -> str:
        """Return a short string key for the aircraft type (used in web UI)."""
        if meta.get('is_military'):
            return 'mil'
        if meta.get('is_helicopter'):
            return 'heli'
        if meta.get('is_commercial_jet'):
            return 'jet'
        if meta.get('is_small_plane'):
            return 'ga'
        if meta.get('is_drone'):
            return 'drone'
        if meta.get('is_glider'):
            return 'glider'
        return 'other'

    def _default_metadata(self):
        """Return a default metadata dict (used when metadata fetching is disabled or fails)."""
        return {
            'model': 'Unknown',
            'registration': 'Unknown',
            'db_flags': '',
            'is_helicopter': False,
            'is_commercial_jet': False,
            'is_small_plane': True,    # fallback to GA
            'is_drone': False,
            'is_glider': False,
            'is_military': False
        }

    def get_aircraft_metadata(self, icao24: str) -> Dict:
        """Fetch metadata from OpenSky, with caching and expiry."""
        with self.metadata_lock:
            # Return cached if exists and not expired
            if icao24 in self.metadata_cache:
                entry = self.metadata_cache[icao24]
                if not self._is_metadata_expired(entry):
                    return entry['data']
                else:
                    logging.debug(f"[SkyHigh] Metadata for {icao24} expired, refreshing.")

        # Fetch fresh metadata
        url = f"https://opensky-network.org/api/metadata/aircraft/icao/{icao24}"
        headers = {}
        if self.options['opensky_username'] and self.options['opensky_password']:
            import base64
            auth_str = f"{self.options['opensky_username']}:{self.options['opensky_password']}"
            auth_encoded = base64.b64encode(auth_str.encode()).decode()
            headers['Authorization'] = f'Basic {auth_encoded}'

        try:
            r = requests.get(url, headers=headers or None, timeout=10)
            if r.status_code == 401:
                logging.warning("[SkyHigh] OpenSky credentials invalid, retrying anonymously.")
                r = requests.get(url, timeout=10)   # anonymous retry
            if r.status_code == 200:
                d = r.json()
                meta = self._classify_from_metadata(d)
                # Store with timestamp
                with self.metadata_lock:
                    self.metadata_cache[icao24] = {
                        'data': meta,
                        'fetch_time': time.time()
                    }
                self.save_metadata_cache()
                return meta
            else:
                logging.warning(f"[SkyHigh] Metadata fetch for {icao24} failed: {r.status_code}")
        except Exception as e:
            logging.error(f"[SkyHigh] Exception fetching metadata for {icao24}: {e}")

        # Return cached if available (even if expired) as fallback
        with self.metadata_lock:
            if icao24 in self.metadata_cache:
                return self.metadata_cache[icao24]['data']
        return self._default_metadata()

    def _classify_from_metadata(self, md: Dict) -> Dict:
        """Classify aircraft type using pattern matching on manufacturer/model/typecode."""
        manufacturer = (md.get('manufacturerName') or '').lower()
        model = (md.get('model') or '').lower()
        typecode = (md.get('typecode') or '').lower()
        db_flags = ' '.join([f.lower() for f in md.get('special_flags', []) if isinstance(f, str)])

        # Helper to check patterns
        def matches(patterns, text):
            return any(p in text for p in patterns)

        is_military = (matches(TYPE_PATTERNS['military'], manufacturer) or
                       matches(TYPE_PATTERNS['military'], model) or
                       matches(TYPE_PATTERNS['military'], typecode) or
                       'military' in db_flags)

        is_helicopter = matches(TYPE_PATTERNS['helicopter'], model) or matches(TYPE_PATTERNS['helicopter'], typecode)
        is_commercial_jet = matches(TYPE_PATTERNS['commercial_jet'], manufacturer) or \
                            matches(TYPE_PATTERNS['commercial_jet'], model) or \
                            matches(TYPE_PATTERNS['commercial_jet'], typecode)
        is_small_plane = matches(TYPE_PATTERNS['small_plane'], manufacturer) or \
                         matches(TYPE_PATTERNS['small_plane'], model) or \
                         matches(TYPE_PATTERNS['small_plane'], typecode)
        is_drone = matches(TYPE_PATTERNS['drone'], model) or matches(TYPE_PATTERNS['drone'], typecode)
        is_glider = matches(TYPE_PATTERNS['glider'], model) or matches(TYPE_PATTERNS['glider'], typecode)

        return {
            'model': md.get('model', 'Unknown'),
            'registration': md.get('registration', 'Unknown'),
            'db_flags': ', '.join(md.get('special_flags', [])),
            'is_military': is_military,
            'is_helicopter': is_helicopter,
            'is_commercial_jet': is_commercial_jet,
            'is_small_plane': is_small_plane,
            'is_drone': is_drone,
            'is_glider': is_glider
        }

    def prune_old_data(self):
        """Remove aircraft that haven't been seen for prune_minutes."""
        prune_minutes = self.options.get('prune_minutes', 5)
        now_epoch = time.time()
        cutoff = now_epoch - (prune_minutes * 60)

        remove = []
        with self.data_lock:
            for icao24, info in self.data.items():
                last = info.get('last_contact', 0)
                if last < cutoff:
                    remove.append(icao24)
            for icao24 in remove:
                self.data.pop(icao24, None)
                self.historical_positions.pop(icao24, None)
        if remove:
            logging.debug(f"[SkyHigh] Pruned {len(remove)} old aircraft.")

    def _get_current_coords(self):
        """Return the current center coordinates and radius from config."""
        return (self.options['latitude'],
                self.options['longitude'],
                self.options['radius'])

    # -----------------------------------------------------------------
    # Web UI endpoints
    # -----------------------------------------------------------------
    def on_webhook(self, path, req):
        """Handle web requests for the map view and exports."""
        if req.method == 'GET':
            if path == '/' or not path:
                with self.data_lock:
                    # Convert to list and ensure type_key exists
                    aircrafts = []
                    for ac in self.data.values():
                        ac_copy = ac.copy()
                        if 'type_key' not in ac_copy:
                            ac_copy['type_key'] = self._get_type_key(ac_copy)
                        aircrafts.append(ac_copy)
                center = [self.options["latitude"], self.options["longitude"]]
                tile_url = self.options.get('map_tile_url', 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png')
                return render_template_string(HTML_TEMPLATE,
                                              aircrafts=aircrafts,
                                              center=center,
                                              tile_url=tile_url)
            elif path == 'export/csv':
                return self.export_csv()
            elif path == 'export/kml':
                return self.export_kml()
        return "Not found", 404

    def export_csv(self):
        """Generate a CSV file with current aircraft data."""
        import io
        import csv
        si = io.StringIO()
        cw = csv.writer(si)
        cw.writerow(['icao24', 'callsign', 'model', 'registration', 'latitude', 'longitude',
                     'altitude', 'velocity', 'type', 'last_seen'])

        with self.data_lock:
            for icao24, ac in self.data.items():
                # Skip entries with invalid coordinates
                lat = ac.get('latitude')
                lon = ac.get('longitude')
                if lat in (None, 'N/A') or lon in (None, 'N/A'):
                    continue
                t = ("Military" if ac.get('is_military') else
                     "Drone" if ac.get('is_drone') else
                     "Helicopter" if ac.get('is_helicopter') else
                     "Jet" if ac.get('is_commercial_jet') else
                     "GA" if ac.get('is_small_plane') else
                     "Glider" if ac.get('is_glider') else "Other")
                cw.writerow([icao24, ac.get('callsign'), ac.get('model'), ac.get('registration'),
                             lat, lon, ac.get('baro_altitude'),
                             ac.get('velocity'), t, ac.get('last_seen_str')])

        return Response(si.getvalue(),
                        mimetype='text/csv',
                        headers={"Content-Disposition": "attachment;filename=skyhigh_aircraft.csv"})

    def export_kml(self):
        """Generate a KML file with current aircraft data."""
        kml = ['<?xml version="1.0" encoding="UTF-8"?>',
               '<kml xmlns="http://www.opengis.net/kml/2.2">',
               '<Document>']

        with self.data_lock:
            for ac in self.data.values():
                lat = ac.get('latitude')
                lon = ac.get('longitude')
                if lat in (None, 'N/A') or lon in (None, 'N/A'):
                    continue
                name = ac.get('callsign', 'Unknown')
                desc = f"Model: {ac.get('model', '')} Alt: {ac.get('baro_altitude', '')}m"
                kml.append(f'''
                    <Placemark>
                        <name>{name}</name>
                        <description>{desc}</description>
                        <Point><coordinates>{lon},{lat},0</coordinates></Point>
                    </Placemark>
                ''')

        kml.append('</Document></kml>')
        return Response(''.join(kml),
                        mimetype='application/vnd.google-earth.kml+xml',
                        headers={"Content-Disposition": "attachment;filename=skyhigh_aircraft.kml"})
