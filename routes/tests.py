import json
import shutil
import tempfile
from pathlib import Path

from django.conf import settings
from django.test import TestCase

from routes.models import Airport, Override, Route
from routes.regions import region_for
from routes.sync import apply_dataset, export_overrides, import_overrides


def dataset(*destinations):
    return {"destinations": list(destinations), "overrides": {"warnings": []}, "unresolved_articles": []}


def dest(code, city, *services, country="US", region="US-WA", miles=130):
    return {
        "iata": code, "city": city, "country": country, "region": region, "lat": 47.4, "lon": -122.3,
        "distance_mi": miles, "airport_name": f"{city} airport",
        "services": [{"airline": a, "kind": k, "source": "wikipedia", **extra} for a, k, *rest in services
                     for extra in [rest[0] if rest else {}]],
    }


class ApplyDatasetTests(TestCase):
    def test_creates_airports_airlines_and_routes(self):
        run = apply_dataset(dataset(dest("SEA", "Seattle", ("Alaska Airlines", "year-round"), ("Delta Air Lines", "year-round"))), 123)
        self.assertEqual(run.destinations, 1)
        self.assertEqual(run.routes, 2)
        self.assertEqual(run.revision, 123)
        self.assertTrue(Airport.objects.get(iata="SEA").is_destination)

    def test_route_missing_from_a_later_sync_is_turned_off_not_deleted(self):
        apply_dataset(dataset(dest("SEA", "Seattle", ("Alaska Airlines", "year-round")),
                              dest("PDT", "Pendleton", ("Boutique Air", "year-round"), region="US-OR")))
        run = apply_dataset(dataset(dest("SEA", "Seattle", ("Alaska Airlines", "year-round"))))
        self.assertEqual(run.dropped, 1)
        pdt = Route.objects.get(destination__iata="PDT")
        self.assertFalse(pdt.active)
        self.assertFalse(Airport.objects.get(iata="PDT").is_destination)

    def test_returning_route_keeps_its_first_seen(self):
        apply_dataset(dataset(dest("SEA", "Seattle", ("Alaska Airlines", "year-round"))))
        first = Route.objects.get().first_seen
        apply_dataset(dataset(dest("SEA", "Seattle", ("Alaska Airlines", "seasonal"))))
        route = Route.objects.get()
        self.assertEqual(route.first_seen, first)
        self.assertEqual(route.kind, "seasonal")

    def test_destination_without_a_code_is_skipped_and_reported(self):
        run = apply_dataset(dataset({"iata": None, "city": "Somewhere", "services": []}))
        self.assertEqual(Airport.objects.count(), 0)
        self.assertIn("Skipped 1 destinations without an IATA code", run.warnings)


