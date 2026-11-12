from django.db.models import Prefetch
from django.shortcuts import render

from .display import board_rows
from .models import Airport, Route, SyncRun

FILTERS = {
    "az": ("A to Z", lambda rows: sorted(rows, key=lambda r: r.name)),
    "far": ("Farthest", lambda rows: sorted(rows, key=lambda r: -(r.miles or 0))),
    "seasonal": ("Seasonal", lambda rows: sorted((r for r in rows if r.seasonal), key=lambda r: r.name)),
    "intl": ("International", lambda rows: sorted((r for r in rows if r.airport.international), key=lambda r: r.name)),
    "soon": ("Starting soon", lambda rows: sorted((r for r in rows if r.starting_soon), key=lambda r: r.name)),
}


def departures(request):
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
    return render(request, "routes/departures.html", {
        "rows": rows,
        "total": len(all_rows),
        "filters": [(key, label) for key, (label, _) in FILTERS.items()],
        "current": current,
        "last_sync": last_sync,
    })
