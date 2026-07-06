# 1. all states, all capital cities weather information
# 2. all timezone from GMT 0 to 10 info
# 3. currency exchange value with usa$, uk pounds and qwait dinar (KWD)
#
# the agents pull real data from free (no-key) apis instead of asking the llm
# to make numbers up. the llm is only used for an optional --summarize pass.

import argparse
import json
import os
import sqlite3
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import requests

HERE = Path(__file__).parent
DB = HERE / "blackboard.db"
DASHBOARD = HERE / "dashboard.html"

OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen2.5:1.5b")


# --- blackboard (just a sqlite table the agents read/write) ---

def init_db():
    conn = sqlite3.connect(DB)
    conn.execute(
        """CREATE TABLE IF NOT EXISTS logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            agent_name TEXT NOT NULL,
            input_data TEXT,
            output_data TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )"""
    )
    conn.commit()
    conn.close()


def log_run(agent, query, output):
    conn = sqlite3.connect(DB)
    conn.execute(
        "INSERT INTO logs (agent_name, input_data, output_data) VALUES (?, ?, ?)",
        (agent, query, output),
    )
    conn.commit()
    conn.close()


def get_latest_output(agent):
    conn = sqlite3.connect(DB)
    row = conn.execute(
        "SELECT output_data FROM logs WHERE agent_name = ? ORDER BY id DESC LIMIT 1",
        (agent,),
    ).fetchone()
    conn.close()
    return row[0] if row else None


def get_all_latest():
    # latest row per agent, for the dashboard
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """SELECT l.agent_name, l.input_data, l.output_data, l.created_at
           FROM logs l
           JOIN (SELECT agent_name, MAX(id) AS m FROM logs GROUP BY agent_name) last
             ON l.agent_name = last.agent_name AND l.id = last.m"""
    ).fetchall()
    conn.close()
    return {r["agent_name"]: dict(r) for r in rows}


# --- weather: open-meteo, one call for every state capital ---

# state -> (capital, lat, lon)
STATE_CAPITALS = {
    "Alabama": ("Montgomery", 32.3792, -86.3077),
    "Alaska": ("Juneau", 58.3019, -134.4197),
    "Arizona": ("Phoenix", 33.4484, -112.0740),
    "Arkansas": ("Little Rock", 34.7465, -92.2896),
    "California": ("Sacramento", 38.5816, -121.4944),
    "Colorado": ("Denver", 39.7392, -104.9903),
    "Connecticut": ("Hartford", 41.7658, -72.6734),
    "Delaware": ("Dover", 39.1582, -75.5244),
    "Florida": ("Tallahassee", 30.4383, -84.2807),
    "Georgia": ("Atlanta", 33.7490, -84.3880),
    "Hawaii": ("Honolulu", 21.3069, -157.8583),
    "Idaho": ("Boise", 43.6150, -116.2023),
    "Illinois": ("Springfield", 39.7817, -89.6501),
    "Indiana": ("Indianapolis", 39.7684, -86.1581),
    "Iowa": ("Des Moines", 41.5868, -93.6250),
    "Kansas": ("Topeka", 39.0473, -95.6752),
    "Kentucky": ("Frankfort", 38.2009, -84.8733),
    "Louisiana": ("Baton Rouge", 30.4515, -91.1871),
    "Maine": ("Augusta", 44.3106, -69.7795),
    "Maryland": ("Annapolis", 38.9784, -76.4922),
    "Massachusetts": ("Boston", 42.3601, -71.0589),
    "Michigan": ("Lansing", 42.7325, -84.5555),
    "Minnesota": ("Saint Paul", 44.9537, -93.0900),
    "Mississippi": ("Jackson", 32.2988, -90.1848),
    "Missouri": ("Jefferson City", 38.5767, -92.1735),
    "Montana": ("Helena", 46.5891, -112.0391),
    "Nebraska": ("Lincoln", 40.8136, -96.7026),
    "Nevada": ("Carson City", 39.1638, -119.7674),
    "New Hampshire": ("Concord", 43.2081, -71.5376),
    "New Jersey": ("Trenton", 40.2206, -74.7597),
    "New Mexico": ("Santa Fe", 35.6870, -105.9378),
    "New York": ("Albany", 42.6526, -73.7562),
    "North Carolina": ("Raleigh", 35.7796, -78.6382),
    "North Dakota": ("Bismarck", 46.8083, -100.7837),
    "Ohio": ("Columbus", 39.9612, -82.9988),
    "Oklahoma": ("Oklahoma City", 35.4676, -97.5164),
    "Oregon": ("Salem", 44.9429, -123.0351),
    "Pennsylvania": ("Harrisburg", 40.2732, -76.8867),
    "Rhode Island": ("Providence", 41.8240, -71.4128),
    "South Carolina": ("Columbia", 34.0007, -81.0348),
    "South Dakota": ("Pierre", 44.3683, -100.3510),
    "Tennessee": ("Nashville", 36.1627, -86.7816),
    "Texas": ("Austin", 30.2672, -97.7431),
    "Utah": ("Salt Lake City", 40.7608, -111.8910),
    "Vermont": ("Montpelier", 44.2601, -72.5754),
    "Virginia": ("Richmond", 37.5407, -77.4360),
    "Washington": ("Olympia", 47.0379, -122.9007),
    "West Virginia": ("Charleston", 38.3498, -81.6326),
    "Wisconsin": ("Madison", 43.0731, -89.4012),
    "Wyoming": ("Cheyenne", 41.1400, -104.8202),
}

