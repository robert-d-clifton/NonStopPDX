from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from routes.sync import export_overrides


class Command(BaseCommand):
    help = "Write the database's overrides to data/overrides.json, so admin site changes can be committed."

    def add_arguments(self, parser):
        parser.add_argument("--file", type=Path, default=settings.OVERRIDES_FILE)

    def handle(self, *args, **options):
        n = export_overrides(options["file"])
        self.stdout.write(self.style.SUCCESS(f"Wrote {n} overrides to {options['file']}"))
