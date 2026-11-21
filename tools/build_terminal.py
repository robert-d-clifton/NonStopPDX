"""Build data/terminal.json, the shapes and places behind the Inside PDX page, from OpenStreetMap.

    python3 tools/build_terminal.py            # fetch from the Overpass API and write the file
    python3 tools/build_terminal.py --offline  # rebuild from the last raw download in .cache/

Shapes are projected to meters around the main terminal (x east, y south) so the page can draw
them without a map library. Each place is given an area: "main" for the main terminal, a concourse
letter, or "outside". Standard library only. Data © OpenStreetMap contributors, ODbL.
"""

from __future__ import annotations

import json
import math
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "terminal.json"
RAW = ROOT / ".cache" / "terminal-osm.json"
OVERPASS = "https://overpass-api.de/api/interpreter"
QUERY = """[out:json][timeout:90];
(
  way["aeroway"="terminal"](45.580,-122.610,45.600,-122.575);
  relation["aeroway"="terminal"](45.580,-122.610,45.600,-122.575);
  way["building"="parking"](45.583,-122.603,45.595,-122.580);
  way["building"]["name"~"Control Tower"](45.583,-122.603,45.595,-122.580);
  node["aeroway"="gate"](45.580,-122.610,45.600,-122.575);
  nwr["amenity"](45.584,-122.600,45.594,-122.583);
  nwr["shop"](45.584,-122.600,45.594,-122.583);
  nwr["tourism"](45.584,-122.600,45.594,-122.583);
  nwr["leisure"](45.584,-122.600,45.594,-122.583);
  node["railway"="halt"](45.584,-122.600,45.594,-122.583);
);
out body center;
>;
out skel qt;"""

LAT0, LON0 = 45.5887, -122.5933
NAMES = {
    "Portland International Airport Main Terminal": "Main terminal",
    "Portland International Airport Control Tower": "Control tower",
    "Short Term Parking Garage P1": "P1",
    "Long Term Parking Garage P2": "P2",
    "Long Term Parking Garage P3": "P3",
}
CATEGORY = {
    "food": {"restaurant", "fast_food", "cafe", "pub", "bar", "alcohol", "tea", "ice_cream", "food_court", "coffee"},
    "shops": {"gift", "clothes", "books", "convenience", "jewelry", "electronics", "kiosk", "shoes", "chocolate",
              "cosmetics", "newsagent", "bag", "outdoor", "variety_store", "toys"},
    "see": {"cinema", "artwork", "playground", "garden", "fountain", "museum", "attraction", "arts_centre"},
    "services": {"lounge", "information", "bureau_de_change", "dog_park", "lactation_room", "shoe_shine",
                 "clinic", "pharmacy", "massage", "beauty", "hairdresser", "place_of_worship"},
    "transit": {"halt", "station"},
}
RENAME = {
    "Portland International Airport": "MAX Red Line station",
    "Sentinels;Habitat Tiles": "Sentinels and Habitat Tiles",
    "CXI - Ccurrency Exchange International": "Currency Exchange International",
    "Your NW Travel Mart": "Your Northwest Travel Mart",
    "USO Northwest - PDX": "USO Northwest",
}


def meters(lat: float, lon: float) -> list[float]:
    x = (lon - LON0) * 111320 * math.cos(math.radians(LAT0))
    y = (lat - LAT0) * 110540
    return [round(x, 1), round(-y, 1)]


def inside(pt, poly) -> bool:
    hit = False
    j = len(poly) - 1
    for i in range(len(poly)):
        (xi, yi), (xj, yj) = poly[i], poly[j]
        if (yi > pt[1]) != (yj > pt[1]) and pt[0] < (xj - xi) * (pt[1] - yi) / (yj - yi) + xi:
            hit = not hit
        j = i
    return hit


def category(tags: dict) -> str | None:
    kind = tags.get("railway") or tags.get("amenity") or tags.get("shop") or tags.get("tourism") or tags.get("leisure")
    for name, kinds in CATEGORY.items():
        if kind in kinds:
            return name
    return None