# WMO weather codes -> plain english
WMO = {
    0: "Clear", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
    45: "Fog", 48: "Freezing fog",
    51: "Light drizzle", 53: "Drizzle", 55: "Heavy drizzle",
    56: "Freezing drizzle", 57: "Freezing drizzle",
    61: "Light rain", 63: "Rain", 65: "Heavy rain",
    66: "Freezing rain", 67: "Freezing rain",
    71: "Light snow", 73: "Snow", 75: "Heavy snow", 77: "Snow grains",
    80: "Light showers", 81: "Showers", 82: "Heavy showers",
    85: "Snow showers", 86: "Snow showers",
    95: "Thunderstorm", 96: "Thunderstorm w/ hail", 99: "Thunderstorm w/ hail",
}


def fetch_weather():
    caps = list(STATE_CAPITALS.items())
    lats = ",".join(str(lat) for _, (_, lat, _) in caps)
    lons = ",".join(str(lon) for _, (_, _, lon) in caps)
    r = requests.get(
        "https://api.open-meteo.com/v1/forecast",
        params={
            "latitude": lats,
            "longitude": lons,
            "current": "temperature_2m,weather_code,wind_speed_10m",
            "temperature_unit": "fahrenheit",
            "wind_speed_unit": "mph",
        },
        timeout=60,
    )
    r.raise_for_status()
    data = r.json()

    lines = []
    for (state, (capital, _, _)), d in zip(caps, data):
        c = d["current"]
        desc = WMO.get(c["weather_code"], f"code {c['weather_code']}")
        lines.append(
            f"{capital}, {state}: {c['temperature_2m']}°F, {desc}, wind {c['wind_speed_10m']} mph"
        )
    return "\n".join(lines)


# --- timezones: computed locally, no api needed ---

GMT_ZONES = {
    0: "London (winter), Accra, Reykjavik",
    1: "Berlin, Paris, Lagos",
    2: "Cairo, Athens, Johannesburg",
    3: "Moscow, Nairobi, Riyadh",
    4: "Dubai, Baku, Tbilisi",
    5: "Karachi, Tashkent, Yekaterinburg",
    6: "Dhaka, Almaty, Omsk",
    7: "Bangkok, Jakarta, Hanoi",
    8: "Beijing, Singapore, Perth",
    9: "Tokyo, Seoul, Yakutsk",
    10: "Sydney, Brisbane, Vladivostok",
}


def fetch_timezones():
    now = datetime.now(timezone.utc)
    lines = []
    for off in range(0, 11):
        local = now.astimezone(timezone(timedelta(hours=off)))
        lines.append(f"GMT+{off:<2} {local:%Y-%m-%d %H:%M}  — {GMT_ZONES[off]}")
    return "\n".join(lines)