class OverrideFileTests(TestCase):
    def test_import_then_export_matches_the_committed_file(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "overrides.json"
            shutil.copy(settings.OVERRIDES_FILE, path)
            original = json.loads(path.read_text())
            n = import_overrides(path)
            self.assertEqual(n, len(original["overrides"]))
            export_overrides(path)
            self.assertEqual(json.loads(path.read_text()), original)

    def test_import_replaces_what_was_there(self):
        Override.objects.create(action="remove", iata="XYZ", reason="old")
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "overrides.json"
            path.write_text(json.dumps({"overrides": [{"action": "add", "iata": "msy", "airline": "Alaska Airlines", "reason": "x"}]}))
            import_overrides(path)
        self.assertEqual([str(o) for o in Override.objects.all()], ["add MSY (Alaska Airlines)"])


class RegionTests(TestCase):
    def test_regions(self):
        self.assertEqual(region_for("US", "US-OR").name, "Pacific Northwest")
        self.assertEqual(region_for("CA", "CA-AB").name, "Mountain West")
        self.assertEqual(region_for("US", "US-GA").name, "Central and East")
        self.assertEqual(region_for("IS", "IS-1").name, "International")


class DeparturesPageTests(TestCase):
    def setUp(self):
        apply_dataset(dataset(
            dest("SEA", "Seattle", ("Alaska Airlines", "year-round")),
            dest("AZA", "Mesa", ("Allegiant Air", "seasonal"), region="US-AZ", miles=1028),
            dest("HDN", "Hayden", ("Alaska Airlines", "seasonal", {"begins": "February 11, 2027"}), region="US-CO", miles=851),
            dest("KEF", "Reykjavík", ("Icelandair", "seasonal"), country="IS", region="IS-1", miles=3727),
        ))

    def test_lists_every_destination(self):
        page = self.client.get("/")
        self.assertEqual(page.status_code, 200)
        for text in ("Seattle", "Mesa", "Hayden", "Reykjavík", "Year round", "Starts Feb 11", "Showing 4 of 4"):
            self.assertContains(page, text)

    def test_filters(self):
        self.assertContains(self.client.get("/?f=intl"), "Showing 1 of 4")
        self.assertContains(self.client.get("/?f=soon"), "Hayden")
        seasonal = self.client.get("/?f=seasonal")
        self.assertNotIn("SEA", [r.airport.iata for r in seasonal.context["rows"]])
        self.assertContains(seasonal, "Showing 3 of 4")

    def test_unknown_filter_falls_back_to_a_to_z(self):
        self.assertContains(self.client.get("/?f=nope"), "Showing 4 of 4")

    def test_farthest_puts_reykjavik_first(self):
        rows = self.client.get("/?f=far").context["rows"]
        self.assertEqual(rows[0].airport.iata, "KEF")


class OverviewMapTests(TestCase):
    def setUp(self):
        apply_dataset(dataset(
            dest("SEA", "Seattle", ("Alaska Airlines", "year-round"), ("Delta Air Lines", "year-round")),
            dest("HDN", "Hayden", ("Alaska Airlines", "seasonal", {"begins": "February 11, 2027"}), region="US-CO", miles=851),
        ))

    def test_page_carries_one_map_point_per_destination(self):
        page = self.client.get("/")
        points = {p["code"]: p for p in page.context["map_points"]}
        self.assertEqual(set(points), {"SEA", "HDN"})
        self.assertEqual(points["SEA"]["airlines"], ["Alaska", "Delta"])
        self.assertTrue(points["SEA"]["yearRound"])
        self.assertFalse(points["HDN"]["yearRound"])
        self.assertEqual(points["HDN"]["service"], "Starts Feb 11")
        self.assertContains(page, '<script id="map-points" type="application/json">')
        self.assertContains(page, 'id="overview-map"')

    def test_filters_do_not_shrink_the_map(self):
        page = self.client.get("/?f=intl")
        self.assertEqual(len(page.context["map_points"]), 2)

    def test_destination_without_coordinates_is_left_off_the_map(self):
        Airport.objects.filter(iata="HDN").update(latitude=None)
        page = self.client.get("/")
        self.assertEqual([p["code"] for p in page.context["map_points"]], ["SEA"])


class MapFilesTests(TestCase):
    def test_geography_files_are_valid(self):
        geo = settings.BASE_DIR / "static" / "geo"
        world = json.loads((geo / "world-110m.json").read_text())
        detail = json.loads((geo / "north-america-50m.json").read_text())
        self.assertGreater(len(world["land"]["features"]), 50)
        self.assertEqual(set(world), {"land", "lakes", "countries", "states"})
        self.assertEqual(set(detail), {"land", "lakes", "countries", "states"})
        self.assertGreater(len(detail["countries"]["features"]), 5)


class DestinationPageTests(TestCase):
    def setUp(self):
        apply_dataset(dataset(
            dest("SEA", "Seattle", ("Alaska Airlines", "year-round"), ("Delta Air Lines", "year-round")),
            dest("HDN", "Hayden", ("Alaska Airlines", "seasonal", {"begins": "February 11, 2027"}), region="US-CO", miles=851),
        ))

    def test_page_shows_the_route(self):
        page = self.client.get("/to/sea/")
        self.assertEqual(page.status_code, 200)
        for text in ("Seattle", "Pacific Northwest", "130 mi", "Year round", "Alaska Airlines", "Delta Air Lines",
                     "https://www.google.com/travel/flights?q=Nonstop%20flights%20from%20PDX%20to%20SEA",
                     '<script id="route-point" type="application/json">', "story is still to be written"):
            self.assertContains(page, text)
        self.assertEqual(page.context["route_point"]["code"], "SEA")
        self.assertTrue(page.context["route_point"]["yearRound"])

    def test_upcoming_route_shows_its_start_date(self):
        page = self.client.get("/to/hdn/")
        self.assertContains(page, "Seasonal, starts Feb 11")
        self.assertFalse(page.context["route_point"]["yearRound"])

    def test_uppercase_code_redirects_to_lowercase(self):
        self.assertRedirects(self.client.get("/to/SEA/"), "/to/sea/", status_code=301)

    def test_unknown_or_never_served_airport_is_not_found(self):
        self.assertEqual(self.client.get("/to/zzz/").status_code, 404)
        Airport.objects.create(iata="LAX", city="Los Angeles")
        self.assertEqual(self.client.get("/to/lax/").status_code, 404)

    def test_route_no_longer_flown_says_so(self):
        apply_dataset(dataset(dest("SEA", "Seattle", ("Alaska Airlines", "year-round"))))
        page = self.client.get("/to/hdn/")
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, "PDX has no nonstop to Hayden right now")
        self.assertNotContains(page, "Check fares")

    def test_written_story_is_shown(self):
        from stories.models import Story
        Story.objects.create(airport=Airport.objects.get(iata="SEA"), status="draft", headline="Up the road", body="A short hop north.")
        page = self.client.get("/to/sea/")
        self.assertContains(page, "Up the road")
        self.assertContains(page, "A short hop north.")
        self.assertNotContains(page, "still to be written")

    def test_board_and_map_link_to_destination_pages(self):
        home = self.client.get("/")
        self.assertContains(home, 'href="/to/sea/"')
        self.assertEqual({p["url"] for p in home.context["map_points"]}, {"/to/sea/", "/to/hdn/"})
