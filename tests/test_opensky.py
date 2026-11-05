import unittest
from datetime import datetime, timezone

from sync.opensky_departures import compare, day_windows, icao_to_iata, parse_env


def dest(iata, year_round=True):
    return {"iata": iata, "year_round": year_round}


def flight(callsign, arrival, first_seen, icao24="abc123"):
    return {"callsign": callsign, "estArrivalAirport": arrival, "firstSeen": first_seen, "icao24": icao24}


class ParseEnvTests(unittest.TestCase):
    def test_strips_matching_quotes_and_skips_comments(self):
        values = parse_env('# note\nA="one"\nB=\'two\'\nC=three\n\nD="uneven\n')
        self.assertEqual(values, {"A": "one", "B": "two", "C": "three", "D": '"uneven'})

    def test_keeps_equals_signs_in_values(self):
        self.assertEqual(parse_env("A=b=c")["A"], "b=c")


class WindowTests(unittest.TestCase):
    def test_seven_complete_days_ending_at_midnight_utc(self):
        windows = day_windows(datetime(2026, 11, 5, 13, 30, tzinfo=timezone.utc))
        self.assertEqual(len(windows), 7)
        self.assertEqual(windows[0][0], int(datetime(2026, 10, 29, tzinfo=timezone.utc).timestamp()))
        self.assertEqual(windows[-1][1], int(datetime(2026, 11, 5, tzinfo=timezone.utc).timestamp()))
        self.assertTrue(all(end - begin == 86400 for begin, end in windows))


class CompareTests(unittest.TestCase):
    def setUp(self):
        self.iata = icao_to_iata([
            {"iata_code": "SEA", "ident": "KSEA"},
            {"iata_code": "MEM", "ident": "KMEM"},
            {"iata_code": "", "ident": "KXXX"},
        ])

    def test_sorts_routes_into_buckets(self):
        result = compare(
            [flight("ASA123  ", "KSEA", 1), flight("FDX9", "KMEM", 2)],
            [dest("SEA"), dest("JFK"), dest("MSY", year_round=False)],
            self.iata,
        )
        self.assertEqual(result["confirmed"], {"SEA": 1})
        self.assertEqual(result["year_round_not_seen"], ["JFK"])
        self.assertEqual(result["seasonal_not_seen"], ["MSY"])
        self.assertEqual(result["seen_not_listed"],
                         [{"airport": "MEM", "departures": 1, "callsign_prefixes": {"FDX": 1}}])

    def test_ignores_private_flights_and_counts_missing_estimates(self):
        result = compare(
            [flight("N123AB", "KSEA", 1), flight(None, "KSEA", 2), flight("ASA1", None, 3)],
            [dest("SEA")], self.iata,
        )
        self.assertEqual(result["other_flights_ignored"], 2)
        self.assertEqual(result["airline_flights_without_arrival_estimate"], 1)
        self.assertEqual(result["confirmed"], {})

    def test_counts_a_repeated_flight_once(self):
        result = compare([flight("ASA1", "KSEA", 5), flight("ASA1", "KSEA", 5)], [dest("SEA")], self.iata)
        self.assertEqual(result["total_flights"], 1)
        self.assertEqual(result["confirmed"], {"SEA": 1})


if __name__ == "__main__":
    unittest.main()