# --- currency: open.er-api.com, USD/GBP/KWD cross rates ---

def fetch_currency():
    r = requests.get("https://open.er-api.com/v6/latest/USD", timeout=60)
    r.raise_for_status()
    d = r.json()
    rates = d["rates"]
    gbp, kwd = rates["GBP"], rates["KWD"]  # per 1 USD
    return "\n".join([
        f"Rates as of {d.get('time_last_update_utc', 'n/a')}",
        "",
        f"1 USD = {gbp:.4f} GBP = {kwd:.4f} KWD",
        f"1 GBP = {1/gbp:.4f} USD = {kwd/gbp:.4f} KWD",
        f"1 KWD = {1/kwd:.4f} USD = {gbp/kwd:.4f} GBP",
    ])


AGENTS = {
    "weather_agent": {
        "fetch": fetch_weather,
        "system": "You are a weather analyst. Summarise the weather readings you are given.",
    },
    "timezone_agent": {
        "fetch": fetch_timezones,
        "system": "You are a timezone assistant. Summarise the timezone list you are given.",
    },
    "currency_agent": {
        "fetch": fetch_currency,
        "system": "You are an FX assistant. Summarise the exchange rates you are given.",
    },
}


def call_llm(system, prompt):
    r = requests.post(
        OLLAMA_URL,
        json={
            "model": OLLAMA_MODEL,
            "system": system,
            "prompt": prompt,
            "stream": False,
        },
        timeout=600,
    )
    r.raise_for_status()
    return r.json()["response"]


def run_agent(agent, query="", summarize=False):
    a = AGENTS[agent]
    print(f"[{agent}] fetching")
    data = a["fetch"]()

    output = data
    if summarize:
        # feed the real data to the llm so it summarises facts instead of
        # inventing them (and can't refuse for "no real-time access")
        try:
            note = call_llm(a["system"], f"Data:\n{data}\n\nWrite a short summary.")
            output = f"{note.strip()}\n\n--- data ---\n{data}"
        except Exception as e:
            print(f"[{agent}] summary skipped: {e}")

    log_run(agent, query, output)
    print(f"[{agent}] done")
    return agent, output


def run_parallel(query="", summarize=False):
    results = {}
    with ThreadPoolExecutor(max_workers=len(AGENTS)) as pool:
        futures = {pool.submit(run_agent, a, query, summarize): a for a in AGENTS}
        for f in as_completed(futures):
            agent = futures[f]
            try:
                results[agent] = f.result()[1]
            except Exception as e:
                # one agent dying shouldn't take the others down
                print(f"[{agent}] failed: {e}")
                results[agent] = f"ERROR: {e}"
    return results


# --- tiny server so the dashboard can pull the blackboard over http ---

class Dashboard(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path in ("/", "/dashboard"):
            self._send(DASHBOARD.read_bytes(), "text/html")
        elif self.path.startswith("/api/blackboard"):
            body = json.dumps(get_all_latest()).encode()
            self._send(body, "application/json")
        else:
            self._send(b'{"error": "not found"}', "application/json", 404)

    def _send(self, body, ctype, status=200):
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


def serve(port=8000):
    init_db()
    server = ThreadingHTTPServer(("localhost", port), Dashboard)
    print(f"dashboard on http://localhost:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.server_close()


def main():
    p = argparse.ArgumentParser()
    p.add_argument("query", nargs="?", default="")
    p.add_argument("--agent", choices=list(AGENTS), help="run just one agent")
    p.add_argument("--summarize", action="store_true", help="add an llm summary on top of the data")
    p.add_argument("--serve", action="store_true", help="start the dashboard server")
    p.add_argument("--port", type=int, default=8000)
    args = p.parse_args()

    init_db()

    if args.serve:
        serve(args.port)
        return

    if args.agent:
        agent, output = run_agent(args.agent, args.query, args.summarize)
        results = {agent: output}
    else:
        results = run_parallel(args.query, args.summarize)

    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