def fetch() -> dict:
    body = urllib.parse.urlencode({"data": QUERY}).encode()
    req = urllib.request.Request(OVERPASS, data=body, headers={"User-Agent": "NonStopPDX terminal builder"})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                raw = resp.read()
            break
        except urllib.error.HTTPError as e:  # Overpass answers 429 or 502 when busy
            if attempt == 3 or e.code not in (429, 502, 503, 504):
                raise
            time.sleep(10 * 2 ** attempt)
    RAW.parent.mkdir(exist_ok=True)
    RAW.write_bytes(raw)
    return json.loads(raw)


def build(osm: dict) -> dict:
    els = osm["elements"]
    nodes = {e["id"]: (e["lat"], e["lon"]) for e in els if e["type"] == "node" and "lat" in e}
    ways = {e["id"]: e for e in els if e["type"] == "way"}

    def ring(ids):
        return [meters(*nodes[i]) for i in ids if i in nodes]

    def stitch(wids):
        segs = [list(ways[w]["nodes"]) for w in wids if w in ways]
        out = segs.pop(0)
        while segs:
            for i, s in enumerate(segs):
                if s[0] == out[-1]:
                    out += s[1:]
                elif s[-1] == out[-1]:
                    out += s[::-1][1:]
                else:
                    continue
                segs.pop(i)
                break
            else:
                break
        return out

    shapes = []
    for e in els:
        tags = e.get("tags", {})
        name = NAMES.get(tags.get("name", ""), tags.get("name", ""))
        if tags.get("aeroway") == "terminal" and tags.get("name") != "GA TERMINAL":
            kind = "terminal"
        elif tags.get("building") == "parking":
            kind = "garage"
        elif name == "Control tower":
            kind = "tower"
        else:
            continue
        if e["type"] == "way":
            pts = ring(e["nodes"])
        elif e["type"] == "relation":
            pts = ring(stitch([m["ref"] for m in e["members"] if m["type"] == "way" and m.get("role") == "outer"]))
        else:
            continue
        shapes.append({"kind": kind, "name": name, "pts": [[round(x), round(y)] for x, y in pts]})
    shapes.sort(key=lambda s: (s["kind"], s["name"]))

    areas = [(s["name"][-1] if s["name"].startswith("Concourse") else "main", s["pts"])
             for s in shapes if s["kind"] == "terminal"]
    gates = sorted(
        ({"ref": e["tags"]["ref"], "p": [round(v) for v in meters(e["lat"], e["lon"])]}
         for e in els if e["type"] == "node" and e.get("tags", {}).get("aeroway") == "gate" and e["tags"].get("ref")),
        key=lambda g: (g["ref"][0], int("".join(c for c in g["ref"][1:] if c.isdigit()) or 0), g["ref"]),
    )

    places, seen = [], set()
    for e in els:
        tags = e.get("tags", {})
        cat = category(tags)
        if not cat or not tags.get("name"):
            continue
        lat = e.get("lat", e.get("center", {}).get("lat"))
        lon = e.get("lon", e.get("center", {}).get("lon"))
        if lat is None:
            continue
        p = meters(lat, lon)
        area = next((a for a, poly in areas if inside(p, poly)), "outside")
        name = RENAME.get(tags["name"], tags["name"])
        if (name, area) in seen:
            continue
        seen.add((name, area))
        kind = tags.get("railway") or tags.get("amenity") or tags.get("shop") or tags.get("tourism") or tags.get("leisure")
        places.append({"name": name, "kind": kind, "category": cat, "area": area, "p": [round(v) for v in p]})
    places.sort(key=lambda pl: (pl["area"], pl["category"], pl["name"].lower()))
    return {"_source": "© OpenStreetMap contributors, ODbL. Built by tools/build_terminal.py; edit that, not this file.",
            "shapes": shapes, "gates": gates, "places": places}


def main() -> None:
    osm = json.loads(RAW.read_text()) if "--offline" in sys.argv else fetch()
    data = build(osm)
    OUT.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    by_area = {}
    for pl in data["places"]:
        by_area[pl["area"]] = by_area.get(pl["area"], 0) + 1
    print(f"Wrote {OUT.relative_to(ROOT)}: {len(data['shapes'])} shapes, {len(data['gates'])} gates, places by area {by_area}")


if __name__ == "__main__":
    main()
