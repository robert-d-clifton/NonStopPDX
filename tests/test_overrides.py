import unittest

from sync.pdx_routes import Service, build_dataset, review_overrides


def svc(code, airline):
    # Offline datasets have no airport lookup, so use the iata: form to pin the code.
    return Service(airline=airline, airline_article=airline,
                   destination_article=f"iata:{code}", destination_label=code)


class OverrideTests(unittest.TestCase):
    def test_add_creates_manual_service(self):
        ds = build_dataset([svc("SEA", "Alaska Airlines")], offline=True, overrides=[
            {"action": "add", "iata": "MSY", "airline": "Alaska Airlines", "kind": "seasonal", "reason": "x"}])
        msy = [d for d in ds["destinations"] if d["iata"] == "MSY"][0]
        self.assertEqual(msy["services"][0]["source"], "manual")
        self.assertEqual(ds["overrides"]["added"], ["MSY Alaska Airlines"])

    def test_remove_by_airline_keeps_others(self):
        ds = build_dataset([svc("YVR", "Alaska Airlines"), svc("YVR", "Air Canada Express")],
                           offline=True, overrides=[
            {"action": "remove", "iata": "YVR", "airline": "Air Canada Express", "reason": "x"}])
        airlines = [s["airline"] for d in ds["destinations"] for s in d["services"]]
        self.assertEqual(airlines, ["Alaska Airlines"])

    def test_remove_without_airline_drops_destination(self):
        ds = build_dataset([svc("RDM", "SeaPort Airlines")], offline=True, overrides=[
            {"action": "remove", "iata": "RDM", "reason": "x"}])
        self.assertEqual(ds["destination_count"], 0)

    def test_set_changes_kind_and_marks_it(self):
        ds = build_dataset([svc("AZA", "Allegiant Air")], offline=True, overrides=[
            {"action": "set", "iata": "AZA", "airline": "Allegiant Air", "kind": "seasonal", "reason": "x"}])
        aza = ds["destinations"][0]
        self.assertEqual(aza["services"][0]["kind"], "seasonal")
        self.assertEqual(aza["services"][0]["kind_source"], "manual")
        self.assertEqual(aza["services"][0]["source"], "wikipedia")
        self.assertFalse(aza["year_round"])
        self.assertEqual(ds["overrides"]["changed"], ["AZA Allegiant Air year-round to seasonal"])
        self.assertEqual(ds["overrides"]["warnings"], [])

    def test_set_leaves_other_airlines_alone(self):
        ds = build_dataset([svc("IDA", "Alaska Airlines"), svc("IDA", "Allegiant Air")], offline=True, overrides=[
            {"action": "set", "iata": "IDA", "airline": "Allegiant Air", "kind": "seasonal", "reason": "x"}])
        kinds = {s["airline"]: s["kind"] for s in ds["destinations"][0]["services"]}
        self.assertEqual(kinds, {"Alaska Airlines": "year-round", "Allegiant Air": "seasonal"})
        self.assertTrue(ds["destinations"][0]["year_round"])

    def test_set_warns_when_stale_or_unmatched(self):
        e = {"action": "set", "iata": "AZA", "airline": "Allegiant Air", "kind": "seasonal", "reason": "x"}
        caught_up = review_overrides([e], {("AZA", "Allegiant Air")}, "2027-01-01",
                                     {("AZA", "allegiant air"): {"seasonal"}})
        self.assertIn("Wikipedia says seasonal now", caught_up[0])
        missing = review_overrides([e], set(), "2027-01-01", {})
        self.assertIn("nothing to change", missing[0])

    def test_set_needs_a_valid_kind(self):
        import json, tempfile
        from pathlib import Path
        from sync.pdx_routes import load_overrides
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "o.json"
            p.write_text(json.dumps({"overrides": [
                {"action": "set", "iata": "AZA", "airline": "Allegiant Air", "kind": "summer", "reason": "x"}]}))
            with self.assertRaises(ValueError):
                load_overrides(p)

    def test_stale_warnings(self):
        w = review_overrides(
            [{"action": "add", "iata": "MSY", "airline": "Alaska Airlines", "reason": "x", "review_by": "2027-02-01"}],
            {("MSY", "Alaska Airlines")}, today="2027-03-01")
        self.assertEqual(len(w), 2)


if __name__ == "__main__":
    unittest.main()
