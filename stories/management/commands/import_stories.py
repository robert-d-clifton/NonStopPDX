from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from routes.models import Airport
from stories.files import read_dir
from stories.models import Story


class Command(BaseCommand):
    help = "Load stories/<IATA>.md into the database. The files are the source of truth."

    def add_arguments(self, parser):
        parser.add_argument("--dir", type=Path, default=settings.STORIES_DIR)

    @transaction.atomic
    def handle(self, *args, **options):
        try:
            entries = read_dir(options["dir"])
        except ValueError as exc:
            raise CommandError(f"Couldn't read stories: {exc}") from exc
        airports = {a.iata: a for a in Airport.objects.all()}
        loaded, missing = 0, []
        for path, fields, body in entries:
            code = (fields.get("iata") or path.stem).upper()
            airport = airports.get(code)
            if not airport:
                missing.append(code)
                continue
            status = fields.get("status") or "placeholder"
            if status not in dict(Story.STATUSES):
                raise CommandError(f"{path.name}: status must be placeholder, draft or ready, not {status!r}")
            Story.objects.update_or_create(airport=airport, defaults={
                "status": status,
                "headline": fields.get("headline", ""),
                "body": body,
                "photo": fields.get("photo", ""),
                "photo_credit": fields.get("photo_credit", ""),
                "credits": fields.get("credits", ""),
            })
            loaded += 1
        self.stdout.write(self.style.SUCCESS(f"Loaded {loaded} stories"))
        if missing:
            self.stderr.write("No airport in the database for: " + ", ".join(missing) + ". Run sync_routes first.")
