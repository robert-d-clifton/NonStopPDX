"""Build the map geography in static/geo/ from Natural Earth.

Run from the project root (needs network, standard library only):
    python3 tools/build_geo.py

Writes:
  static/geo/world-110m.json          world land, lakes, country lines, and US and Canada state lines
  static/geo/north-america-50m.json   finer North American land, lakes, country lines, and US, Canada and Mexico state lines

Natural Earth is public domain. The version is pinned so the files rebuild the same way.
"""

from __future__ import annotations

import json
import urllib.request
from pathlib import Path

NE = "https://cdn.jsdelivr.net/gh/nvkelso/natural-earth-vector@v5.1.2/geojson/{}.geojson"
OUT = Path(__file__).resolve().parent.parent / "static" / "geo"
NORTH_AMERICA = (-170, 10, -50, 72)  # west, south, east, north: Alaska and Hawaii to the Caribbean


def fetch(name: str) -> dict:
    req = urllib.request.Request(NE.format(name), headers={"User-Agent": "NonStopPDX/0.1 (personal hobby project)"})
    with urllib.request.urlopen(req, timeout=180) as resp:
        return json.load(resp)


def prop(feature: dict, key: str):
    p = feature["properties"]
    return p.get(key, p.get(key.upper()))


def rings(geometry: dict) -> list:
    t, c = geometry["type"], geometry["coordinates"]
    if t == "LineString":
        return [c]
    if t in ("MultiLineString", "Polygon"):
        return c
    return [ring for poly in c for ring in poly]  # MultiPolygon


def rounded(coords, places: int):
    if isinstance(coords[0], list):
        return [rounded(c, places) for c in coords]
    return [round(coords[0], places), round(coords[1], places)]


def collection(name: str, places: int, keep=lambda f: True, box=None) -> dict:
    features = []
    for f in fetch(name)["features"]:
        g = f.get("geometry")
        if not g or not keep(f):
            continue
        if box and not any(box[0] <= x <= box[2] and box[1] <= y <= box[3] for ring in rings(g) for x, y in ring):
            continue
        features.append({"type": "Feature", "properties": {},
                         "geometry": {"type": g["type"], "coordinates": rounded(g["coordinates"], places)}})
    return {"type": "FeatureCollection", "features": features}


def write(name: str, data: dict) -> None:
    path = OUT / name
    path.write_text(json.dumps(data, separators=(",", ":")), encoding="utf-8")
    counts = ", ".join(f"{k} {len(v['features'])}" for k, v in data.items())
    print(f"{path.name}: {path.stat().st_size / 1024:.0f} KB ({counts})")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    write("world-110m.json", {
        "land": collection("ne_110m_land", 2),
        "lakes": collection("ne_110m_lakes", 2, keep=lambda f: (prop(f, "scalerank") or 99) <= 1),
        "countries": collection("ne_110m_admin_0_boundary_lines_land", 2),
        "states": collection("ne_110m_admin_1_states_provinces_lines", 2),
    })
    write("north-america-50m.json", {
        "land": collection("ne_50m_land", 3, box=NORTH_AMERICA),
        "lakes": collection("ne_50m_lakes", 3, keep=lambda f: (prop(f, "scalerank") or 99) <= 4, box=NORTH_AMERICA),
        "countries": collection("ne_50m_admin_0_boundary_lines_land", 3, box=NORTH_AMERICA),
        "states": collection("ne_50m_admin_1_states_provinces_lines", 2,
                             keep=lambda f: prop(f, "adm0_a3") in ("USA", "CAN", "MEX"), box=NORTH_AMERICA),
    })


if __name__ == "__main__":
    main()
