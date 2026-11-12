import time
from datetime import timedelta

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from routes.models import SyncRun

CHECK_EVERY_SECONDS = 3600


class Command(BaseCommand):
    help = "Run the route sync, then the OpenSky check, whenever the last good run is older than SYNC_INTERVAL_HOURS."

    def due(self, kind: str) -> bool:
        last = SyncRun.objects.filter(kind=kind, ok=True).order_by("-finished_at").first()
        return last is None or timezone.now() - last.finished_at > timedelta(hours=settings.SYNC_INTERVAL_HOURS)

    def run(self, name: str) -> None:
        try:
            call_command(name, stdout=self.stdout, stderr=self.stderr)
        except CommandError as exc:
            self.stderr.write(f"{name} failed: {exc}")

    def handle(self, *args, **options):
        self.stdout.write(f"Scheduler started. Syncs run every {settings.SYNC_INTERVAL_HOURS} hours.")
        while True:
            if self.due("routes"):
                self.run("sync_routes")
            if self.due("opensky") and not self.due("routes"):
                self.run("sync_opensky")
            time.sleep(CHECK_EVERY_SECONDS)
