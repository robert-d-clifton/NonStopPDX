"""How routes read on the site: short names, flight time estimates and service labels."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

SHORT_NAMES = {
    "HNL": "Honolulu", "LIH": "Lihue", "FRA": "Frankfurt", "CVG": "Cincinnati", "IAD": "Washington Dulles",
    "DCA": "Washington National", "BFI": "Seattle Boeing Field", "DFW": "Dallas Fort Worth", "MDW": "Chicago Midway",
    "ORD": "Chicago O'Hare", "SJD": "Los Cabos", "DAL": "Dallas Love Field",
}


def short_name(airport) -> str:
    return SHORT_NAMES.get(airport.iata) or airport.city.split(",")[0]


def short_airline(name: str) -> str:
    return name.replace(" Airlines", "").replace(" Air Lines", "")


def flight_minutes(miles: int | None) -> int | None:
    """A rough estimate until real schedules arrive: 480 mph plus half an hour, to the nearest 5 minutes."""
    if miles is None:
        return None
    return round((miles / 8 + 30) / 5) * 5


def hours_minutes(minutes: int | None) -> str:
    if minutes is None:
        return ""
    h, m = divmod(minutes, 60)
    return f"{h}h {m:02d}m" if h else f"{m}m"


def _month_day(text: str) -> str:
    try:
        return datetime.strptime(text.strip(), "%B %d, %Y").strftime("%b %-d")
    except ValueError:
        return text


@dataclass
class Service:
    label: str
    css: str  # yr, se or soon


def service_for(routes) -> Service:
    """Starting soon beats year round, which beats seasonal."""
    for r in routes:
        if r.begins:
            return Service("Starts " + _month_day(r.begins), "soon")
        if r.resumes:
            return Service("Back " + _month_day(r.resumes), "soon")
    if any(r.kind == "year-round" for r in routes):
        return Service("Year round", "yr")
    return Service("Seasonal", "se")


@dataclass
class BoardRow:
    airport: object
    name: str
    airlines: str
    miles: int | None
    flight: str
    service: Service
    region: object
    starting_soon: bool
    seasonal: bool


def board_rows(airports) -> list[BoardRow]:
    rows = []
    for a in airports:
        routes = list(a.active_routes)
        service = service_for(routes)
        rows.append(BoardRow(
            airport=a,
            name=short_name(a),
            airlines=", ".join(short_airline(r.airline.name) for r in routes),
            miles=a.distance_mi,
            flight=hours_minutes(flight_minutes(a.distance_mi)),
            service=service,
            region=a.region_group,
            starting_soon=service.css == "soon",
            seasonal=not any(r.kind == "year-round" for r in routes),
        ))
    return rows
