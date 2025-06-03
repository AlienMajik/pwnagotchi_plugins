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
            <tr>
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
                <td>{{a.last_seen}}</td>
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

        aircrafts.forEach(function(ac) {
            if (ac.latitude && ac.longitude && ac.latitude != "N/A" && ac.longitude != "N/A") {
                var key = ac.is_military ? 'mil' :
                          ac.is_helicopter ? 'heli' :
                          ac.is_commercial_jet ? 'jet' :
                          ac.is_small_plane ? 'ga' :
                          ac.is_drone ? 'drone' :
                          ac.is_glider ? 'glider' : 'default';
                console.log(`Aircraft ${ac.icao24}: type key = ${key}`); // Debugging log
                var marker = L.marker([ac.latitude, ac.longitude], {icon: icons[key]}).addTo(map);
                marker.bindPopup(
                    `<b>${ac.callsign}</b> [${ac.model}]<br>
                     Reg: ${ac.registration}<br>
                     Alt: ${ac.baro_altitude} m<br>
                     Speed: ${ac.velocity} m/s<br>
                     Seen: ${ac.last_seen}`);
            }
        });
        var bounds = aircrafts.filter(a => a.latitude && a.longitude && a.latitude != "N/A" && a.longitude != "N/A")
            .map(a => [a.latitude, a.longitude]);
        if (bounds.length > 0) map.fitBounds(bounds);

        document.getElementById('filterForm').onsubmit = function(e) {
            e.preventDefault();
            var callsign = this.callsign.value.toLowerCase();
            var model = this.model.value.toLowerCase();
            var min_alt = parseFloat(this.min_alt.value) || -9999;
            var max_alt = parseFloat(this.max_alt.value) || 99999;
            var rows = document.querySelectorAll('#aircraftTable tbody tr');
            rows.forEach(function(row) {
                var tds = row.children;
                var c = tds[0].innerText.toLowerCase();
                var m = tds[1].innerText.toLowerCase();
                var a = parseFloat(tds[5].innerText) || 0;
                var show = (!callsign || c.includes(callsign)) && (!model || m.includes(model)) && a >= min_alt && a <= max_alt;
                row.style.display = show ? '' : 'none';
            });
        }
    </script>
