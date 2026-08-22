#!/usr/bin/env python3
"""
SkyHigh — nearby aircraft (ADS-B) tracking for Pwnagotchi.

Fetches live aircraft state vectors from the OpenSky Network, shows the count on
the Pwnagotchi screen, and serves a live map + flight-strip board at
/plugins/skyhigh/.

Data provided by the OpenSky Network (https://opensky-network.org).
This plugin is not affiliated with OpenSky Network.
"""

import base64
import csv
import io
import json
import logging
import math
import os
import re
import threading
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from xml.sax.saxutils import escape as xml_escape

import requests

from flask import Response

import pwnagotchi.plugins as plugins
import pwnagotchi.ui.fonts as fonts
from pwnagotchi.ui.components import LabeledValue
from pwnagotchi.ui.view import BLACK

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

STATES_URL = "https://opensky-network.org/api/states/all"
OPENSKY_META_URL = "https://opensky-network.org/api/metadata/aircraft/icao/{icao}"
ADSBDB_META_URL = "https://api.adsbdb.com/v0/aircraft/{icao}"
TOKEN_URL = ("https://auth.opensky-network.org/auth/realms/opensky-network/"
             "protocol/openid-connect/token")

USER_AGENT = "pwnagotchi-skyhigh/2.2.0 (+https://github.com/AlienMajik/pwnagotchi_plugins)"

MILES_PER_DEG_LAT = 69.0
EARTH_RADIUS_MI = 3958.8

EMERGENCY_SQUAWKS = {
    "7500": "HIJACK",
    "7600": "NO RADIO",
    "7700": "EMERGENCY",
}

# ADS-B emitter category (state vector index 17, only sent when the request
# asks for extended=1). The aircraft broadcasts this itself, so it works with
# no registry lookup at all — which matters because OpenSky's metadata endpoint
# is unreliable and often gone entirely.
CATEGORY_TYPE = {
    2: "ga",        # light, under 15 500 lb
    3: "ga",        # small
    4: "jet",       # large
    5: "jet",       # high vortex large
    6: "jet",       # heavy
    7: "mil",       # high performance (>5g, >400 kt) — civil traffic never sets this
    8: "heli",      # rotorcraft
    9: "glider",
    12: "ga",       # ultralight / hang-glider / paraglider
    14: "drone",    # UAV
}

CATEGORY_LABEL = {
    0: "", 1: "no info", 2: "light", 3: "small", 4: "large",
    5: "high vortex", 6: "heavy", 7: "high performance", 8: "rotorcraft",
    9: "glider", 10: "lighter-than-air", 11: "parachutist", 12: "ultralight",
    13: "reserved", 14: "UAV", 15: "space vehicle", 16: "emergency vehicle",
    17: "service vehicle", 18: "obstacle", 19: "obstacle", 20: "obstacle",
}

DEFAULTS: Dict[str, Any] = {
    # polling
    "timer": 120,                       # seconds between state fetches
    "enforce_rate_limit": True,         # clamp timer to a sane floor for the API tier
    "request_timeout": 20,

    # location
    "latitude": 37.717683,              # fallback when no GPS fix
    "longitude": -122.439393,
    "radius": 50,                       # miles
    "use_gps": True,
    "gps_max_age": 300,                 # seconds a GPS fix stays trusted

    # storage
    "aircraft_file": "/root/handshakes/skyhigh_aircraft.json",
    "metadata_file": "/root/handshakes/skyhigh_metadata.json",
    "stats_file": "/root/handshakes/skyhigh_stats.json",
    "persist_aircraft": True,

    # screen
    "adsb_x_coord": 160,
    "adsb_y_coord": 80,
    "ui_verbose": False,                # append last-update time on screen

    # data hygiene
    "prune_minutes": 5,                 # 0 disables pruning
    "history_points": 10,               # trail points kept per aircraft
    "max_tracked": 500,                 # hard cap on tracked aircraft

    # filters
    "blocklist": [],
    "allowlist": [],
    "min_altitude": None,               # metres, drops anything lower
    "ignore_on_ground": False,
    "trim_to_radius": True,             # discard the box corners outside radius

    # credentials
    "opensky_client_id": None,          # OAuth2 (current OpenSky auth)
    "opensky_client_secret": None,
    "opensky_username": None,           # legacy basic auth
    "opensky_password": None,

    # metadata enrichment
    "disable_metadata": False,
    "metadata_source": "auto",          # auto | opensky | adsbdb | none
    "metadata_cache_expiry_days": 30,
    "metadata_negative_cache_hours": 24,
    "max_metadata_fetches_per_cycle": 8,
    "military_callsign_heuristic": True,

    # web ui
    "map_tile_url": "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
    "map_attribution": "&copy; OpenStreetMap contributors",
    "units": "metric",                  # metric | imperial
    "web_refresh": 0,                   # 0 = follow the fetch timer
}

NUMERIC_INT = ("timer", "adsb_x_coord", "adsb_y_coord", "prune_minutes",
               "history_points", "max_tracked", "max_metadata_fetches_per_cycle",
               "metadata_cache_expiry_days", "metadata_negative_cache_hours",
               "request_timeout", "gps_max_age", "web_refresh")
NUMERIC_FLOAT = ("latitude", "longitude", "radius")
BOOLS = ("use_gps", "persist_aircraft", "disable_metadata", "ui_verbose",
         "enforce_rate_limit", "ignore_on_ground", "military_callsign_heuristic",
         "trim_to_radius")

# --- classification -------------------------------------------------------
# Word-boundary patterns, so "atlas air" no longer matches the helicopter
# pattern "as ", which was a frequent misclassification in 2.0.0.

TYPE_PATTERNS = {
    "heli": [r"\bhelicopters?\b", r"\bbell\b", r"\brobinson\b", r"\bsikorsky\b",
             r"\bagusta\b", r"\beurocopter\b", r"\bschweizer\b", r"\benstrom\b",
             r"\bkamov\b", r"\bmil mi-?\d", r"\bmd helicopters\b", r"\bguimbal\b"],
    "jet": [r"\bairbus\b", r"\bboeing\b", r"\bembraer\b", r"\bbombardier\b",
            r"\bmcdonnell\b", r"\bdouglas\b", r"\bfokker\b", r"\bsukhoi\b",
            r"\btupolev\b", r"\bcomac\b", r"\bavro\b", r"\bcanadair\b", r"\batr\b"],
    "ga": [r"\bcessna\b", r"\bpiper\b", r"\bbeech(craft)?\b", r"\bcirrus\b",
           r"\bdiamond\b", r"\bmooney\b", r"\bsocata\b", r"\bvans\b", r"\bpilatus\b",
           r"\bgrumman\b", r"\bmaule\b", r"\baviat\b", r"\bicon\b"],
    "drone": [r"\bdrones?\b", r"\buav\b", r"\bunmanned\b", r"\bgeneral atomics\b",
              r"\bpredator\b", r"\breaper\b"],
    "glider": [r"\bglider\b", r"\bsailplane\b", r"\bschleicher\b", r"\bschempp\b",
               r"\bgrob\b", r"\bszd\b", r"\bpipistrel\b"],
    "mil": [r"\bmilitary\b", r"\bair force\b", r"\bnavy\b", r"\barmy\b",
            r"\blockheed\b", r"\bnorthrop\b", r"\bfighter\b", r"\bmarine corps\b"],
}
TYPE_RE = {k: [re.compile(p) for p in v] for k, v in TYPE_PATTERNS.items()}

