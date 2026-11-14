from django.db.models import Prefetch
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from stories.models import Story

from .display import (board_rows, flight_minutes, google_flights_url, hours_minutes, route_note, service_for,
                      short_airline, short_name)
from .models import Airline, Airport, Route, SyncRun

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
        "map_label": f"Map of the {len(all_rows)} nonstop routes from PDX. The departures list below has every destination.",
        "show_west": True,
    })


def destination(request, code):
    if code != code.lower():
        return redirect("routes:destination", code=code.lower(), permanent=True)
    airport = get_object_or_404(
        Airport.objects.prefetch_related(Prefetch("routes", queryset=Route.objects.select_related("airline__parent").order_by("airline__name"))),
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
        "active": [{"airline": r.airline.name, "note": route_note(r), "slug": r.airline.main.slug} for r in active],
        "last_flown": max((r.last_seen for r in routes if r.last_seen), default=None),
        "service": service,
        "flight": hours_minutes(flight_minutes(airport.distance_mi)),
        "story": story,
        "snapshot": snapshot,
        "fares_url": google_flights_url(airport.iata),
        "route_point": point,
    })


def _airline_rows(routes, main):
    """One board row per destination. When a regional brand flies it, say so: "United Express" when only the
    brand does, "Also United Express" when the main airline does too."""
    by_dest = {}
    for r in routes:
        by_dest.setdefault(r.destination.pk, []).append(r)
    rows = []
    for dest_routes in by_dest.values():
        a = dest_routes[0].destination
        brands = sorted({r.airline.name for r in dest_routes if r.airline_id != main.pk})
        main_flies = any(r.airline_id == main.pk for r in dest_routes)
        brand = ", ".join(brands)
        rows.append({
            "airport": a,
            "name": short_name(a),
            "miles": a.distance_mi,
            "flight": hours_minutes(flight_minutes(a.distance_mi)),
            "service": service_for(dest_routes),
            "region": a.region_group,
            "brand": ("Also " + brand) if brand and main_flies else brand,
            "seasonal": not any(r.kind == "year-round" for r in dest_routes),
        })
    return sorted(rows, key=lambda row: row["name"])


def _airline_points(rows) -> list[dict]:
    points = []
    for row in rows:
        a = row["airport"]
        if a.latitude is None or a.longitude is None:
            continue
        points.append({
            "code": a.iata, "name": row["name"], "lat": round(a.latitude, 4), "lon": round(a.longitude, 4),
            "miles": row["miles"], "flight": row["flight"], "airlines": [row["brand"]] if row["brand"] else [],
            "service": row["service"].label, "yearRound": not row["seasonal"],
            "url": reverse("routes:destination", args=[a.iata.lower()]),
        })
    return points


def airlines(request):
    mains = Airline.objects.filter(parent__isnull=True).prefetch_related("brands")
    entries = []
    for airline in mains:
        routes = Route.objects.filter(active=True, airline__in=airline.family()).select_related("destination")
        dests = {r.destination for r in routes}
        if not dests:
            continue
        entries.append({
            "airline": airline,
            "destinations": len(dests),
            "seasonal": sum(1 for r in routes if r.kind != "year-round"),
            "international": sum(1 for d in dests if d.international),
            "brands": [b.name for b in airline.brands.all() if Route.objects.filter(active=True, airline=b).exists()],
        })
    entries.sort(key=lambda e: (-e["destinations"], e["airline"].name))
    return render(request, "routes/airlines.html", {"entries": entries})


def airline(request, slug):
    airline = get_object_or_404(Airline.objects.select_related("parent"), slug=slug)
    if airline.parent:  # regional brands live on their main airline's page
        return redirect("routes:airline", slug=airline.parent.slug, permanent=True)
    routes = list(Route.objects.filter(active=True, airline__in=airline.family())
                  .select_related("destination", "airline").order_by("destination__city"))
    rows = _airline_rows(routes, airline)
    farthest = max((r for r in rows if r["miles"] is not None), key=lambda r: r["miles"], default=None)
    points = _airline_points(rows)
    return render(request, "routes/airline.html", {
        "airline": airline,
        "rows": rows,
        "destinations": len(rows),
        "seasonal": sum(1 for r in rows if r["seasonal"]),
        "international": len({r["airport"].pk for r in rows if r["airport"].international}),
        "farthest": farthest,
        "has_brands": any(r["brand"] for r in rows),
        "map_points": points,
        "show_west": sum(1 for p in points if p["miles"] is not None and p["miles"] < 1150) >= 2,
    })
