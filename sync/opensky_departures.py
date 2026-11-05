"""Pull a week of real KPDX departures from OpenSky and compare them to our route list.

Needs OPENSKY_CLIENT_ID and OPENSKY_CLIENT_SECRET in .env at the project root.

Run from the project root, after sync.pdx_routes has written data/routes.json:
    python3 -m sync.opensky_departures

Raw flights and the comparison go in data/raw/opensky/, which git ignores. Arrival
airports are OpenSky's estimates, so treat the comparison as a prompt for a manual
look against FlyPDX, not as proof a route exists or doesn't.

Standard library only.
"""

from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sync.pdx_routes import DATA_DIR, ROOT, USER_AGENT, load_ourairports

TOKEN_URL = "https://auth.opensky-network.org/auth/realms/opensky-network/protocol/openid-connect/token"
DEPARTURES_URL = "https://opensky-network.org/api/flights/departure"
ORIGIN_ICAO = "KPDX"
ENV_FILE = ROOT / ".env"
RAW_DIR = DATA_DIR / "raw" / "opensky"
WEEK_DAYS = 7

# Airline flights use a three letter ICAO prefix then a number, like ASA123.
# Private flights use registrations like N123AB, which this leaves out.
AIRLINE_CALLSIGN_RE = re.compile(r"^[A-Z]{3}\d")


def parse_env(text: str) -> dict[str, str]:
    """Read KEY=value lines, ignoring comments and one pair of matching quotes."""
    out = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        out[key.strip()] = value
    return out


def load_credentials(path: Path = ENV_FILE) -> tuple[str, str]:
    values = parse_env(path.read_text(encoding="utf-8")) if path.exists() else {}
    client_id = os.environ.get("OPENSKY_CLIENT_ID") or values.get("OPENSKY_CLIENT_ID")
    secret = os.environ.get("OPENSKY_CLIENT_SECRET") or values.get("OPENSKY_CLIENT_SECRET")
    if not client_id or not secret:
        raise SystemExit("OPENSKY_CLIENT_ID and OPENSKY_CLIENT_SECRET are required in .env")
    return client_id, secret


def fetch_token(client_id: str, secret: str) -> str:
    body = urllib.parse.urlencode({
        "grant_type": "client_credentials", "client_id": client_id, "client_secret": secret,
    }).encode()
    req = urllib.request.Request(TOKEN_URL, data=body, headers={
        "User-Agent": USER_AGENT, "Content-Type": "application/x-www-form-urlencoded",
    })
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.load(resp)["access_token"]
    except urllib.error.HTTPError as e:
        raise SystemExit(f"OpenSky rejected the credentials (HTTP {e.code}). Check the values in .env.") from None


