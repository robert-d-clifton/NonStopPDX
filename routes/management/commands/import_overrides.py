from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from routes.sync import import_overrides


class Command(BaseCommand):
    help = "Replace the overrides in the database with data/overrides.json, the source of truth."

    def add_arguments(self, parser):
        parser.add_argument("--file", type=Path, default=settings.OVERRIDES_FILE)

    def handle(self, *args, **options):
        try:
            n = import_overrides(options["file"])
        except (ValueError, OSError) as exc:
            raise CommandError(f"Couldn't import overrides: {exc}") from exc
        self.stdout.write(self.style.SUCCESS(f"Imported {n} overrides from {options['file']}"))
