from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from stories.files import render
from stories.models import Story


class Command(BaseCommand):
    help = "Write stories from the database back to stories/<IATA>.md, so admin site edits can be committed."

    def add_arguments(self, parser):
        parser.add_argument("--dir", type=Path, default=settings.STORIES_DIR)

    def handle(self, *args, **options):
        folder = options["dir"]
        folder.mkdir(exist_ok=True)
        changed = 0
        for story in Story.objects.select_related("airport"):
            a = story.airport
            text = render({
                "iata": a.iata, "city": a.city, "status": story.status, "headline": story.headline,
                "photo": story.photo, "photo_credit": story.photo_credit, "credits": story.credits,
            }, story.body)
            path = folder / f"{a.iata}.md"
            if not path.exists() or path.read_text(encoding="utf-8") != text:
                path.write_text(text, encoding="utf-8")
                changed += 1
        self.stdout.write(self.style.SUCCESS(f"Wrote {changed} changed story files to {folder}"))
