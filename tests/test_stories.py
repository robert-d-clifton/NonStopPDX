import tempfile
import unittest
from pathlib import Path

from sync.seed_stories import seed


class SeedStoriesTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name) / "stories"

    def tearDown(self):
        self.tmp.cleanup()

    def test_creates_one_placeholder_per_destination(self):
        created, orphans = seed([{"iata": "AZA", "city": "Mesa"}, {"iata": None, "city": "?"}], self.dir)
        self.assertEqual(created, ["AZA"])
        self.assertEqual(orphans, [])
        text = (self.dir / "AZA.md").read_text()
        self.assertIn("iata: AZA\ncity: Mesa\nstatus: placeholder\n", text)

    def test_never_overwrites_an_existing_story(self):
        self.dir.mkdir()
        (self.dir / "AZA.md").write_text("our story")
        created, _ = seed([{"iata": "AZA", "city": "Mesa"}], self.dir)
        self.assertEqual(created, [])
        self.assertEqual((self.dir / "AZA.md").read_text(), "our story")

    def test_reports_stories_whose_route_is_gone(self):
        self.dir.mkdir()
        (self.dir / "XYZ.md").write_text("old route")
        (self.dir / "README.md").write_text("about stories")
        _, orphans = seed([{"iata": "AZA", "city": "Mesa"}], self.dir)
        self.assertEqual(orphans, ["XYZ"])


if __name__ == "__main__":
    unittest.main()
