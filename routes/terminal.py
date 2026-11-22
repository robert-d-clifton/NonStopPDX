"""The Inside PDX page's data: building shapes, art and lounges (data/terminal.json, from OpenStreetMap),
shops, restaurants and services (data/places.json, from FlyPDX by hand) and which airlines use each
concourse (data/concourses.json, kept by hand)."""

from __future__ import annotations

import json
import re
from datetime import date
from functools import lru_cache
from pathlib import Path

from django.conf import settings

CATEGORIES = [("food", "Food and drink"), ("shops", "Shops"), ("see", "Things to see"), ("services", "Lounges and services")]
AREA_NAMES = {"main": "Main terminal", "B": "Concourse B", "C": "Concourse C", "D": "Concourse D", "E": "Concourse E"}
KIND_CATEGORY = {"restaurant": "food", "shop": "shops", "service": "services"}
# the main terminal's halls in walking order, and whether they're before security
HALLS = [("Ticket Hall", True), ("Mezzanine", True), ("North Concession Hall", False), ("South Concession Hall", False), ("Baggage Claim", True)]


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


def _osm_extras(terminal: dict, area: str, flypdx_names: set[str]) -> list[tuple[str, str]]:
    """Art, play areas and airline lounges from OpenStreetMap, which FlyPDX's shop list doesn't carry."""
    out = []
    for p in terminal["places"]:
        if p["area"] != area or p["name"] in flypdx_names:
            continue
        if p["category"] == "see" and p["kind"] != "cinema":
            out.append(("see", p["name"]))
        elif p["kind"] == "lounge":
            out.append(("services", p["name"]))
    return out


def inside_pdx(airlines_by_slug: dict) -> dict:
    """Everything the page needs: one entry per area in walking order, plus the map payload."""
    terminal = load(settings.TERMINAL_FILE)
    hand = load(settings.CONCOURSES_FILE)
    concourses = hand["concourses"]
    shown = [p for p in load(settings.PLACES_FILE)["places"] if p.get("show", True)]
    flypdx_names = {p["name"] for p in shown}
    areas = []
    for key, title in AREA_NAMES.items():
        if key == "main":
            groups = []
            for hall, before in HALLS:
                here = [p for p in shown if hall in p["where"]]
                order = {"restaurant": 0, "shop": 1, "service": 2}
                names = [p["name"] for p in sorted(here, key=lambda p: (order[p["kind"]], p["name"].lower()))]
                if names:
                    groups.append((hall, names, "Before security" if before else "After security"))
            extras = [name for _, name in _osm_extras(terminal, "main", flypdx_names)]
            if extras:
                groups.append(("Lounges", extras, ""))
        else:
            items = [("see" if p.get("see") else KIND_CATEGORY[p["kind"]], p["name"]) for p in shown if title in p["where"]]
            items += _osm_extras(terminal, key, flypdx_names)
            groups = [(label, sorted({n for c, n in items if c == cat}, key=str.lower), "") for cat, label in CATEGORIES]
            groups = [g for g in groups if g[1]]
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
            "groups": groups,
        })
    getting_here = [p["name"] for p in terminal["places"] if p["area"] == "outside"]
    map_data = {
        "shapes": terminal["shapes"],
        "gates": terminal["gates"],
        "rail": terminal.get("rail", []),
        "noAircraft": hand.get("no_aircraft", []),
        "groundBoarding": hand.get("ground_boarding", []),
        "pins": [{"name": p["name"], "p": p["p"]} for p in terminal["places"] if p["category"] == "transit"],
        "areas": {a["key"]: {"title": a["title"], "anchor": a["anchor"], "gateSpan": a["gate_span"],
                             "airlines": [x["name"] + (f" ({x['note']})" if x["note"] else "") for x in a["airlines"]]}
                  for a in areas},
    }
    as_of = load(settings.PLACES_FILE).get("as_of", "")
    places_as_of = date.fromisoformat(as_of).strftime("%B %-d, %Y") if as_of else ""
    return {"areas": areas, "getting_here": getting_here, "map_data": map_data, "places_as_of": places_as_of}