</body>
</html>
'''

class SkyHigh(plugins.Plugin):
    __author__ = 'AlienMajik'
    __version__ = '1.1.1'
    __license__ = 'GPL3'
    __description__ = 'Advanced aircraft/ADS-B data plugin with robust type-detection, embedded SVG icons, filtering, export, and caching.'

    METADATA_CACHE_FILE = '/root/handshakes/skyhigh_metadata.json'

    def __init__(self):
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
        }
        self.last_fetch_time = 0
        self.data = {}
        self.data_lock = threading.Lock()
        self.metadata_cache = {}
        self.historical_positions = {}
        self.error_message = ""
        self.web_ui_last_update = ""
        self._stop_event = threading.Event()
        self.fetch_thread = None

    def on_loaded(self):
        logging.info("[SkyHigh] Plugin loaded.")
        os.makedirs(os.path.dirname(self.options['aircraft_file']), exist_ok=True)
        os.makedirs(os.path.dirname(self.METADATA_CACHE_FILE), exist_ok=True)
        self.load_metadata_cache()
        try:
            with open(self.options['aircraft_file'], 'r') as f:
                self.data = json.load(f)
        except Exception:
            self.data = {}
        self._stop_event.clear()
        self.fetch_thread = threading.Thread(target=self._fetch_loop, daemon=True)
        self.fetch_thread.start()

    def on_unload(self, ui):
        self._stop_event.set()
        if ui:
            with ui._lock:
                ui.remove_element('SkyHigh')
        self.save_metadata_cache()

    def on_ui_setup(self, ui):
        ui.add_element('SkyHigh', LabeledValue(
            color=BLACK,
            label='SkyHigh',
            value=" ",
            position=(self.options["adsb_x_coord"], self.options["adsb_y_coord"]),
            label_font=fonts.Small,
            text_font=fonts.Small
        ))

    def on_ui_update(self, ui):
        with self.data_lock:
            aircraft_count = len(self.data)
        ui.set('SkyHigh', f"{aircraft_count} aircraft (Last: {self.web_ui_last_update}){(' - ERROR: '+self.error_message) if self.error_message else ''}")

    def _fetch_loop(self):
        while not self._stop_event.is_set():
            try:
                self.fetch_aircraft_data()
                self.web_ui_last_update = datetime.now().strftime("%H:%M:%S")
                self.error_message = ""
            except Exception as e:
                self.error_message = str(e)
                logging.error(f"[SkyHigh] Background fetch error: {e}")
            time.sleep(self.options['timer'])

    def load_metadata_cache(self):
        try:
            with open(self.METADATA_CACHE_FILE, 'r') as f:
                self.metadata_cache = json.load(f)
        except Exception:
            self.metadata_cache = {}

    def save_metadata_cache(self):
        try:
            with open(self.METADATA_CACHE_FILE, 'w') as f:
                json.dump(self.metadata_cache, f)
        except Exception:
            pass

    def fetch_aircraft_data(self):
        lat, lon, radius = self._get_current_coords()
        lat_min, lat_max = lat - (radius / 69), lat + (radius / 69)
        lon_min, lon_max = lon - (radius / 69), lon + (radius / 69)
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
                    logging.error("[SkyHigh] API response missing 'states' key or is None.")
                    return "No aircraft data"
                logging.info(f"[SkyHigh] Sample Raw API Data: {json.dumps(api_data['states'][:2], indent=2)}")
                aircrafts = self._parse_and_store(api_data)
                self.prune_old_data()
                with self.data_lock:
                    with open(self.options['aircraft_file'], 'w') as f:
                        json.dump(self.data, f)
                return f"{len(aircrafts)} aircraft detected"
            elif response.status_code == 401:
                self.error_message = "OpenSky authentication failed."
                raise Exception("OpenSky authentication failed (401).")
            elif response.status_code == 429:
                self.error_message = "OpenSky rate-limited."
                raise Exception("OpenSky rate-limited (429).")
            else:
                raise Exception(f"OpenSky API error: {response.status_code}")
        except Exception as e:
            self.error_message = str(e)
            raise

    def _parse_and_store(self, api_data: Dict[str, Any]) -> List[Dict]:
        aircrafts = []
        blocklist = set(self.options.get('blocklist', []))
        allowlist = set(self.options.get('allowlist', []))
        if 'states' in api_data and api_data['states']:
            for state in api_data['states']:
                icao24 = state[0]
                if blocklist and icao24 in blocklist: continue
                if allowlist and icao24 not in allowlist: continue
                callsign = state[1].strip() if state[1] else "Unknown"
                lat = state[6] if state[6] is not None else 'N/A'
                lon = state[5] if state[5] is not None else 'N/A'
                baro_altitude = state[7] if state[7] is not None else 'N/A'
                velocity = state[9] if state[9] is not None else 'N/A'
                timestamp = state[4] if state[4] is not None else int(time.time())
                with self.data_lock:
                    if lat != 'N/A' and lon != 'N/A':
                        pos = {'timestamp': timestamp, 'latitude': lat, 'longitude': lon, 'baro_altitude': baro_altitude}
                        self.historical_positions.setdefault(icao24, []).append(pos)
                        self.historical_positions[icao24] = self.historical_positions[icao24][-10:]
                    meta = self.get_aircraft_metadata(icao24)
                    info = {
                        **meta,
                        'callsign': callsign,
                        'latitude': lat,
                        'longitude': lon,
                        'baro_altitude': baro_altitude,
                        'velocity': velocity,
                        'last_seen': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        'icao24': icao24
                    }
                    self.data[icao24] = info
                    aircrafts.append(info)
        return aircrafts

    def get_aircraft_metadata(self, icao24: str) -> Dict:
        if icao24 in self.metadata_cache:
            return self.metadata_cache[icao24]
        url = f"https://opensky-network.org/api/metadata/aircraft/icao/{icao24}"
        headers = {}
        try:
            if self.options['opensky_username'] and self.options['opensky_password']:
                import base64
                auth_str = f"{self.options['opensky_username']}:{self.options['opensky_password']}"
                auth_encoded = base64.b64encode(auth_str.encode()).decode()
                headers['Authorization'] = f'Basic {auth_encoded}'
                r = requests.get(url, headers=headers, timeout=10)
                if r.status_code == 401:
                    logging.warning("[SkyHigh] OpenSky credentials invalid. Attempting anonymous metadata fetch.")
                    r = requests.get(url, timeout=10)
            else:
                logging.warning("[SkyHigh] No OpenSky credentials. Attempting anonymous metadata fetch.")
                r = requests.get(url, timeout=10)
            if r.status_code == 200:
                d = r.json()
                manufacturer = d.get('manufacturerName', '') or ''
                model = d.get('model', 'Unknown') or 'Unknown'
                registration = d.get('registration', 'Unknown') or 'Unknown'
                db_flags = ', '.join([f.lower() for f in d.get('special_flags', []) if isinstance(f, str)])
                typecode = d.get('typecode', '') or ''
                
                logging.info(f"[SkyHigh] Metadata for {icao24}: Manufacturer={manufacturer}, Model={model}, Typecode={typecode}")

                manufacturer_lower = manufacturer.lower()
                model_lower = model.lower()
                typecode_lower = typecode.lower()

                is_helicopter = (
                    'helicopter' in model_lower or
                    model_lower.startswith('as') or
                    model_lower.startswith('ec')
                )
                is_commercial_jet = (
                    any(j in manufacturer_lower for j in ['airbus', 'boeing', 'embraer', 'bombardier']) or
                    any(model_lower.startswith(prefix) for prefix in [
                        'a', 'b', 'e', 'crj', 'erj',
                        '737', '747', '757', '767', '777', '787', '320', '319'
                    ]) or
                    any(typecode_lower.startswith(prefix) for prefix in [
                        'a', 'b', 'e', 'crj', 'erj',
                        '737', '747', '757', '767', '777', '787', '320', '319'
                    ])
                )
                is_small_plane = (
                    any(s in manufacturer_lower for s in ['cessna', 'piper', 'beechcraft', 'cirrus']) or
                    any(model_lower.startswith(prefix) for prefix in ['c', 'p', 'be', 'sr', 'u']) or
                    (len(model_lower) <= 4 and model_lower[0] in 'cpu')
                )
                is_drone = 'drone' in model_lower or 'uav' in model_lower or 'unmanned' in model_lower
                is_glider = 'glider' in model_lower or 'sailplane' in model_lower
                is_military = (
                    'military' in db_flags or
                    'military' in manufacturer_lower or
                    'military' in model_lower
                )

                meta = {
                    'model': model,
                    'registration': registration,
                    'db_flags': db_flags,
                    'is_helicopter': is_helicopter,
                    'is_commercial_jet': is_commercial_jet,
                    'is_small_plane': is_small_plane,
                    'is_drone': is_drone,
                    'is_glider': is_glider,
                    'is_military': is_military
                }

                logging.debug(f"[SkyHigh] Aircraft {icao24} type flags: {meta}")

                self.metadata_cache[icao24] = meta
                self.save_metadata_cache()
                return meta
            else:
                logging.warning(f"[SkyHigh] Failed to fetch metadata for {icao24}: {r.status_code}")
                return {
                    'model': 'Unknown',
                    'registration': 'Unknown',
                    'db_flags': '',
                    'is_helicopter': False,
                    'is_commercial_jet': False,
                    'is_small_plane': True,
                    'is_drone': False,
                    'is_glider': False,
                    'is_military': False
                }
        except Exception as e:
            logging.error(f"[SkyHigh] Exception fetching metadata for {icao24}: {e}")
            return {
                'model': 'Unknown',
                'registration': 'Unknown',
                'db_flags': '',
                'is_helicopter': False,
                'is_commercial_jet': False,
                'is_small_plane': True,
                'is_drone': False,
                'is_glider': False,
                'is_military': False
            }

    def prune_old_data(self):
        prune_minutes = self.options.get('prune_minutes', 5)
        now = datetime.now()
        cutoff = now - timedelta(minutes=prune_minutes)
        remove = []
        with self.data_lock:
            for icao24, info in self.data.items():
                try:
                    last_seen = datetime.strptime(info['last_seen'], '%Y-%m-%d %H:%M:%S')
                    if last_seen < cutoff:
                        remove.append(icao24)
                except Exception:
                    continue
            for icao24 in remove:
                self.data.pop(icao24, None)
                self.historical_positions.pop(icao24, None)

    def _get_current_coords(self):
        return self.options['latitude'], self.options['longitude'], self.options['radius']

    def on_webhook(self, path, req):
        if req.method == 'GET':
            if path == '/' or not path:
                with self.data_lock:
                    aircrafts = list(self.data.values())
                center = [self.options["latitude"], self.options["longitude"]]
                logging.debug(f"[SkyHigh] Sending {len(aircrafts)} aircraft to web interface")
                return render_template_string(HTML_TEMPLATE, aircrafts=aircrafts, center=center)
            elif path.startswith('export/csv'):
                return self.export_csv()
            elif path.startswith('export/kml'):
                return self.export_kml()
        return "Not found", 404

    def export_csv(self):
        import io
        import csv
        si = io.StringIO()
        cw = csv.writer(si)
        cw.writerow(['icao24', 'callsign', 'model', 'registration', 'latitude', 'longitude', 'altitude', 'velocity', 'type', 'last_seen'])
        with self.data_lock:
            for icao24, ac in self.data.items():
                t = ("Military" if ac.get('is_military') else
                     "Drone" if ac.get('is_drone') else
                     "Helicopter" if ac.get('is_helicopter') else
                     "Jet" if ac.get('is_commercial_jet') else
                     "GA" if ac.get('is_small_plane') else
                     "Glider" if ac.get('is_glider') else "Other")
                cw.writerow([icao24, ac.get('callsign'), ac.get('model'), ac.get('registration'),
                             ac.get('latitude'), ac.get('longitude'), ac.get('baro_altitude'),
                             ac.get('velocity'), t, ac.get('last_seen')])
        return Response(si.getvalue(), mimetype='text/csv',
                        headers={"Content-Disposition": "attachment;filename=skyhigh_aircraft.csv"})

    def export_kml(self):
        with self.data_lock:
            kml = ['<?xml version="1.0" encoding="UTF-8"?><kml xmlns="http://www.opengis.net/kml/2.2"><Document>']
            for ac in self.data.values():
                kml.append(f'''
                    <Placemark>
                        <name>{ac.get('callsign', '')}</name>
                        <description>Model:{ac.get('model', '')} Alt:{ac.get('baro_altitude', '')}m</description>
                        <Point><coordinates>{ac.get('longitude')},{ac.get('latitude')},0</coordinates></Point>
                    </Placemark>
                ''')
            kml.append('</Document></kml>')
        return Response(''.join(kml), mimetype='application/vnd.google-earth.kml+xml',
                        headers={"Content-Disposition": "attachment;filename=skyhigh_aircraft.kml"})
