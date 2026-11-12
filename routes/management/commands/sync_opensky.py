import json
from datetime import datetime, timezone as dt_timezone

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from routes.models import Airport, SyncRun, WeeklySnapshot
from sync import opensky_departures as od


class Command(BaseCommand):
    help = ("Pull the last seven complete days of PDX departures from OpenSky and store a weekly count per destination. "
            "Arrival airports are estimates, so treat the counts as a signal, not proof.")

    def handle(self, *args, **options):
        started = timezone.now()
        destinations = [
            {"iata": a.iata, "year_round": a.routes.filter(active=True, kind="year-round").exists()}
            for a in Airport.objects.filter(is_destination=True)
        ]
        if not destinations:
            raise CommandError("No destinations in the database yet. Run sync_routes first.")
        try:
            token = od.fetch_token(*od.load_credentials())
            flights, per_day = [], {}
            for begin, end in od.day_windows(datetime.now(dt_timezone.utc)):
                day = datetime.fromtimestamp(begin, dt_timezone.utc).date()
                batch, _ = od.fetch_departures(token, begin, end)
                flights.extend(batch)
                per_day[day.isoformat()] = len(batch)
            result = od.compare(flights, destinations, od.icao_to_iata(od.load_ourairports()))
        except SystemExit as exc:  # the OpenSky helpers exit with a readable message
            SyncRun.objects.create(kind="opensky", started_at=started, finished_at=timezone.now(), ok=False, message=str(exc))
            raise CommandError(str(exc)) from None

        first, last = min(per_day), max(per_day)
        week_start = datetime.fromisoformat(first).date()
        for d in destinations:
            WeeklySnapshot.objects.update_or_create(
                airport=Airport.objects.get(iata=d["iata"]), week_start=week_start, source="opensky",
                defaults={"departures": result["confirmed"].get(d["iata"], 0)},
            )
        od.RAW_DIR.mkdir(parents=True, exist_ok=True)
        (od.RAW_DIR / f"departures_{first}_{last}.json").write_text(json.dumps(flights) + "\n", encoding="utf-8")
        (od.RAW_DIR / f"comparison_{first}_{last}.json").write_text(json.dumps({**result, "departures_per_day": per_day}, indent=2) + "\n", encoding="utf-8")

        SyncRun.objects.create(
            kind="opensky", started_at=started, finished_at=timezone.now(), ok=True,
            destinations=len(result["confirmed"]), routes=result["total_flights"],
            warnings=[f"Year round, not seen: {', '.join(result['year_round_not_seen'])}"] if result["year_round_not_seen"] else [],
            message=f"{result['total_flights']} departures, {first} to {last} UTC; "
                    f"{result['airline_flights_without_arrival_estimate']} airline flights had no arrival estimate",
        )
        self.stdout.write(self.style.SUCCESS(
            f"{result['total_flights']} departures from {first} to {last}. "
            f"{len(result['confirmed'])} of {len(destinations)} destinations seen."))
