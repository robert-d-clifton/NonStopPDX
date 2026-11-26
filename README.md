# NonStopPDX

Explore every nonstop destination from Portland International Airport (PDX).

## Running the site

NonStopPDX is a Django site backed by PostgreSQL, run with Docker Compose. Everything runs in containers, so the host only needs Docker.

```sh
cp .env.example .env            # then fill in a secret key and a database password
docker compose up -d db
docker compose run --rm web python manage.py migrate
docker compose run --rm web python manage.py createsuperuser
docker compose run --rm web python manage.py sync_routes       # routes from Wikipedia into the database
docker compose run --rm web python manage.py import_stories    # stories/*.md into the database
docker compose up -d                                           # the site, plus the weekly scheduler
docker compose run --rm web python manage.py test              # all tests, against PostgreSQL
```

The site listens on `WEB_BIND` from `.env` (127.0.0.1:8000 unless you change it). The admin site is at `/admin/`.

| Service | What it does |
|---------|--------------|
| `db` | PostgreSQL 17, with its data in the `pgdata` volume |
| `web` | Django under gunicorn. The code folder is mounted, so changes show up without a rebuild. |
| `scheduler` | Runs `sync_routes`, then `sync_opensky`, whenever the last good run is older than `SYNC_INTERVAL_HOURS` |

### Management commands

| Command | What it does |
|---------|--------------|
| `sync_routes` | Pulls Wikipedia and OurAirports into the database, applying overrides. Routes that disappear are turned off, not deleted. `--write-files` also refreshes `data/routes.json` and `data/routes.csv`. |
| `sync_opensky` | Stores a week of observed departures per destination. Needs the OpenSky settings in `.env`. |
| `import_overrides` / `export_overrides` | `data/overrides.json` is the source of truth. Import loads it into the database; export writes admin site changes back so they can be committed. |
| `import_stories` / `export_stories` | The same, for `stories/*.md`. |
| `import_airlines` | Applies `data/airlines.json`: airline page addresses, codes, websites, and which regional brands (like United Express) belong to which airline. `sync_routes` runs it too. |

Every sync run is recorded in the admin site under Sync runs, with its warnings.

## Data sync (proof of concept)

`sync/pdx_routes.py` builds the route dataset from free sources:

* **Routes:** the Passenger table in Wikipedia's [Portland International Airport](https://en.wikipedia.org/wiki/Portland_International_Airport) article. It's community maintained, usually current within days, and includes seasonal routes plus announced start and end dates.
* **Airports:** [OurAirports](https://ourairports.com/data/) for names, cities, countries and coordinates (cached in `.cache/` for a week).
* **IATA fallback:** Wikidata, only for destinations OurAirports doesn't link to a Wikipedia article.

It uses only the Python standard library, so there's nothing to install.

```sh
python3 -m sync.pdx_routes        # writes data/routes.json and data/routes.csv
python3 -m unittest discover -s tests -t .   # parser tests, no Django or network needed
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

### Destination stories

Each destination has a story file in `stories/`, named by airport code. They start as placeholders and get written by hand over time. `stories/README.md` explains the fields.

```sh
python3 -m sync.seed_stories   # adds placeholders for new destinations, never overwrites
```

### Inside PDX

The Inside PDX page (`/inside/`) draws the terminal as a raised model and lists what's on each concourse. Three files feed it:

* `data/terminal.json`: building outlines, gates and places from OpenStreetMap, in meters around the main terminal. Rebuild it with `python3 tools/build_terminal.py` (add `--offline` to reuse the last download). Don't edit it by hand.
* `data/places.json`: shops, restaurants and services, copied by hand from FlyPDX's Shops, Dining & More list (never scraped), with an as of date shown on the page. Art, play areas and airline lounges still come from OpenStreetMap.
* `data/concourses.json`: which airlines use each concourse, kept by hand. Mark an airline `checked` once it's confirmed against FlyPDX; unchecked ones show as unconfirmed.

## Hosting

Test hosting is this Docker Compose project on a home server, reached at nonstoppdx.com through its own Cloudflare Tunnel. The tunnel dials out from the `tunnel` container, so no router ports are open. Cloudflare Access sits in front of it as the login while the site is in testing (the free plan allows 50 people); Django's own invite only accounts will take over from Access later. The LAN address keeps working alongside the domain.

To bring it up:

1. In Cloudflare Zero Trust, create a tunnel named `nonstoppdx` and copy its token into `.env` as `CLOUDFLARE_TUNNEL_TOKEN`.
2. Give the tunnel public hostnames `nonstoppdx.com` and `www.nonstoppdx.com`, both HTTP to `web:8000`.
3. Add an Access application (self hosted) for both hostnames, with a policy that allows the testers' emails.
4. In `.env`, add the domain to `DJANGO_ALLOWED_HOSTS` and `DJANGO_CSRF_TRUSTED_ORIGINS` (see `.env.example`) and set `DJANGO_DEBUG=0`.
5. Start it: `docker compose up -d web && docker compose --profile tunnel up -d tunnel`.

Before going public, the data licenses need another look, especially OpenSky's noncommercial terms.

## License and data credits

The code is under the [MIT License](LICENSE). That license doesn't cover the source data in `data/routes.json` and `data/routes.csv`, which keeps its own terms:

* **Route data** comes from the [Portland International Airport](https://en.wikipedia.org/wiki/Portland_International_Airport) article by Wikipedia contributors, under [CC BY SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/). It has been parsed and reformatted, and combined with the airport data below. `data/routes.json` records the revision it came from. Changes we share to this data stay under the same license.
* **Airport data** comes from [OurAirports](https://ourairports.com/data/), which is public domain.
* **Terminal outlines, gates and places** in `data/terminal.json` come from [OpenStreetMap](https://www.openstreetmap.org/copyright) contributors, under the [ODbL](https://opendatacommons.org/licenses/odbl/). The Inside PDX page credits them.
* **IATA fallback codes** come from [Wikidata](https://www.wikidata.org/), under [CC0](https://creativecommons.org/publicdomain/zero/1.0/).
