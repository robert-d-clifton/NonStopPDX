"""The Inside PDX page's data: building shapes and places (data/terminal.json, from OpenStreetMap)
and which airlines use each concourse (data/concourses.json, kept by hand)."""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

from django.conf import settings

CATEGORIES = [("food", "Food and drink"), ("shops", "Shops"), ("see", "Things to see"), ("services", "Lounges and services")]
AREA_NAMES = {"main": "Main terminal", "B": "Concourse B", "C": "Concourse C", "D": "Concourse D", "E": "Concourse E"}


@lru_cache(maxsize=4)
def _read(path: str, mtime: float) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def load(path: Path) -> dict:
    return _read(str(path), path.stat().st_mtime)


def _gate_number(ref: str) -> tuple:
    m = re.match(r"([A-Z])(\d+)(.*)", ref)
    return (m.group(1), int(m.group(2)), m.group(3)) if m else (ref, 0, "")


def gate_span(refs: list[str]) -> str:
    """'C4 to C23' for a concourse's gates, by number."""
    ordered = sorted(refs, key=_gate_number)
    if not ordered:
        return ""
    return ordered[0] if len(ordered) == 1 else f"{ordered[0]} to {ordered[-1]}"


def inside_pdx(airlines_by_slug: dict) -> dict:
    """Everything the page needs: one entry per area in walking order, plus the map payload."""
    terminal = load(settings.TERMINAL_FILE)
    hand = load(settings.CONCOURSES_FILE)
    concourses = hand["concourses"]
    areas = []
    for key, title in AREA_NAMES.items():
        places = [p for p in terminal["places"] if p["area"] == key]
        groups = [(label, [p["name"] for p in places if p["category"] == cat]) for cat, label in CATEGORIES]
        gates = [g["ref"] for g in terminal["gates"] if g["ref"].startswith(key)] if key != "main" else []
        airlines = []
        for entry in concourses.get(key, {}).get("airlines", []):
            airline = airlines_by_slug.get(entry["slug"])
            if airline:
                airlines.append({"name": airline.name, "slug": airline.slug, "note": entry.get("note", ""),
                                 "checked": entry.get("checked", False)})
        areas.append({
            "key": key,
            "anchor": "main-terminal" if key == "main" else f"concourse-{key.lower()}",
            "title": title,
            "gates": len(gates),
            "gate_span": gate_span(gates),
            "airlines": airlines,
            "groups": [(label, names) for label, names in groups if names],
            "count": len(places),
        })
    getting_here = [p["name"] for p in terminal["places"] if p["area"] == "outside"]
    map_data = {
        "shapes": terminal["shapes"],
        "gates": terminal["gates"],
        "rail": terminal.get("rail", []),
        "noAircraft": hand.get("no_aircraft", []),
        "pins": [{"name": p["name"], "p": p["p"]} for p in terminal["places"] if p["category"] == "transit"],
        "areas": {a["key"]: {"title": a["title"], "anchor": a["anchor"], "gateSpan": a["gate_span"],
                             "airlines": [x["name"] + (f" ({x['note']})" if x["note"] else "") for x in a["airlines"]]}
                  for a in areas},
    }
    return {"areas": areas, "getting_here": getting_here, "map_data": map_data}
