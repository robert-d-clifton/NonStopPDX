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

    def test_stale_warnings(self):
        w = review_overrides(
            [{"action": "add", "iata": "MSY", "airline": "Alaska Airlines", "reason": "x", "review_by": "2027-02-01"}],
            {("MSY", "Alaska Airlines")}, today="2027-03-01")
        self.assertEqual(len(w), 2)


if __name__ == "__main__":
    unittest.main()
