import unittest
from pathlib import Path

from sync.pdx_routes import build_dataset, parse_routes

FIXTURE = Path(__file__).parent / "fixtures" / "sample_wikitext.txt"


class ParseRoutesTest(unittest.TestCase):
    def setUp(self):
        self.services = parse_routes(FIXTURE.read_text(encoding="utf-8"))

    def find(self, airline, label):
        return next(s for s in self.services if s.airline == airline and s.destination_label == label)

    def test_counts_and_cargo_ignored(self):
        self.assertEqual(len(self.services), 14)
        self.assertNotIn("Memphis", {s.destination_label for s in self.services})

    def test_year_round_and_seasonal(self):
        self.assertEqual(self.find("Alaska Airlines", "Boise").kind, "year-round")
        self.assertEqual(self.find("Alaska Airlines", "Bozeman").kind, "seasonal")
        self.assertEqual(self.find("Condor", "Frankfurt").kind, "seasonal")

    def test_dates(self):
        self.assertEqual(self.find("Alaska Airlines", "Puerto Vallarta").begins, "December 18, 2026")
        self.assertEqual(self.find("Delta Air Lines", "Tokyo–Haneda").ends, "March 28, 2027")

    def test_charter_and_airline_article(self):
        svc = self.find("Sun Country Airlines", "Bullhead City")
        self.assertEqual(svc.kind, "seasonal charter")
        self.assertEqual(self.find("Condor", "Frankfurt").airline_article, "Condor (airline)")

    def test_offline_dataset_groups_by_destination(self):
        ds = build_dataset(self.services, offline=True)
        msp = next(d for d in ds["destinations"] if d["label"] == "Minneapolis/St. Paul")
        self.assertEqual({s["airline"] for s in msp["services"]}, {"Delta Air Lines", "Sun Country Airlines"})
        self.assertTrue(msp["year_round"])


if __name__ == "__main__":
    unittest.main()
