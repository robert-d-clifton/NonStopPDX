import tempfile
from io import StringIO
from pathlib import Path

from django.conf import settings
from django.core.management import call_command
from django.test import SimpleTestCase, TestCase

from routes.models import Airport
from stories.files import parse, render
from stories.models import Story


class StoryFileTests(SimpleTestCase):
    def test_placeholder_round_trips_exactly(self):
        text = (settings.STORIES_DIR / "AZA.md").read_text()
        fields, body = parse(text)
        self.assertEqual(fields["iata"], "AZA")
        self.assertEqual(fields["status"], "placeholder")
        self.assertEqual(body, "Story to come.")
        self.assertEqual(render(fields, body), text)

    def test_missing_fields_block_is_an_error(self):
        with self.assertRaises(ValueError):
            parse("just a story")


class ImportExportTests(TestCase):
    def test_import_then_export(self):
        Airport.objects.create(iata="PDT", city="Pendleton", is_destination=True)
        with tempfile.TemporaryDirectory() as d:
            folder = Path(d)
            (folder / "PDT.md").write_text(render({"iata": "PDT", "city": "Pendleton", "status": "draft", "headline": "Round Up town"}, "A short hop."))
            (folder / "XYZ.md").write_text(render({"iata": "XYZ", "status": "placeholder"}, "Story to come."))
            err = StringIO()
            call_command("import_stories", dir=folder, stdout=StringIO(), stderr=err)
            self.assertIn("XYZ", err.getvalue())
            story = Story.objects.get()
            self.assertEqual((story.status, story.headline, story.body), ("draft", "Round Up town", "A short hop."))

            story.body = "A short hop over the Columbia."
            story.save()
            call_command("export_stories", dir=folder, stdout=StringIO())
            fields, body = parse((folder / "PDT.md").read_text())
            self.assertEqual(body, "A short hop over the Columbia.")
            self.assertEqual(fields["headline"], "Round Up town")