# Exact ICAO typecodes are far more reliable than free-text model strings.
HELI_TYPECODES = {
    "A109", "A119", "A139", "A149", "A169", "A189", "AS32", "AS3B", "AS50",
    "AS55", "AS65", "B06", "B06T", "B222", "B230", "B407", "B412", "B429",
    "B430", "B505", "BK17", "EC20", "EC25", "EC30", "EC35", "EC45", "EC55",
    "EC75", "EH10", "EXPL", "GAZL", "H125", "H130", "H135", "H145", "H155",
    "H160", "H175", "H500", "H60", "AH64", "CH47", "UH1", "KA32", "LYNX",
    "MI8", "MI17", "MI24", "NH90", "R22", "R44", "R66", "S61", "S64", "S76",
    "S92", "SW4", "V22",
}
GLIDER_TYPECODES = {
    "AS21", "AS25", "AS33", "ARCP", "DG40", "DG80", "DISC", "DUOD", "G103",
    "JS1", "LS4", "LS8", "NIMB", "SZD5", "VENT", "TWIN", "ASW2",
}
DRONE_TYPECODES = {"MQ9", "MQ1", "RQ4", "MQ4", "Q4", "GHWK"}
MIL_TYPECODES = {
    "A400", "AV8B", "B1", "B2", "B52", "C130", "C17", "C30J", "C5M", "E3TF",
    "E3CF", "E6", "E8", "EUFI", "F15", "F16", "F18", "F22", "F35", "GLF5",
    "H60", "K35R", "KC10", "KC30", "P8", "R135", "RC12", "T38", "T6", "U2",
    "AH64", "CH47", "V22", "C27J", "C295", "C160", "TOR", "RFAL", "GR4",
}
JET_TYPECODE_RE = re.compile(
    r"^(A2\d\d|A3\d\d|A19N|A20N|A21N|B7\d\d|B37M|B38M|B39M|B3XM|BCS[13]|"
    r"CRJ\d|CL\d\d|E1\d\d|E7\d\d|E29\d|E55P|E135|E145|E170|E175|E190|E195|"
    r"MD8\d|MD9\d|MD11|F70|F100|GLEX|GL\d\d|GLF\d|C25\d|C5\d\d|C6\d\d|C7\d\d|"
    r"LJ\d\d|PC24|HDJT|FA\d\d|SU95|RJ\d\d|A748)$"
)
GA_TYPECODE_RE = re.compile(
    r"^(C1\d\d|C2\d\d|C3\d\d|C4\d\d|P2\d\d|PA\d\d|P28[A-Z]|P32[A-Z]|P46[A-Z]|"
    r"SR2\d|SR22|DA\d\d|BE\d\d|B\d\dP|M20[A-Z]|TB\d\d|RV\d|AA5|GA8|AT\d\d|"
    r"PC12|PC6T|TBM[789]|C82[RS]|DHC2|DR40|F406|EV97|CH70|S22T)$"
)
# Conservative: only used when no database match exists.
MIL_CALLSIGN_PREFIXES = (
    "RCH", "REACH", "CNV", "RRR", "ASCOT", "DOOM", "SNTRY", "FORTE", "HOMER",
    "EVAC", "PAT", "NAVY", "ARMY", "NATO", "JOLLY", "PEDRO", "HOIST", "TITAN",
    "MAGMA", "VADER", "GRZLY", "BLKCT", "LAGR", "TREK", "SPAR", "CFC", "IAM",
)
MIL_CALLSIGN_RE = re.compile(r"^(%s)\d" % "|".join(MIL_CALLSIGN_PREFIXES))

TYPE_LABELS = {
    "mil": "Military", "heli": "Helicopter", "jet": "Jet",
    "ga": "Light", "drone": "Drone", "glider": "Glider", "other": "Unknown",
}


class OpenSkyError(Exception):
    """Any non-recoverable-this-cycle API problem."""


class RateLimited(OpenSkyError):
    def __init__(self, msg, retry_after=None):
        super().__init__(msg)
        self.retry_after = retry_after


# ---------------------------------------------------------------------------
# Web UI
# ---------------------------------------------------------------------------
# Rendered by string substitution rather than Jinja: aircraft data is never
# interpolated into markup server-side, it arrives as JSON and is written with
# textContent, so a hostile callsign cannot inject script.

HTML_PAGE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>SkyHigh</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
<style>
:root{
  --panel:#111820; --panel-2:#18222d; --edge:#243240; --edge-soft:#1c2734;
  --ink:#e8eef4; --ink-dim:#8ea3b6; --ink-faint:#5d7285;
  --amber:#ffb43a; --amber-dim:#7a5518;
  --mil:#5ad18a; --heli:#ff6b6b; --jet:#5aa9ff; --ga:#ffd453;
  --drone:#c08cff; --glider:#ff9d5c; --other:#8ea3b6;
  --alarm:#ff4d4d;
  --mono:ui-monospace,"SF Mono","JetBrains Mono",Menlo,Consolas,"Liberation Mono",monospace;
  --sans:system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;
}
@media (prefers-color-scheme: light){
  :root{
    --panel:#eef2f6; --panel-2:#ffffff; --edge:#c8d4de; --edge-soft:#dde5ec;
    --ink:#16212b; --ink-dim:#4b5f70; --ink-faint:#7e91a1;
    --amber:#a35c00; --amber-dim:#e6c99a;
    --mil:#0f8a4d; --heli:#c62828; --jet:#1565c0; --ga:#9a7500;
    --drone:#6a35b8; --glider:#c2571a; --other:#5b6f80;
  }
}
*{box-sizing:border-box}
body{margin:0;background:var(--panel);color:var(--ink);font-family:var(--sans);
     font-size:14px;line-height:1.45}
.wrap{max-width:1180px;margin:0 auto;padding:14px}
header{display:flex;flex-wrap:wrap;align-items:baseline;gap:12px;
       border-bottom:1px solid var(--edge);padding-bottom:10px}
h1{font-family:var(--mono);font-size:17px;font-weight:600;letter-spacing:.16em;
   text-transform:uppercase;margin:0;color:var(--amber)}
h1 span{color:var(--ink-faint)}
.status{font-family:var(--mono);font-size:11.5px;color:var(--ink-dim);
        letter-spacing:.06em;display:flex;align-items:center;gap:6px}
.dot{width:7px;height:7px;border-radius:50%;background:var(--ink-faint);flex:none}
.dot.live{background:var(--mil);box-shadow:0 0 0 3px rgba(90,209,138,.18)}
.dot.err{background:var(--alarm);box-shadow:0 0 0 3px rgba(255,77,77,.18)}
.spacer{flex:1}
.err-bar{display:none;margin-top:10px;padding:8px 10px;border-left:3px solid var(--alarm);
         background:var(--panel-2);font-family:var(--mono);font-size:12px}
.tally{display:flex;flex-wrap:wrap;gap:6px;margin:12px 0}
.chip{font-family:var(--mono);font-size:11.5px;letter-spacing:.05em;padding:4px 9px;
      border:1px solid var(--edge);border-radius:2px;background:var(--panel-2);
      color:var(--ink-dim);cursor:pointer;user-select:none}
.chip b{color:var(--ink);font-weight:600}
.chip[aria-pressed="true"]{border-color:var(--amber);color:var(--ink)}
.chip:focus-visible{outline:2px solid var(--amber);outline-offset:2px}
.controls{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin-bottom:10px}
input,select,button,a.btn{font-family:var(--mono);font-size:12px;color:var(--ink);
  background:var(--panel-2);border:1px solid var(--edge);border-radius:2px;padding:6px 8px}
input::placeholder{color:var(--ink-faint)}
input:focus,select:focus,button:focus-visible,a.btn:focus-visible{
  outline:2px solid var(--amber);outline-offset:1px}
a.btn{text-decoration:none;color:var(--ink-dim)}
a.btn:hover,button:hover{border-color:var(--amber)}
button{cursor:pointer}
label.toggle{font-family:var(--mono);font-size:11.5px;color:var(--ink-dim);
             display:flex;align-items:center;gap:5px;cursor:pointer}
#map{height:420px;border:1px solid var(--edge);background:var(--panel-2)}
#mapnote{display:none;padding:10px;border:1px solid var(--edge);background:var(--panel-2);
         font-family:var(--mono);font-size:12px;color:var(--ink-dim)}
.board{margin-top:14px;border-top:1px solid var(--edge)}
.head,.strip{display:grid;grid-template-columns:4px 92px 1fr 78px 74px 74px 66px 84px;
             gap:10px;align-items:center}
.head{font-family:var(--mono);font-size:10.5px;letter-spacing:.12em;text-transform:uppercase;
      color:var(--ink-faint);padding:8px 8px;border-bottom:1px solid var(--edge)}
.head span{cursor:pointer}
.head span:hover{color:var(--amber)}
.head .arrow{color:var(--amber)}
.strip{padding:7px 8px;border-bottom:1px solid var(--edge-soft);cursor:pointer;
       font-family:var(--mono);font-size:12.5px}
