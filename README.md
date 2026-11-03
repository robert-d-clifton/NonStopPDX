# NonStopPDX

Explore every nonstop destination from Portland International Airport (PDX).

## Data sync (proof of concept)

`sync/pdx_routes.py` builds the route dataset from free sources:

* **Routes:** the Passenger table in Wikipedia's [Portland International Airport](https://en.wikipedia.org/wiki/Portland_International_Airport) article. It's community maintained, usually current within days, and includes seasonal routes plus announced start and end dates.
* **Airports:** [OurAirports](https://ourairports.com/data/) for names, cities, countries and coordinates (cached in `.cache/` for a week).
* **IATA fallback:** Wikidata, only for destinations OurAirports doesn't link to a Wikipedia article.

It uses only the Python standard library, so there's nothing to install.

```sh
python3 -m sync.pdx_routes        # writes data/routes.json and data/routes.csv
python3 -m unittest               # parser tests, no network needed
```

### Output

`data/routes.json` has one entry per destination, sorted by distance from PDX:

```json
{
  "iata": "FRA",
  "city": "Frankfurt",
  "country": "DE",
  "distance_mi": 5212,
  "year_round": false,
  "international": true,
  "services": [{ "airline": "Condor", "kind": "seasonal" }]
}
```

`kind` is one of `year-round`, `seasonal`, `charter`, or `seasonal charter`. Services can also carry `begins`, `ends` or `resumes` dates as written on Wikipedia.

### Manual overrides

Sources lag reality now and then, like a seasonal route Wikipedia drops while it's paused. `data/overrides.json` lets you fix that by hand:

```json
{ "action": "add", "iata": "MSY", "airline": "Alaska Airlines", "kind": "seasonal",
  "reason": "Paused for the season, Wikipedia dropped it", "review_by": "2027-02-01" }
```

* `add` puts in a route the sources are missing. `remove` takes one out, for one airline or, with no `airline`, the whole destination.
* `reason` is required, so future you knows why it's there.
* Each run warns when an override looks stale: Wikipedia caught up, or `review_by` has passed.
* Manual rows are marked `"source": "manual"` in the output, so the app can tell them apart.

### Known limits

* Wikipedia is crowd edited, so a bad edit can slip through. The output records the revision it came from.
* No schedules or frequencies yet. The free BTS T-100 data could add monthly flight counts later.
