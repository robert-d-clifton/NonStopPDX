from django.db.models import Prefetch
from django.shortcuts import render

from .display import board_rows, short_airline
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
