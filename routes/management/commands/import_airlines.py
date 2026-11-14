from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from routes.sync import import_airlines


class Command(BaseCommand):
    help = "Apply data/airlines.json: page addresses, codes, websites and regional brands."

    def add_arguments(self, parser):
        parser.add_argument("--file", type=Path, default=settings.AIRLINES_FILE)

    def handle(self, *args, **options):
        try:
            n = import_airlines(options["file"])
        except (ValueError, KeyError, OSError) as exc:
            raise CommandError(f"Couldn't import airlines: {exc}") from exc
        self.stdout.write(self.style.SUCCESS(f"Applied {n} airlines from {options['file']}"))
