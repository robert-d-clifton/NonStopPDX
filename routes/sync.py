"""Load route datasets and override files into the database."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from django.db import transaction
from django.utils import timezone

from sync.pdx_routes import load_overrides

from .models import Airline, Airport, Override, Route, SyncRun

OVERRIDES_HELP = (
    "Hand edited fixes for data lag. action is add, remove or set. iata and reason are required. "
    "An add needs airline. A remove without airline drops every airline on that route. A set needs airline "
    "and kind, and changes the kind of a route Wikipedia already lists. review_by flags the entry once that date passes."
)


@transaction.atomic
def apply_dataset(dataset: dict, revision: int | None = None, started_at=None) -> SyncRun:
    """Upsert a dataset from sync.pdx_routes.build_dataset. Routes it no longer lists are turned off, not deleted."""
    now = timezone.now()
    seen: set[int] = set()
    skipped = 0
    for d in dataset["destinations"]:
        if not d.get("iata"):
            skipped += 1
            continue
        airport, _ = Airport.objects.update_or_create(
            iata=d["iata"],
            defaults={
                "name": d.get("airport_name") or "",
                "city": d.get("city") or "",
                "country": d.get("country") or "",
                "region": d.get("region") or "",
                "latitude": d.get("lat"),
                "longitude": d.get("lon"),
                "distance_mi": d.get("distance_mi"),
                "wikipedia_article": d.get("wikipedia_article") or "",
                "is_destination": True,
            },
        )
        for s in d["services"]:
            airline, _ = Airline.objects.get_or_create(name=s["airline"])
            fields = {
                "kind": s.get("kind") or "year-round",
                "begins": s.get("begins") or "",
                "ends": s.get("ends") or "",
                "resumes": s.get("resumes") or "",
                "note": s.get("note") or "",
                "source": s.get("source") or "wikipedia",
                "kind_source": s.get("kind_source") or "",
                "active": True,
                "last_seen": now,
            }
            route, _ = Route.objects.update_or_create(
                destination=airport, airline=airline, defaults=fields, create_defaults={**fields, "first_seen": now}
            )
            seen.add(route.pk)
    dropped = Route.objects.filter(active=True).exclude(pk__in=seen).update(active=False)
    Airport.objects.filter(is_destination=True).exclude(routes__active=True).update(is_destination=False)

    warnings = list(dataset.get("overrides", {}).get("warnings", []))
    if dataset.get("unresolved_articles"):
        warnings.append("No IATA code for: " + ", ".join(dataset["unresolved_articles"]))
    if skipped:
        warnings.append(f"Skipped {skipped} destinations without an IATA code")
    return SyncRun.objects.create(
        kind="routes",
        started_at=started_at or now,
        finished_at=timezone.now(),
        ok=True,
        revision=revision,
        destinations=Airport.objects.filter(is_destination=True).count(),
        routes=Route.objects.filter(active=True).count(),
        dropped=dropped,
        warnings=warnings,
    )


def overrides_from_db() -> list[dict]:
    return [o.as_dict() for o in Override.objects.all()]


@transaction.atomic
def import_overrides(path: Path) -> int:
    """Replace the database's overrides with the file's. The file is the source of truth."""
    entries = load_overrides(path)  # validates
    Override.objects.all().delete()
    for e in entries:
        Override.objects.create(
            action=e["action"],
            iata=e["iata"],
            city=e.get("city", ""),
            airline=e.get("airline", ""),
            kind=e.get("kind", ""),
            reason=e["reason"],
            added=date.fromisoformat(e["added"]) if e.get("added") else None,
            review_by=date.fromisoformat(e["review_by"]) if e.get("review_by") else None,
            note=e.get("note", ""),
        )
    return len(entries)


def export_overrides(path: Path) -> int:
    """Write the database's overrides back to the file, so changes made in the admin site can be committed."""
    entries = overrides_from_db()
    path.write_text(json.dumps({"_help": OVERRIDES_HELP, "overrides": entries}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return len(entries)