def day_windows(now: datetime, days: int = WEEK_DAYS) -> list[tuple[int, int]]:
    """One (begin, end) pair per complete UTC day, oldest first, ending at last midnight."""
    midnight = now.astimezone(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    starts = [midnight - timedelta(days=n) for n in range(days, 0, -1)]
    return [(int(s.timestamp()), int((s + timedelta(days=1)).timestamp())) for s in starts]


def fetch_departures(token: str, begin: int, end: int) -> tuple[list[dict], str | None]:
    """Flights for one window, plus credits remaining if the API reports them."""
    query = urllib.parse.urlencode({"airport": ORIGIN_ICAO, "begin": begin, "end": end})
    req = urllib.request.Request(f"{DEPARTURES_URL}?{query}", headers={
        "User-Agent": USER_AGENT, "Authorization": f"Bearer {token}",
    })
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return json.load(resp), resp.headers.get("X-Rate-Limit-Remaining")
    except urllib.error.HTTPError as e:
        if e.code == 404:       # OpenSky's way of saying no flights in this window
            return [], e.headers.get("X-Rate-Limit-Remaining")
        if e.code == 429:
            wait = e.headers.get("X-Rate-Limit-Retry-After-Seconds", "unknown")
            raise SystemExit(f"OpenSky credits are used up. Retry after {wait} seconds.") from None
        raise SystemExit(f"OpenSky returned HTTP {e.code} for the departures request.") from None


def icao_to_iata(airports: list[dict]) -> dict[str, str]:
    out = {}
    for a in airports:
        if not a.get("iata_code"):
            continue
        for field in ("ident", "gps_code", "icao_code"):
            if a.get(field):
                out.setdefault(a[field], a["iata_code"])
    return out


def compare(flights: list[dict], destinations: list[dict], iata_by_icao: dict[str, str]) -> dict:
    """Line up observed departures against our list, at the destination level."""
    seen = {}
    for f in flights:
        seen[(f.get("icao24"), f.get("firstSeen"))] = f
    flights = list(seen.values())

    observed: Counter = Counter()
    prefixes: dict[str, Counter] = {}
    no_estimate = other = 0
    for f in flights:
        callsign = (f.get("callsign") or "").strip()
        if not AIRLINE_CALLSIGN_RE.match(callsign):
            other += 1
            continue
        arrival = f.get("estArrivalAirport")
        if not arrival:
            no_estimate += 1
            continue
        code = iata_by_icao.get(arrival, arrival)
        observed[code] += 1
        prefixes.setdefault(code, Counter())[callsign[:3]] += 1

    listed = {d["iata"]: d for d in destinations if d.get("iata")}
    rows = {
        "confirmed": {c: observed[c] for c in sorted(listed) if observed[c]},
        "year_round_not_seen": sorted(c for c, d in listed.items() if d["year_round"] and not observed[c]),
        "seasonal_not_seen": sorted(c for c, d in listed.items() if not d["year_round"] and not observed[c]),
        "seen_not_listed": [
            {"airport": c, "departures": n, "callsign_prefixes": dict(prefixes[c])}
            for c, n in observed.most_common() if c not in listed and c != "PDX"
        ],
    }
    return {
        "total_flights": len(flights),
        "airline_flights_matched": sum(observed.values()),
        "airline_flights_without_arrival_estimate": no_estimate,
        "other_flights_ignored": other,
        **rows,
    }


def main() -> int:
    routes = json.loads((DATA_DIR / "routes.json").read_text(encoding="utf-8"))
    token = fetch_token(*load_credentials())

    flights, per_day, remaining = [], {}, None
    windows = day_windows(datetime.now(timezone.utc))
    for begin, end in windows:
        day = datetime.fromtimestamp(begin, timezone.utc).date().isoformat()
        batch, left = fetch_departures(token, begin, end)
        flights.extend(batch)
        per_day[day] = len(batch)
        remaining = left or remaining

    result = compare(flights, routes["destinations"], icao_to_iata(load_ourairports()))
    result["departures_per_day"] = per_day
    result["routes_generated_at"] = routes.get("generated_at")

    first, last = min(per_day), max(per_day)
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    (RAW_DIR / f"departures_{first}_{last}.json").write_text(json.dumps(flights) + "\n", encoding="utf-8")
    report = RAW_DIR / f"comparison_{first}_{last}.json"
    report.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

    print(f"{result['total_flights']} departures from {ORIGIN_ICAO}, {first} to {last} UTC")
    print("Per day:", ", ".join(f"{d[5:]}: {n}" for d, n in per_day.items()))
    print(f"Airline flights matched to an airport: {result['airline_flights_matched']}; "
          f"no arrival estimate: {result['airline_flights_without_arrival_estimate']}; "
          f"other flights ignored: {result['other_flights_ignored']}")
    print(f"Listed destinations seen: {len(result['confirmed'])} of {routes['destination_count']}")
    print("Year round, not seen:", ", ".join(result["year_round_not_seen"]) or "none")
    print("Seasonal, not seen:", ", ".join(result["seasonal_not_seen"]) or "none")
    print("Seen, not listed:")
    for row in result["seen_not_listed"]:
        print(f"  {row['airport']}: {row['departures']} ({', '.join(row['callsign_prefixes'])})")
    if remaining:
        print(f"Flight credits remaining: {remaining}")
    print(f"Wrote {report}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
