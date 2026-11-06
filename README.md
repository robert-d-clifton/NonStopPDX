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
* `set` changes the `kind` of a route Wikipedia already lists, for one airline. Use it when Wikipedia's label is wrong, like a seasonal route listed as year round:

  ```json
  { "action": "set", "iata": "AZA", "airline": "Allegiant Air", "kind": "seasonal",
    "reason": "BTS shows February to August flights only", "review_by": "2027-09-01" }
  ```

* `reason` is required, so future you knows why it's there.
* Each run warns when an override looks stale: Wikipedia caught up, the route it changes is gone, or `review_by` has passed.
* Manual rows are marked `"source": "manual"` in the output, and a changed kind is marked `"kind_source": "manual"`, so the app can tell them apart.

### Known limits

* Wikipedia is crowd edited, so a bad edit can slip through. The output records the revision it came from.
* No schedules or frequencies yet. The free BTS T-100 data could add monthly flight counts later.

### OpenSky departures check

`sync/opensky_departures.py` pulls the last seven complete UTC days of real PDX departures from the [OpenSky Network](https://opensky-network.org/) API and compares them to `data/routes.json`. It needs a free OpenSky API client, with `OPENSKY_CLIENT_ID` and `OPENSKY_CLIENT_SECRET` in a `.env` file at the project root.

```sh
python3 -m sync.opensky_departures   # needs data/routes.json, writes to data/raw/opensky/
```

Raw flights and the comparison stay in `data/raw/`, which git ignores.

OpenSky's arrival airports are estimates, and flights often get logged at a small airfield near the real destination. So the check only flags routes for a manual look against FlyPDX, and never adds or removes a route. It compares airports, not airlines. OpenSky's terms are noncommercial.

## Hosting (planned)

Nothing is hosted yet. Test hosting will be one Docker Compose project on a home server, with its own Cloudflare Tunnel and a Cloudflare Access login in front of it. That opens no router ports and keeps the site private while it's in testing. The site reads only from our own store, so it can move to another host later. Before going public, the data licenses need another look, especially OpenSky's noncommercial terms.

## License and data credits

The code is under the [MIT License](LICENSE). That license doesn't cover the source data in `data/routes.json` and `data/routes.csv`, which keeps its own terms:

* **Route data** comes from the [Portland International Airport](https://en.wikipedia.org/wiki/Portland_International_Airport) article by Wikipedia contributors, under [CC BY SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/). It has been parsed and reformatted, and combined with the airport data below. `data/routes.json` records the revision it came from. Changes we share to this data stay under the same license.
* **Airport data** comes from [OurAirports](https://ourairports.com/data/), which is public domain.
* **IATA fallback codes** come from [Wikidata](https://www.wikidata.org/), under [CC0](https://creativecommons.org/publicdomain/zero/1.0/).
