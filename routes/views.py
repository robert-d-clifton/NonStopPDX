from django.db.models import Prefetch
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from stories.models import Story

from .display import (board_rows, flight_minutes, google_flights_url, hours_minutes, route_note, service_for,
                      short_airline, short_name)
from .models import Airport, Route, SyncRun

FILTERS = {
    "az": ("A to Z", lambda rows: sorted(rows, key=lambda r: r.name)),
    "far": ("Farthest", lambda rows: sorted(rows, key=lambda r: -(r.miles or 0))),
    "seasonal": ("Seasonal", lambda rows: sorted((r for r in rows if r.seasonal), key=lambda r: r.name)),
    "intl": ("International", lambda rows: sorted((r for r in rows if r.airport.international), key=lambda r: r.name)),
    "soon": ("Starting soon", lambda rows: sorted((r for r in rows if r.starting_soon), key=lambda r: r.name)),
}


def map_points(rows) -> list[dict]:
    """The small payload the overview map needs, one entry per destination with coordinates."""
    points = []
    for r in rows:
        a = r.airport
        if a.latitude is None or a.longitude is None:
            continue
        points.append({
            "code": a.iata,
            "name": r.name,
            "lat": round(a.latitude, 4),
            "lon": round(a.longitude, 4),
            "miles": r.miles,
            "flight": r.flight,
            "airlines": [short_airline(rt.airline.name) for rt in a.active_routes],
            "service": r.service.label,
            "yearRound": not r.seasonal,
            "url": reverse("routes:destination", args=[a.iata.lower()]),
        })
    return points


def home(request):
    current = request.GET.get("f", "az")
    if current not in FILTERS:
        current = "az"
    airports = Airport.objects.filter(is_destination=True).prefetch_related(
        Prefetch("routes", queryset=Route.objects.filter(active=True).select_related("airline").order_by("airline__name"),
                 to_attr="active_routes")
    )
    all_rows = board_rows(airports)
    rows = FILTERS[current][1](all_rows)
    last_sync = SyncRun.objects.filter(kind="routes", ok=True).order_by("-finished_at").first()
    return render(request, "routes/home.html", {
        "rows": rows,
        "total": len(all_rows),
        "filters": [(key, label) for key, (label, _) in FILTERS.items()],
        "current": current,
        "last_sync": last_sync,
        "map_points": map_points(all_rows),
    })


def destination(request, code):
    if code != code.lower():
        return redirect("routes:destination", code=code.lower(), permanent=True)
    airport = get_object_or_404(
        Airport.objects.prefetch_related(Prefetch("routes", queryset=Route.objects.select_related("airline").order_by("airline__name"))),
        iata=code.upper(),
    )
    routes = list(airport.routes.all())
    if not routes:  # an airport we know about, but never as a PDX nonstop
        raise Http404("No nonstop from PDX")
    active = [r for r in routes if r.active]
    name = short_name(airport)
    region = airport.region_group
    service = service_for(active) if active else None
    year_round = any(r.kind == "year-round" for r in active)
    story = Story.objects.filter(airport=airport).first()
    snapshot = airport.snapshots.filter(source="opensky").order_by("-week_start").first()
    point = None
    if airport.latitude is not None and airport.longitude is not None:
        point = {"code": airport.iata, "name": name, "lat": airport.latitude, "lon": airport.longitude,
                 "miles": airport.distance_mi, "yearRound": year_round, "regionColor": region.color}
    return render(request, "routes/destination.html", {
        "airport": airport,
        "name": name,
        "region": region,
        "active": [{"airline": r.airline.name, "note": route_note(r)} for r in active],
        "last_flown": max((r.last_seen for r in routes if r.last_seen), default=None),
        "service": service,
        "flight": hours_minutes(flight_minutes(airport.distance_mi)),
        "story": story,
        "snapshot": snapshot,
        "fares_url": google_flights_url(airport.iata),
        "route_point": point,
    })
