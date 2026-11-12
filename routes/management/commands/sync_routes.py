from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from routes.models import Override, SyncRun
from routes.sync import apply_dataset, import_overrides, overrides_from_db
from sync import pdx_routes


class Command(BaseCommand):
    help = "Pull the Wikipedia route table and OurAirports data into the database, applying overrides."

    def add_arguments(self, parser):
        parser.add_argument("--write-files", action="store_true",
                            help="Also write data/routes.json and data/routes.csv, the snapshot committed to the repo")

    def handle(self, *args, **options):
        started = timezone.now()
        if not Override.objects.exists() and settings.OVERRIDES_FILE.exists():
            n = import_overrides(settings.OVERRIDES_FILE)
            self.stdout.write(f"No overrides in the database yet, so imported {n} from {settings.OVERRIDES_FILE.name}")
        try:
            wikitext, revision = pdx_routes.fetch_wikitext()
            services = pdx_routes.parse_routes(wikitext)
            dataset = pdx_routes.build_dataset(services, overrides=overrides_from_db())
        except Exception as exc:
            SyncRun.objects.create(kind="routes", started_at=started, finished_at=timezone.now(), ok=False,
                                   message=f"{type(exc).__name__}: {exc}"[:2000])
            raise CommandError(f"Route sync failed: {exc}") from exc

        run = apply_dataset(dataset, revision, started)
        if options["write_files"]:
            pdx_routes.write_outputs(dataset, revision)
            self.stdout.write("Wrote data/routes.json and data/routes.csv")

        ov = dataset["overrides"]
        self.stdout.write(self.style.SUCCESS(
            f"{run.destinations} destinations, {run.routes} active routes, from Wikipedia revision {revision}. "
            f"{run.dropped} routes turned off."))
        if ov["added"] or ov["removed"] or ov["changed"]:
            self.stdout.write(f"Overrides: added {', '.join(ov['added']) or 'none'}; removed {', '.join(ov['removed']) or 'none'}; "
                              f"changed {', '.join(ov['changed']) or 'none'}")
        for w in run.warnings:
            self.stderr.write(f"Check: {w}")