.strip:hover{background:var(--panel-2)}
.strip.sel{background:var(--panel-2);box-shadow:inset 0 0 0 1px var(--amber-dim)}
.band{height:22px;border-radius:1px;background:var(--other)}
.band.mil{background:var(--mil)}.band.heli{background:var(--heli)}
.band.jet{background:var(--jet)}.band.ga{background:var(--ga)}
.band.drone{background:var(--drone)}.band.glider{background:var(--glider)}
.cs{font-weight:600;letter-spacing:.04em}
.model{color:var(--ink-dim);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.model em{font-style:normal;color:var(--ink-faint)}
.num{text-align:right;font-variant-numeric:tabular-nums}
.num.dim{color:var(--ink-dim)}
.tag{font-size:10px;letter-spacing:.1em;color:var(--ink-faint);text-transform:uppercase}
.sq{color:var(--alarm);font-weight:700}
.strip.alarm{box-shadow:inset 3px 0 0 var(--alarm)}
.empty{padding:26px 8px;color:var(--ink-faint);font-family:var(--mono);font-size:12.5px}
footer{margin:18px 0 8px;padding-top:10px;border-top:1px solid var(--edge);
        font-family:var(--mono);font-size:11px;color:var(--ink-faint)}
footer a{color:var(--ink-dim)}
.ac-icon svg{display:block;filter:drop-shadow(0 0 2px rgba(0,0,0,.55))}
.leaflet-popup-content{font-family:var(--mono);font-size:12px}
@media (max-width:860px){
  .head{display:none}
  .strip{grid-template-columns:4px 1fr 1fr;grid-auto-rows:min-content;
         row-gap:2px;padding:9px 8px}
  .band{grid-row:span 3;height:100%;min-height:40px}
  .model{grid-column:span 2}
  .num{text-align:left}
  #map{height:300px}
}
@media (prefers-reduced-motion:reduce){*{transition:none!important;animation:none!important}}
</style>
</head>
<body>
<div class="wrap">
  <header>
    <h1>SkyHigh<span>/adsb</span></h1>
    <div class="status"><i class="dot" id="dot"></i><span id="stat">connecting</span></div>
    <div class="spacer"></div>
    <div class="status" id="clock"></div>
  </header>
  <div class="err-bar" id="errbar"></div>

  <div class="tally" id="tally"></div>

  <div class="controls">
    <input id="q" placeholder="callsign / reg / model" size="22" autocomplete="off">
    <input id="minalt" class="num" type="number" placeholder="min alt" style="width:92px">
    <input id="maxalt" class="num" type="number" placeholder="max alt" style="width:92px">
    <button id="clear" type="button">Clear filters</button>
    <label class="toggle"><input type="checkbox" id="trails"> Trails</label>
    <label class="toggle"><input type="checkbox" id="follow" checked> Auto-refresh</label>
    <div class="spacer"></div>
    <a class="btn" href="/plugins/skyhigh/export/csv">CSV</a>
    <a class="btn" href="/plugins/skyhigh/export/kml">KML</a>
    <a class="btn" href="/plugins/skyhigh/export/gpx">GPX</a>
    <a class="btn" href="/plugins/skyhigh/data.json">JSON</a>
  </div>

  <div id="map"></div>
  <div id="mapnote">Map tiles are unavailable — the device has no route to the tile
    server. The board below still updates.</div>

  <div class="board">
    <div class="head" id="head">
      <span></span>
      <span data-k="callsign">Callsign</span>
      <span data-k="model">Type</span>
      <span data-k="altitude" class="num">Alt</span>
      <span data-k="velocity" class="num">Speed</span>
      <span data-k="distance" class="num">Range</span>
      <span data-k="track" class="num">Trk</span>
      <span data-k="age" class="num">Seen</span>
    </div>
    <div id="strips"></div>
  </div>

  <footer>
    Aircraft data from the <a href="https://opensky-network.org" target="_blank"
    rel="noreferrer noopener">OpenSky Network</a>. Positions are as reported by
    each aircraft and may lag by a few seconds.
  </footer>
</div>

<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script>
(function(){
"use strict";
var CFG = __CONFIG__;
var UNITS = CFG.units === "imperial"
  ? {alt:{f:function(m){return m*3.28084},s:"ft"}, spd:{f:function(v){return v*1.94384},s:"kt"},
     dst:{f:function(d){return d},s:"mi"}}
  : {alt:{f:function(m){return m},s:"m"}, spd:{f:function(v){return v*3.6},s:"km/h"},
     dst:{f:function(d){return d*1.609344},s:"km"}};

var TYPES = ["mil","heli","jet","ga","drone","glider","other"];
var LABEL = {mil:"MIL",heli:"HELI",jet:"JET",ga:"LIGHT",drone:"UAV",glider:"GLIDER",other:"UNKN"};
var COLOR = {};
var cs = getComputedStyle(document.documentElement);
TYPES.forEach(function(t){ COLOR[t] = cs.getPropertyValue("--"+t).trim() || "#888"; });

var state = {ac:[], sort:"distance", dir:1, sel:null, types:{}, timer:null};
var map=null, acLayer=null, trailLayer=null, marks={};

var $ = function(id){ return document.getElementById(id); };

/* ---------- map ---------- */
function initMap(){
  if (typeof L === "undefined"){
    $("map").style.display="none"; $("mapnote").style.display="block"; return;
  }
  map = L.map("map",{zoomControl:true}).setView(CFG.center, 9);
  L.tileLayer(CFG.tile_url,{attribution:CFG.attribution,maxZoom:18}).addTo(map);
  acLayer = L.layerGroup().addTo(map);
  trailLayer = L.layerGroup().addTo(map);
  L.circle(CFG.center,{radius:CFG.radius_mi*1609.34,color:"#ffb43a",weight:1,
    opacity:.45,fill:false,dashArray:"4 6"}).addTo(map);
  L.circleMarker(CFG.center,{radius:4,color:"#ffb43a",weight:2,fillOpacity:1})
    .addTo(map).bindPopup(CFG.gps ? "You (GPS fix)" : "You (configured position)");
}

function planeSVG(color, track, key){
  var body = (key==="heli")
    ? '<path d="M3 11h18v1.6H3zM21 15H3v1.6h18zM19 6h-2V3H7v3H5v1.7h14zM12.9 18h-1.8v3H9v1.7h6V21h-2.1z"/>'
    : (key==="drone")
    ? '<path d="M5 4a3 3 0 106 0 3 3 0 00-6 0zm8 0a3 3 0 106 0 3 3 0 00-6 0zM5 20a3 3 0 106 0 3 3 0 00-6 0zm8 0a3 3 0 106 0 3 3 0 00-6 0zM9.5 9h5v6h-5z"/>'
    : (key==="glider")
    ? '<path d="M23 8L13 10.4V21h-1.6V10.4L1 8l.3-1.5 10.1 1.9V3h1.2v5.4l10.1-1.9z"/>'
    : '<path d="M21 15.5v-1.8l-7.6-4.8V3.6a1.4 1.4 0 10-2.8 0v5.3L3 13.7v1.8l7.6-2.4v5.2L8.4 20v1.4L12 20.3l3.6 1.1V20l-2.2-1.7v-5.2z"/>';
  var rot = (key==="heli"||key==="drone") ? 0 : (track||0);
  return '<svg width="24" height="24" viewBox="0 0 24 24" fill="'+color+'" '+
         'style="transform:rotate('+rot+'deg)">'+body+'</svg>';
}

function esc(s){ return String(s==null?"":s); }

function popupFor(a){
  var d = document.createElement("div");
  function row(k,v){
    var p=document.createElement("div");
    var b=document.createElement("b"); b.textContent=k+" ";
    p.appendChild(b); p.appendChild(document.createTextNode(v));
    d.appendChild(p);
  }
  var t=document.createElement("div");
  t.style.cssText="font-weight:700;letter-spacing:.05em;margin-bottom:4px";
  t.textContent = esc(a.callsign) + "  " + LABEL[a.type_key];
  d.appendChild(t);
  row("Model", esc(a.model || (a.category_label ? a.category_label + " (broadcast)"
                                                : "unknown")));
  row("Reg", esc(a.registration || "—") + "   ICAO " + esc(a.icao24));
  row("Alt", fmtAlt(a) + "   Spd " + fmtSpd(a.velocity));
  row("Range", fmtDst(a.distance) + "   Trk " + (a.track==null?"—":Math.round(a.track)+"\u00b0"));
  if (a.squawk) row("Squawk", esc(a.squawk) + (a.emergency? "  "+a.emergency : ""));
  row("Seen", esc(a.last_seen_str));
  return d;
}

/* ---------- formatting ---------- */
function fmtAlt(a){
  if (a.on_ground) return "GND";
  if (a.altitude==null) return "—";
  return Math.round(UNITS.alt.f(a.altitude)).toLocaleString()+" "+UNITS.alt.s;
}
function fmtSpd(v){ return v==null?"—":Math.round(UNITS.spd.f(v))+" "+UNITS.spd.s; }
function fmtDst(d){ return d==null?"—":UNITS.dst.f(d).toFixed(1)+" "+UNITS.dst.s; }
function fmtAge(sec){
  if (sec==null) return "—";
  if (sec<60) return sec+"s";
  if (sec<3600) return Math.floor(sec/60)+"m";
  return Math.floor(sec/3600)+"h";
}

/* ---------- filtering + sorting ---------- */
function activeTypes(){
  var on = TYPES.filter(function(t){ return state.types[t]; });
  return on.length ? on : null;
}
function visible(){
  var q = $("q").value.trim().toLowerCase();
  var lo = parseFloat($("minalt").value), hi = parseFloat($("maxalt").value);
  var types = activeTypes();
  return state.ac.filter(function(a){
    if (types && types.indexOf(a.type_key) < 0) return false;
    if (q){
      var hay = (a.callsign+" "+(a.model||"")+" "+(a.registration||"")+" "+a.icao24).toLowerCase();
      if (hay.indexOf(q) < 0) return false;
    }
    if (!isNaN(lo) || !isNaN(hi)){
      if (a.altitude == null) return false;
      var shown = UNITS.alt.f(a.altitude);
      if (!isNaN(lo) && shown < lo) return false;
      if (!isNaN(hi) && shown > hi) return false;
    }
    return true;
  });
}
function sorted(list){
  var k = state.sort, d = state.dir;
  return list.slice().sort(function(x,y){
    var a = x[k], b = y[k];
    if (k === "model"){ a = x.model || "zzz"; b = y.model || "zzz"; }
    if (a == null) return 1;
    if (b == null) return -1;
    if (typeof a === "string") return a.localeCompare(b) * d;
    return (a - b) * d;
  });
}

/* ---------- render ---------- */
function renderTally(){
  var counts = {}; TYPES.forEach(function(t){counts[t]=0});
  state.ac.forEach(function(a){ counts[a.type_key] = (counts[a.type_key]||0)+1; });
  var box = $("tally"); box.textContent = "";
  TYPES.forEach(function(t){
    if (!counts[t] && !state.types[t]) return;
    var b = document.createElement("button");
    b.className = "chip"; b.type = "button";
    b.setAttribute("aria-pressed", state.types[t] ? "true" : "false");
    b.style.borderLeft = "3px solid " + COLOR[t];
    var n = document.createElement("b"); n.textContent = counts[t];
    b.appendChild(n); b.appendChild(document.createTextNode(" " + LABEL[t]));
    b.onclick = function(){ state.types[t] = !state.types[t]; render(); };
    box.appendChild(b);
  });
}

function renderStrips(list){
  var box = $("strips"); box.textContent = "";
  if (!list.length){
    var e = document.createElement("div");
    e.className = "empty";
    e.textContent = state.ac.length
      ? "No aircraft match these filters."
      : "No aircraft in range right now. The board fills as traffic enters the radius.";
    box.appendChild(e); return;
  }
  list.forEach(function(a){
    var row = document.createElement("div");
    row.className = "strip" + (a.emergency ? " alarm" : "") + (state.sel===a.icao24 ? " sel" : "");
    function cell(cls, text){
      var d = document.createElement("div"); d.className = cls; d.textContent = text; return d;
    }
    var band = document.createElement("div");
    band.className = "band " + a.type_key; row.appendChild(band);

    var cs = cell("cs", a.callsign || a.icao24);
    if (a.emergency){
      var s = document.createElement("span");
      s.className = "sq"; s.textContent = " " + a.emergency; cs.appendChild(s);
    }
    row.appendChild(cs);

    var m = document.createElement("div"); m.className = "model";
    if (a.model){ m.textContent = a.model; }
    else { var em = document.createElement("em"); em.textContent = LABEL[a.type_key].toLowerCase(); m.appendChild(em); }
    if (a.registration){
      var r = document.createElement("span");
      r.className = "tag"; r.textContent = "  " + a.registration; m.appendChild(r);
    }
    row.appendChild(m);

    row.appendChild(cell("num", fmtAlt(a)));
    row.appendChild(cell("num dim", fmtSpd(a.velocity)));
    row.appendChild(cell("num", fmtDst(a.distance)));
    row.appendChild(cell("num dim", a.track==null ? "—" : Math.round(a.track)+"\u00b0"));
    row.appendChild(cell("num dim", fmtAge(a.age)));

    row.onclick = function(){
      state.sel = (state.sel === a.icao24) ? null : a.icao24;
      if (map && marks[a.icao24] && state.sel){
        map.panTo(marks[a.icao24].getLatLng());
        marks[a.icao24].openPopup();
      }
      render();
    };
    box.appendChild(row);
  });
}

function renderMap(list){
  if (!map) return;
  var keep = {};
  list.forEach(function(a){
    if (a.latitude == null || a.longitude == null) return;
    keep[a.icao24] = 1;
    var icon = L.divIcon({className:"ac-icon", iconSize:[24,24], iconAnchor:[12,12],
      html: planeSVG(COLOR[a.type_key], a.track, a.type_key)});
    var m = marks[a.icao24];
    if (m){ m.setLatLng([a.latitude, a.longitude]); m.setIcon(icon); }
    else {
      m = L.marker([a.latitude, a.longitude], {icon:icon, title:a.callsign});
      marks[a.icao24] = m; m.addTo(acLayer);
    }
    m.bindPopup(popupFor(a));
  });
  Object.keys(marks).forEach(function(k){
    if (!keep[k]){ acLayer.removeLayer(marks[k]); delete marks[k]; }
  });
  trailLayer.clearLayers();
  if ($("trails").checked){
    list.forEach(function(a){
      if (a.trail && a.trail.length > 1){
        L.polyline(a.trail, {color:COLOR[a.type_key], weight:1.5, opacity:.55}).addTo(trailLayer);
      }
    });
  }
}

function renderHead(){
  var spans = $("head").querySelectorAll("span[data-k]");
  Array.prototype.forEach.call(spans, function(s){
    var k = s.dataset.k;
    s.textContent = s.textContent.replace(/[ \u25b2\u25bc]+$/,"");
    if (k === state.sort){
      var a = document.createElement("span");
      a.className = "arrow"; a.textContent = state.dir>0 ? " \u25b2" : " \u25bc";
      s.appendChild(a);
    }
  });
}

function render(){
  var list = sorted(visible());
  renderTally(); renderHead(); renderStrips(list); renderMap(list);
}

/* ---------- data ---------- */
function setStatus(cls, text){
  $("dot").className = "dot " + cls;
  $("stat").textContent = text;
}
async function load(){
  try{
    var r = await fetch("/plugins/skyhigh/data.json", {cache:"no-store"});
    if (!r.ok) throw new Error("HTTP " + r.status);
    var j = await r.json();
    state.ac = j.aircraft || [];
    if (j.center && map && !state._centered && j.gps){
      map.setView(j.center, map.getZoom()); state._centered = true;
    }
    if (j.error){
      setStatus("err", "degraded");
      $("errbar").style.display = "block";
      $("errbar").textContent = "Last fetch failed: " + j.error + " — retrying automatically.";
    } else {
      setStatus("live", state.ac.length + " tracked" + (j.gps ? " · gps" : ""));
      $("errbar").style.display = "none";
    }
    $("clock").textContent = "updated " + (j.updated || "—");
    render();
  }catch(e){
    setStatus("err", "no link to device");
  }
}
function schedule(){
  if (state.timer) clearInterval(state.timer);
  if ($("follow").checked) state.timer = setInterval(load, CFG.refresh * 1000);
}

/* ---------- wiring ---------- */
["q","minalt","maxalt"].forEach(function(id){ $(id).oninput = render; });
$("clear").onclick = function(){
  $("q").value = ""; $("minalt").value = ""; $("maxalt").value = "";
  state.types = {}; render();
};
$("trails").onchange = render;
$("follow").onchange = schedule;
$("head").onclick = function(e){
  var s = e.target.closest("span[data-k]"); if (!s) return;
  var k = s.dataset.k;
  if (state.sort === k) state.dir = -state.dir; else { state.sort = k; state.dir = 1; }
  render();
};

initMap();
load();
schedule();
})();
</script>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# Plugin
# ---------------------------------------------------------------------------

class SkyHigh(plugins.Plugin):
    __author__ = 'AlienMajik'
    __version__ = '2.2.0'
    __license__ = 'GPL3'
    __description__ = ('Tracks nearby aircraft via the OpenSky Network: on-screen '
                       'count, live map, flight-strip board, filters and exports.')

    def __init__(self):
        self.options = dict(DEFAULTS)
        self.ready = False

        self.data: Dict[str, Dict[str, Any]] = {}
        self.data_lock = threading.RLock()

        self.metadata_cache: Dict[str, Dict[str, Any]] = {}
        self.metadata_lock = threading.RLock()
        self._meta_pending: List[str] = []
        self._meta_dirty = False
        self._meta_saved_at = 0.0
        self._meta_source = None          # resolved at runtime for 'auto'
        self._opensky_meta_misses = 0

        self.historical_positions: Dict[str, List[Tuple[float, float]]] = {}
        self.stats: Dict[str, Any] = {}
        self.seen_icaos = set()

        self.error_message = ""
        self.last_update = ""
        self.last_update_epoch = 0

        self._agent = None
        self._gps_fix = None              # (lat, lon, epoch)
        self._session = None
        self._token = None
        self._token_expiry = 0.0
        self._token_lock = threading.RLock()
        self._stop_event = threading.Event()
        self._thread = None
        self._warned_timer = False
        self._consecutive_errors = 0

    # -- config ------------------------------------------------------------

    def _coerce_options(self):
        merged = dict(DEFAULTS)
        merged.update({k: v for k, v in (self.options or {}).items() if v is not None})
        for key in NUMERIC_INT:
            try:
                merged[key] = int(merged[key])
            except (TypeError, ValueError):
                merged[key] = DEFAULTS[key]
        for key in NUMERIC_FLOAT:
            try:
                merged[key] = float(merged[key])
            except (TypeError, ValueError):
                merged[key] = DEFAULTS[key]
        for key in BOOLS:
            val = merged[key]
            if isinstance(val, str):
                merged[key] = val.strip().lower() in ("1", "true", "yes", "on")
            else:
                merged[key] = bool(val)
        for key in ("blocklist", "allowlist"):
            val = merged.get(key) or []
            if isinstance(val, str):
                val = [v for v in re.split(r"[,\s]+", val) if v]
            merged[key] = {str(v).strip().lower() for v in val}
        if merged["units"] not in ("metric", "imperial"):
            merged["units"] = "metric"
        merged["radius"] = max(1.0, min(merged["radius"], 500.0))
        merged["history_points"] = max(2, min(merged["history_points"], 60))
        self.options = merged

    def _has_credentials(self) -> bool:
        o = self.options
        return bool((o.get("opensky_client_id") and o.get("opensky_client_secret"))
                    or (o.get("opensky_username") and o.get("opensky_password")))

    def _effective_timer(self) -> int:
        timer = self.options["timer"]
        if not self.options["enforce_rate_limit"]:
            return max(5, timer)
        floor = 15 if self._has_credentials() else 180
        if timer < floor:
            if not self._warned_timer:
                self._warned_timer = True
                logging.warning(
                    "[SkyHigh] timer=%ss exceeds the OpenSky budget for %s access; "
                    "using %ss instead. Add opensky_client_id/secret for faster polling, "
                    "or set enforce_rate_limit = false to override.",
                    timer, "authenticated" if self._has_credentials() else "anonymous", floor)
            return floor
        return timer

    # -- lifecycle ---------------------------------------------------------

    def on_loaded(self):
        self._coerce_options()
        logging.info("[SkyHigh] v%s loading (timer=%ss, radius=%smi, metadata=%s)",
                     self.__version__, self._effective_timer(), self.options["radius"],
                     "off" if self.options["disable_metadata"] else self.options["metadata_source"])

        for key in ("aircraft_file", "metadata_file", "stats_file"):
            directory = os.path.dirname(self.options[key])
            if directory:
                try:
                    os.makedirs(directory, exist_ok=True)
                except OSError as exc:
                    logging.warning("[SkyHigh] cannot create %s: %s", directory, exc)

        self._session = requests.Session()
        self._session.headers.update({"User-Agent": USER_AGENT})

        self._load_metadata_cache()
        self._load_stats()
        self._load_aircraft_file()

        if self._thread and self._thread.is_alive():
            self._stop_event.set()
            self._thread.join(timeout=3)
        self._stop_event = threading.Event()
        self._thread = threading.Thread(target=self._fetch_loop, name="skyhigh",
                                        daemon=True)
        self._thread.start()
        self.ready = True

    def on_ready(self, agent):
        self._agent = agent

    def on_unload(self, ui):
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=5)
        self._save_metadata_cache(force=True)
        self._save_stats()
        if self.options.get("persist_aircraft"):
            self._save_aircraft_file()
        if ui:
            try:
                with ui._lock:
                    ui.remove_element('SkyHigh')
            except Exception:
                pass
        if self._session:
            try:
                self._session.close()
            except Exception:
                pass
        logging.info("[SkyHigh] unloaded")

    # -- screen ------------------------------------------------------------

    def on_ui_setup(self, ui):
        ui.add_element('SkyHigh', LabeledValue(
            color=BLACK,
            label='SkyHigh',
            value='--',
            position=(int(self.options.get("adsb_x_coord", DEFAULTS["adsb_x_coord"])),
                      int(self.options.get("adsb_y_coord", DEFAULTS["adsb_y_coord"]))),
            label_font=fonts.Small,
            text_font=fonts.Small,
        ))

    def on_ui_update(self, ui):
        with self.data_lock:
            count = len(self.data)
            alarms = sum(1 for a in self.data.values() if a.get("emergency"))
            mil = sum(1 for a in self.data.values() if a.get("type_key") == "mil")

        if self.error_message and count == 0:
            value = "err"
        else:
            value = str(count)
            if mil:
                value += " %dM" % mil
            if alarms:
                value += " !"
            if self.options.get("ui_verbose") and self.last_update:
                value += " %s" % self.last_update
            if self.error_message:
                value += " ?"
        ui.set('SkyHigh', value[:24])

    # -- background loop ---------------------------------------------------

    def _fetch_loop(self):
        if self._stop_event.wait(8):     # let the network settle after boot
            return
        while not self._stop_event.is_set():
            interval = self._effective_timer()
            try:
                self.fetch_aircraft_data()
                self.error_message = ""
                self._consecutive_errors = 0
            except RateLimited as exc:
                self._consecutive_errors += 1
                self.error_message = str(exc)
                interval = max(interval, exc.retry_after or interval * 2)
                logging.warning("[SkyHigh] rate limited, next try in %ss", int(interval))
            except Exception as exc:                      # noqa: BLE001
                self._consecutive_errors += 1
                self.error_message = str(exc)[:120]
                backoff = min(interval * (2 ** min(self._consecutive_errors, 4)), 900)
                interval = max(interval, backoff)
                logging.error("[SkyHigh] fetch failed (%d in a row): %s",
                              self._consecutive_errors, exc)
            self._save_metadata_cache()
            self._stop_event.wait(interval)

    # -- auth --------------------------------------------------------------

    def _oauth_token(self) -> Optional[str]:
        cid = self.options.get("opensky_client_id")
        secret = self.options.get("opensky_client_secret")
        if not (cid and secret):
            return None
        with self._token_lock:
            if self._token and time.time() < self._token_expiry - 60:
                return self._token
            try:
                resp = self._session.post(
                    TOKEN_URL,
                    data={"grant_type": "client_credentials",
                          "client_id": cid, "client_secret": secret},
                    timeout=self.options["request_timeout"])
                if resp.status_code != 200:
                    logging.error("[SkyHigh] OAuth token request failed (%s); "
                                  "check opensky_client_id/secret", resp.status_code)
                    self._token, self._token_expiry = None, 0
                    return None
                payload = resp.json()
                self._token = payload.get("access_token")
                self._token_expiry = time.time() + int(payload.get("expires_in", 1800))
                logging.info("[SkyHigh] OpenSky OAuth token acquired")
                return self._token
            except Exception as exc:                      # noqa: BLE001
                logging.error("[SkyHigh] OAuth token error: %s", exc)
                self._token, self._token_expiry = None, 0
                return None

    def _auth_headers(self) -> Dict[str, str]:
        token = self._oauth_token()
        if token:
            return {"Authorization": "Bearer %s" % token}
        user = self.options.get("opensky_username")
        pwd = self.options.get("opensky_password")
        if user and pwd:
            encoded = base64.b64encode(("%s:%s" % (user, pwd)).encode()).decode()
            return {"Authorization": "Basic %s" % encoded}
        return {}

    # -- position ----------------------------------------------------------

    def _gps_coords(self) -> Optional[Tuple[float, float]]:
        """Best-effort GPS fix from the gps plugin or the bettercap session."""
        if not self.options.get("use_gps"):
            return None

        candidates = []
        try:
            gps_plugin = (plugins.loaded.get("gps")
                          or plugins.loaded.get("gps_listener")
                          or plugins.loaded.get("pwndroid"))
            if gps_plugin is not None:
                candidates.append(getattr(gps_plugin, "coordinates", None))
                candidates.append(getattr(gps_plugin, "last_position", None))
        except Exception:
            pass
        try:
            if self._agent is not None:
                session = self._agent.session()
                if isinstance(session, dict):
                    candidates.append(session.get("gps"))
        except Exception:
            pass

        for cand in candidates:
            coords = self._extract_coords(cand)
            if coords:
                self._gps_fix = (coords[0], coords[1], time.time())
                return coords

        if self._gps_fix:
            lat, lon, when = self._gps_fix
            if time.time() - when <= self.options["gps_max_age"]:
                return (lat, lon)
        return None

    @staticmethod
    def _extract_coords(blob) -> Optional[Tuple[float, float]]:
        if not isinstance(blob, dict):
            return None
        lat = lon = None
        for key, val in blob.items():
            low = str(key).lower()
            if low in ("latitude", "lat"):
                lat = val
            elif low in ("longitude", "lon", "lng", "long"):
                lon = val
        try:
            lat, lon = float(lat), float(lon)
        except (TypeError, ValueError):
            return None
        if not (-90 <= lat <= 90) or not (-180 <= lon <= 180):
            return None
        if abs(lat) < 1e-6 and abs(lon) < 1e-6:      # 0,0 means "no fix"
            return None
        return (lat, lon)

    def _current_center(self) -> Tuple[float, float, bool]:
        coords = self._gps_coords()
        if coords:
            return coords[0], coords[1], True
        return self.options["latitude"], self.options["longitude"], False

    @staticmethod
    def _bbox(lat: float, lon: float, radius_mi: float):
        """Bounding box in degrees. Longitude degrees shrink with latitude —
        2.0.0 ignored that, so boxes were badly wrong away from the equator."""
        lat_delta = radius_mi / MILES_PER_DEG_LAT
        cos_lat = max(math.cos(math.radians(lat)), 0.01)
        lon_delta = min(radius_mi / (MILES_PER_DEG_LAT * cos_lat), 179.0)
        return (max(-90.0, lat - lat_delta), min(90.0, lat + lat_delta),
                max(-180.0, lon - lon_delta), min(180.0, lon + lon_delta))

    @staticmethod
    def _haversine(lat1, lon1, lat2, lon2) -> float:
        p1, p2 = math.radians(lat1), math.radians(lat2)
        dp = p2 - p1
        dl = math.radians(lon2 - lon1)
        a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
        return 2 * EARTH_RADIUS_MI * math.asin(min(1.0, math.sqrt(a)))

    # -- fetching ----------------------------------------------------------

    def fetch_aircraft_data(self):
        lat, lon, from_gps = self._current_center()
        lamin, lamax, lomin, lomax = self._bbox(lat, lon, self.options["radius"])
        params = {"lamin": round(lamin, 5), "lomin": round(lomin, 5),
                  "lamax": round(lamax, 5), "lomax": round(lomax, 5),
                  # extended=1 appends the emitter category, which lets the
                  # plugin type aircraft without any metadata lookup at all.
                  "extended": 1}

        try:
            resp = self._session.get(STATES_URL, params=params,
                                     headers=self._auth_headers(),
                                     timeout=self.options["request_timeout"])
        except requests.RequestException as exc:
            raise OpenSkyError("network: %s" % exc.__class__.__name__) from exc

        if resp.status_code == 429:
            retry = resp.headers.get("Retry-After")
            raise RateLimited("rate limited (429)",
                              retry_after=int(retry) if retry and retry.isdigit() else None)
        if resp.status_code in (401, 403):
            self._token, self._token_expiry = None, 0
            raise OpenSkyError("auth rejected (%s) — check OpenSky credentials"
                               % resp.status_code)
        if resp.status_code != 200:
            raise OpenSkyError("API returned %s" % resp.status_code)

        try:
            payload = resp.json()
        except ValueError as exc:
            raise OpenSkyError("malformed API response") from exc

        states = (payload or {}).get("states") or []
        seen = self._parse_and_store(states, lat, lon)
        self._process_metadata_queue()
        self.prune_old_data()
        if self.options["persist_aircraft"]:
            self._save_aircraft_file()

        self.last_update = datetime.now().strftime("%H:%M:%S")
        self.last_update_epoch = time.time()
        logging.debug("[SkyHigh] %d aircraft in range (%s%.4f, %.4f)",
                      len(seen), "gps " if from_gps else "", lat, lon)

    def _parse_and_store(self, states: List[list], clat: float, clon: float) -> List[str]:
        blocklist = self.options["blocklist"]
        allowlist = self.options["allowlist"]
        min_alt = self.options.get("min_altitude")
        history_points = self.options["history_points"]
        now = time.time()
        touched = []

        for state in states:
            if not state or len(state) < 11:
                continue
            icao24 = str(state[0] or "").strip().lower()
            if not icao24:
                continue
            if blocklist and icao24 in blocklist:
                continue
            if allowlist and icao24 not in allowlist:
                continue

            callsign = (state[1] or "").strip() or icao24.upper()
            lon = self._num(state[5])
            lat = self._num(state[6])
            on_ground = bool(state[8])
            baro = self._num(state[7])
            geo = self._num(state[13]) if len(state) > 13 else None
            altitude = baro if baro is not None else geo
            velocity = self._num(state[9])
            track = self._num(state[10])
            vert = self._num(state[11]) if len(state) > 11 else None
            squawk = str(state[14]).strip() if len(state) > 14 and state[14] else None
            last_contact = self._num(state[4]) or now
            category = None
            if len(state) > 17:
                try:
                    category = int(state[17])
                except (TypeError, ValueError):
                    category = None

            if on_ground and self.options["ignore_on_ground"]:
                continue
            if min_alt is not None and altitude is not None and altitude < float(min_alt):
                continue

            distance = None
            if lat is not None and lon is not None:
                distance = round(self._haversine(clat, clon, lat, lon), 2)
                # The API only takes a rectangle, so without this a "50 mile
                # radius" quietly reached 70 miles into the box corners.
                if (self.options["trim_to_radius"]
                        and distance > self.options["radius"] * 1.02):
                    continue

            meta = self._cached_metadata(icao24)
            if meta is None:
                meta = self._placeholder_metadata(callsign, category)
                self._queue_metadata(icao24)
            elif meta.get("type_key", "other") == "other" and category in CATEGORY_TYPE:
                # Registry text was inconclusive; the broadcast category is a
                # better answer than "other".
                meta = dict(meta, type_key=CATEGORY_TYPE[category])

            emergency = EMERGENCY_SQUAWKS.get(squawk or "")
            with self.data_lock:
                previous = self.data.get(icao24) or {}
                if lat is not None and lon is not None:
                    trail = self.historical_positions.setdefault(icao24, [])
                    if not trail or trail[-1] != [lat, lon]:
                        trail.append([lat, lon])
                    del trail[:-history_points]

                self.data[icao24] = {
                    "icao24": icao24,
                    "callsign": callsign,
                    "origin_country": state[2] or "",
                    "latitude": lat,
                    "longitude": lon,
                    "altitude": altitude,
                    "baro_altitude": baro,
                    "geo_altitude": geo,
                    "on_ground": on_ground,
                    "velocity": velocity,
                    "track": track,
                    "vertical_rate": vert,
                    "squawk": squawk,
                    "emergency": emergency,
                    "category": category,
                    "category_label": CATEGORY_LABEL.get(category or 0, ""),
                    "distance": distance,
                    "last_contact": last_contact,
                    "last_seen_str": datetime.fromtimestamp(last_contact).strftime(
                        "%Y-%m-%d %H:%M:%S"),
                    "first_seen": previous.get("first_seen", last_contact),
                    "model": meta.get("model"),
                    "registration": meta.get("registration"),
                    "manufacturer": meta.get("manufacturer"),
                    "typecode": meta.get("typecode"),
                    "operator": meta.get("operator"),
                    "type_key": meta.get("type_key", "other"),
                }
            touched.append(icao24)

            if emergency and icao24 not in self.seen_icaos:
                logging.warning("[SkyHigh] squawk %s (%s) from %s", squawk,
                                emergency, callsign)
            self.seen_icaos.add(icao24)

        self._update_stats(touched)
        return touched

    @staticmethod
    def _num(value) -> Optional[float]:
        if value is None:
            return None
        try:
            num = float(value)
        except (TypeError, ValueError):
            return None
        return None if math.isnan(num) else num

    # -- metadata ----------------------------------------------------------

    def _queue_metadata(self, icao24: str):
        if self.options["disable_metadata"]:
            return
        with self.metadata_lock:
            if icao24 not in self._meta_pending:
                self._meta_pending.append(icao24)

    def _cached_metadata(self, icao24: str) -> Optional[Dict[str, Any]]:
        """Return usable cached metadata, or None if it should be fetched.

        A cached miss counts as usable until the negative TTL expires, which
        stops the plugin hammering the API once per cycle for aircraft the
        database has never heard of."""
        with self.metadata_lock:
            entry = self.metadata_cache.get(icao24)
        if not entry:
            return None
        fetched = entry.get("fetch_time", 0)
        age = datetime.now() - datetime.fromtimestamp(fetched)
        if entry.get("miss"):
            if age < timedelta(hours=self.options["metadata_negative_cache_hours"]):
                return entry.get("data") or self._placeholder_metadata(None)
            return None
        if age < timedelta(days=self.options["metadata_cache_expiry_days"]):
            return entry.get("data")
        return None

    def _process_metadata_queue(self):
        if self.options["disable_metadata"]:
            return
        limit = max(0, self.options["max_metadata_fetches_per_cycle"])
        for _ in range(limit):
            with self.metadata_lock:
                if not self._meta_pending:
                    return
                icao24 = self._meta_pending.pop(0)
            if self._stop_event.is_set():
                return
            meta = self._fetch_metadata(icao24)
            if meta is None:
                continue
            with self.data_lock:
                record = self.data.get(icao24)
                if record:
                    record.update({
                        "model": meta.get("model"),
                        "registration": meta.get("registration"),
                        "manufacturer": meta.get("manufacturer"),
                        "typecode": meta.get("typecode"),
                        "operator": meta.get("operator"),
                        "type_key": meta.get("type_key", record.get("type_key", "other")),
                    })

    def _resolve_source(self) -> str:
        if self._meta_source:
            return self._meta_source
        configured = str(self.options.get("metadata_source", "auto")).lower()
        self._meta_source = configured if configured in ("opensky", "adsbdb", "none") else "opensky"
        return self._meta_source

    def _fetch_metadata(self, icao24: str) -> Optional[Dict[str, Any]]:
        source = self._resolve_source()
        if source == "none":
            return None
        raw = None
        try:
            if source == "opensky":
                raw = self._fetch_meta_opensky(icao24)
                if raw is None and str(self.options.get("metadata_source")).lower() == "auto":
                    self._opensky_meta_misses += 1
                    if self._opensky_meta_misses >= 5:
                        self._meta_source = "adsbdb"
                        logging.info("[SkyHigh] OpenSky aircraft database is not "
                                     "answering; switching lookups to adsbdb.com")
                        raw = self._fetch_meta_adsbdb(icao24)
            else:
                raw = self._fetch_meta_adsbdb(icao24)
        except requests.RequestException as exc:
            logging.debug("[SkyHigh] metadata lookup %s failed: %s", icao24, exc)
            return None

        if raw is None:
            with self.metadata_lock:
                self.metadata_cache[icao24] = {
                    "miss": True, "fetch_time": time.time(),
                    "data": self._placeholder_metadata(None)}
                self._meta_dirty = True
            return None

        meta = self._classify(raw)
        with self.metadata_lock:
            self.metadata_cache[icao24] = {"data": meta, "fetch_time": time.time()}
            self._meta_dirty = True
        return meta

    def _meta_timeout(self) -> int:
        return max(3, min(int(self.options["request_timeout"]), 8))

    def _fetch_meta_opensky(self, icao24: str) -> Optional[Dict[str, Any]]:
        resp = self._session.get(OPENSKY_META_URL.format(icao=icao24),
                                 headers=self._auth_headers(),
                                 timeout=self._meta_timeout())
        if resp.status_code != 200:
            return None
        try:
            data = resp.json()
        except ValueError:
            return None
        if not isinstance(data, dict) or not data:
            return None
        return {
            "model": (data.get("model") or "").strip(),
            "registration": (data.get("registration") or "").strip(),
            "manufacturer": (data.get("manufacturerName") or "").strip(),
            "typecode": (data.get("typecode") or "").strip(),
            "operator": (data.get("operator") or data.get("owner") or "").strip(),
            "flags": " ".join(str(f) for f in (data.get("special_flags") or [])),
        }

    def _fetch_meta_adsbdb(self, icao24: str) -> Optional[Dict[str, Any]]:
        resp = self._session.get(ADSBDB_META_URL.format(icao=icao24),
                                 timeout=self._meta_timeout())
        if resp.status_code != 200:
            return None
        try:
            body = resp.json()
        except ValueError:
            return None
        aircraft = ((body or {}).get("response") or {}).get("aircraft")
        if not isinstance(aircraft, dict):
            return None
        return {
            "model": (aircraft.get("type") or "").strip(),
            "registration": (aircraft.get("registration") or "").strip(),
            "manufacturer": (aircraft.get("manufacturer") or "").strip(),
            "typecode": (aircraft.get("icao_type") or "").strip(),
            "operator": (aircraft.get("registered_owner") or "").strip(),
            "flags": "",
        }

    def _placeholder_metadata(self, callsign: Optional[str],
                              category: Optional[int] = None) -> Dict[str, Any]:
        """Used before a lookup lands. Unknown aircraft are 'other', not 'ga' —
        2.0.0 defaulted everything to light aircraft, which made the GA filter
        meaningless. The broadcast category fills the gap where it exists, so
        most traffic is typed on the very first sweep with no API call."""
        type_key = CATEGORY_TYPE.get(category, "other") if category else "other"
        if callsign and self.options.get("military_callsign_heuristic"):
            if MIL_CALLSIGN_RE.match(callsign.upper().replace(" ", "")):
                type_key = "mil"
        return {"model": "", "registration": "", "manufacturer": "",
                "typecode": "", "operator": "", "type_key": type_key}

    def _classify(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        model = (raw.get("model") or "").lower()
        manufacturer = (raw.get("manufacturer") or "").lower()
        typecode = (raw.get("typecode") or "").upper().strip()
        operator = (raw.get("operator") or "").lower()
        flags = (raw.get("flags") or "").lower()
        haystack = " ".join((manufacturer, model, operator))

        def matches(key: str) -> bool:
            return any(rx.search(haystack) for rx in TYPE_RE[key])

        # Exact typecodes first — they are unambiguous where free text is not.
        if typecode in DRONE_TYPECODES:
            type_key = "drone"
        elif typecode in HELI_TYPECODES:
            type_key = "heli"
        elif typecode in GLIDER_TYPECODES:
            type_key = "glider"
        elif typecode in MIL_TYPECODES or "military" in flags:
            type_key = "mil"
        elif matches("drone"):
            type_key = "drone"
        elif matches("mil"):
            type_key = "mil"
        elif matches("heli"):
            type_key = "heli"
        elif matches("glider"):
            type_key = "glider"
        elif typecode and JET_TYPECODE_RE.match(typecode):
            type_key = "jet"
        elif typecode and GA_TYPECODE_RE.match(typecode):
            type_key = "ga"
        elif matches("ga"):
            type_key = "ga"
        elif matches("jet"):
            type_key = "jet"
        else:
            type_key = "other"

        return {
            "model": raw.get("model") or typecode or "",
            "registration": raw.get("registration") or "",
            "manufacturer": raw.get("manufacturer") or "",
            "typecode": typecode,
            "operator": raw.get("operator") or "",
            "type_key": type_key,
        }

    # -- pruning + persistence --------------------------------------------

    def prune_old_data(self):
        minutes = self.options["prune_minutes"]
        if minutes <= 0:      # documented as "0 disables" — 2.0.0 pruned everything
            return
        cutoff = time.time() - (minutes * 60)
        with self.data_lock:
            stale = [icao for icao, rec in self.data.items()
                     if (rec.get("last_contact") or 0) < cutoff]
            for icao in stale:
                self.data.pop(icao, None)
                self.historical_positions.pop(icao, None)

            cap = self.options["max_tracked"]
            if len(self.data) > cap:
                ordered = sorted(self.data.items(),
                                 key=lambda kv: kv[1].get("last_contact") or 0)
                for icao, _ in ordered[:len(self.data) - cap]:
                    self.data.pop(icao, None)
                    self.historical_positions.pop(icao, None)
        if stale:
            logging.debug("[SkyHigh] pruned %d stale aircraft", len(stale))

    @staticmethod
    def _atomic_write(path: str, text: str):
        tmp = "%s.tmp" % path
        with open(tmp, "w") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)

    def _save_aircraft_file(self):
        try:
            with self.data_lock:
                payload = json.dumps(self.data, separators=(",", ":"))
            self._atomic_write(self.options["aircraft_file"], payload)
        except OSError as exc:
            logging.warning("[SkyHigh] could not write aircraft file: %s", exc)

    def _load_aircraft_file(self):
        try:
            with open(self.options["aircraft_file"]) as handle:
                data = json.load(handle)
            if isinstance(data, dict):
                with self.data_lock:
                    self.data = {k: v for k, v in data.items() if isinstance(v, dict)}
                    for rec in self.data.values():
                        rec.setdefault("type_key", self._legacy_type_key(rec))
                        rec.setdefault("altitude", rec.get("baro_altitude"))
                self.prune_old_data()
        except (OSError, ValueError):
            with self.data_lock:
                self.data = {}

    @staticmethod
    def _legacy_type_key(rec: Dict[str, Any]) -> str:
        for flag, key in (("is_military", "mil"), ("is_helicopter", "heli"),
                          ("is_commercial_jet", "jet"), ("is_drone", "drone"),
                          ("is_glider", "glider"), ("is_small_plane", "ga")):
            if rec.get(flag):
                return key
        return "other"

    def _load_metadata_cache(self):
        try:
            with open(self.options["metadata_file"]) as handle:
                cache = json.load(handle)
            self.metadata_cache = cache if isinstance(cache, dict) else {}
        except (OSError, ValueError):
            self.metadata_cache = {}

    def _save_metadata_cache(self, force: bool = False):
        """Written at most every 5 minutes; 2.0.0 rewrote the whole file after
        every single lookup, which is rough on an SD card."""
        with self.metadata_lock:
            if not self._meta_dirty and not force:
                return
            if not force and time.time() - self._meta_saved_at < 300:
                return
            payload = json.dumps(self.metadata_cache, separators=(",", ":"))
            self._meta_dirty = False
            self._meta_saved_at = time.time()
        try:
            self._atomic_write(self.options["metadata_file"], payload)
        except OSError as exc:
            logging.warning("[SkyHigh] could not write metadata cache: %s", exc)

    def _load_stats(self):
        try:
            with open(self.options["stats_file"]) as handle:
                stats = json.load(handle)
            if isinstance(stats, dict):
                self.stats = stats
                self.seen_icaos = set(stats.get("seen", [])[:20000])
        except (OSError, ValueError):
            self.stats = {}
        self.stats.setdefault("since", time.time())
        self.stats.setdefault("max_altitude", 0)
        self.stats.setdefault("closest_mi", None)
        self.stats.setdefault("emergencies", 0)

    def _update_stats(self, touched: List[str]):
        with self.data_lock:
            for icao in touched:
                rec = self.data.get(icao) or {}
                alt = rec.get("altitude")
                if alt and alt > (self.stats.get("max_altitude") or 0):
                    self.stats["max_altitude"] = round(alt)
                dist = rec.get("distance")
                if dist is not None:
                    best = self.stats.get("closest_mi")
                    if best is None or dist < best:
                        self.stats["closest_mi"] = dist
                if rec.get("emergency"):
                    self.stats["emergencies"] = self.stats.get("emergencies", 0) + 1
        self.stats["unique_seen"] = len(self.seen_icaos)

    def _save_stats(self):
        try:
            payload = dict(self.stats)
            payload["seen"] = sorted(self.seen_icaos)[:20000]
            self._atomic_write(self.options["stats_file"],
                               json.dumps(payload, separators=(",", ":")))
        except OSError as exc:
            logging.warning("[SkyHigh] could not write stats: %s", exc)

    # -- web ---------------------------------------------------------------

    def _snapshot(self) -> List[Dict[str, Any]]:
        now = time.time()
        with self.data_lock:
            records = [dict(rec) for rec in self.data.values()]
            trails = {k: list(v) for k, v in self.historical_positions.items()}
        for rec in records:
            last = rec.get("last_contact") or now
            rec["age"] = max(0, int(now - last))
            rec["trail"] = trails.get(rec["icao24"], [])
        return records

    def on_webhook(self, path, request):
        route = (path or "").strip("/").lower()

        if request.method != "GET":
            return Response("Method not allowed", status=405)

        if route in ("", "index", "index.html"):
            lat, lon, from_gps = self._current_center()
            config = {
                "center": [lat, lon],
                "gps": from_gps,
                "radius_mi": self.options["radius"],
                "tile_url": self.options["map_tile_url"],
                "attribution": self.options["map_attribution"],
                "units": self.options["units"],
                "refresh": max(10, self.options["web_refresh"] or self._effective_timer()),
            }
            page = HTML_PAGE.replace("__CONFIG__", json.dumps(config))
            return Response(page, mimetype="text/html; charset=utf-8")

        if route in ("data.json", "data"):
            lat, lon, from_gps = self._current_center()
            body = {
                "updated": self.last_update or None,
                "updated_epoch": self.last_update_epoch,
                "error": self.error_message or "",
                "center": [lat, lon],
                "gps": from_gps,
                "radius_mi": self.options["radius"],
                "units": self.options["units"],
                "stats": self.stats,
                "aircraft": self._snapshot(),
            }
            return Response(json.dumps(body, default=str),
                            mimetype="application/json",
                            headers={"Cache-Control": "no-store"})

        if route in ("export/csv", "csv"):
            return self._export_csv()
        if route in ("export/kml", "kml"):
            return self._export_kml()
        if route in ("export/gpx", "gpx"):
            return self._export_gpx()

        return Response("Not found", status=404)

    def _positioned(self) -> List[Dict[str, Any]]:
        return [rec for rec in self._snapshot()
                if isinstance(rec.get("latitude"), (int, float))
                and isinstance(rec.get("longitude"), (int, float))]

    @staticmethod
    def _stamp() -> str:
        return datetime.now().strftime("%Y%m%d-%H%M")

    def _export_csv(self):
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(["icao24", "callsign", "registration", "model", "typecode",
                         "operator", "type", "latitude", "longitude",
                         "altitude_m", "on_ground", "velocity_ms", "track_deg",
                         "vertical_rate_ms", "squawk", "emergency",
                         "distance_mi", "origin_country", "last_seen"])
        for rec in sorted(self._positioned(), key=lambda r: r.get("distance") or 9e9):
            writer.writerow([
                rec.get("icao24"), rec.get("callsign"), rec.get("registration"),
                rec.get("model"), rec.get("typecode"), rec.get("operator"),
                TYPE_LABELS.get(rec.get("type_key"), "Unknown"),
                rec.get("latitude"), rec.get("longitude"), rec.get("altitude"),
                rec.get("on_ground"), rec.get("velocity"), rec.get("track"),
                rec.get("vertical_rate"), rec.get("squawk"), rec.get("emergency"),
                rec.get("distance"), rec.get("origin_country"), rec.get("last_seen_str"),
            ])
        return Response(buffer.getvalue(), mimetype="text/csv", headers={
            "Content-Disposition": "attachment;filename=skyhigh-%s.csv" % self._stamp()})

    def _export_kml(self):
        # KML colours are aabbggrr, not rrggbb.
        colors = {"mil": "ff8ad15a", "heli": "ff6b6bff", "jet": "ffffa95a",
                  "ga": "ff53d4ff", "drone": "ffff8cc0", "glider": "ff5c9dff",
                  "other": "ffb6a38e"}
        out = ['<?xml version="1.0" encoding="UTF-8"?>',
               '<kml xmlns="http://www.opengis.net/kml/2.2"><Document>',
               '<name>SkyHigh %s</name>' % xml_escape(self._stamp())]
        for key, color in colors.items():
            out.append('<Style id="%s"><IconStyle><color>%s</color><scale>1.1</scale>'
                       '<Icon><href>http://maps.google.com/mapfiles/kml/shapes/airports.png'
                       '</href></Icon></IconStyle></Style>' % (key, color))
        for rec in self._positioned():
            alt = rec.get("altitude") or 0
            desc = ("Model: {model}\nReg: {reg}\nType: {typ}\nAlt: {alt} m\n"
                    "Speed: {spd} m/s\nRange: {dist} mi\nSeen: {seen}").format(
                model=rec.get("model") or "unknown",
                reg=rec.get("registration") or "-",
                typ=TYPE_LABELS.get(rec.get("type_key"), "Unknown"),
                alt=round(alt), spd=round(rec.get("velocity") or 0),
                dist=rec.get("distance"), seen=rec.get("last_seen_str"))
            out.append(
                "<Placemark><name>{name}</name><styleUrl>#{style}</styleUrl>"
                "<description>{desc}</description>"
                "<Point><altitudeMode>absolute</altitudeMode>"
                "<coordinates>{lon},{lat},{alt}</coordinates></Point></Placemark>".format(
                    name=xml_escape(str(rec.get("callsign") or rec.get("icao24"))),
                    style=rec.get("type_key", "other"),
                    desc=xml_escape(desc), lon=rec["longitude"], lat=rec["latitude"],
                    alt=round(alt)))
        out.append("</Document></kml>")
        return Response("".join(out),
                        mimetype="application/vnd.google-earth.kml+xml",
                        headers={"Content-Disposition":
                                 "attachment;filename=skyhigh-%s.kml" % self._stamp()})

    def _export_gpx(self):
        out = ['<?xml version="1.0" encoding="UTF-8"?>',
               '<gpx version="1.1" creator="SkyHigh" '
               'xmlns="http://www.topografix.com/GPX/1/1">']
        for rec in self._positioned():
            out.append(
                '<wpt lat="{lat}" lon="{lon}"><ele>{ele}</ele><name>{name}</name>'
                '<desc>{desc}</desc><sym>Airport</sym></wpt>'.format(
                    lat=rec["latitude"], lon=rec["longitude"],
                    ele=round(rec.get("altitude") or 0),
                    name=xml_escape(str(rec.get("callsign") or rec.get("icao24"))),
                    desc=xml_escape("%s | %s" % (
                        rec.get("model") or "unknown",
                        TYPE_LABELS.get(rec.get("type_key"), "Unknown")))))
        out.append("</gpx>")
        return Response("".join(out), mimetype="application/gpx+xml", headers={
            "Content-Disposition": "attachment;filename=skyhigh-%s.gpx" % self._stamp()})
