"""Build a dataset of nonstop passenger routes from PDX.

Sources (both free, no API key):
  * Wikipedia's "Portland International Airport" article, "Airlines and
    destinations" > "Passenger" table, for which airlines fly where.
  * OurAirports (https://ourairports.com/data/) for airport names, cities,
    countries and coordinates.
  * Wikidata, only as a fallback to find the IATA code of a destination
    whose Wikipedia article OurAirports doesn't link to.

Run from the project root:
    python3 -m sync.pdx_routes            # writes data/routes.json and data/routes.csv
    python3 -m sync.pdx_routes --offline tests/fixtures/sample_wikitext.txt

Standard library only.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import math
import re
import sys
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

USER_AGENT = "NonStopPDX/0.1 (personal hobby project; Python urllib)"
WIKI_API = "https://en.wikipedia.org/w/api.php"
WIKIDATA_API = "https://www.wikidata.org/w/api.php"
OURAIRPORTS_CSV = "https://davidmegginson.github.io/ourairports-data/airports.csv"
PAGE_TITLE = "Portland International Airport"
ORIGIN_IATA = "PDX"

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
CACHE_DIR = ROOT / ".cache"
OVERRIDES_FILE = DATA_DIR / "overrides.json"


# --------------------------------------------------------------------------
# HTTP helpers
# --------------------------------------------------------------------------

def http_get(url: str, params: dict | None = None) -> bytes:
    if params:
        url = f"{url}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.read()


def http_json(url: str, params: dict) -> dict:
    return json.loads(http_get(url, params))


# --------------------------------------------------------------------------
# Wikitext parsing (small, purpose built, no dependencies)
# --------------------------------------------------------------------------

def strip_noise(text: str) -> str:
    """Remove refs, comments and a few presentational templates."""
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    text = re.sub(r"<ref[^>/]*/>", "", text, flags=re.I)
    text = re.sub(r"<ref[^>]*>.*?</ref>", "", text, flags=re.I | re.S)
    return text


def find_template(text: str, name: str, start: int = 0) -> tuple[int, int] | None:
    """Return (start, end) of the first {{name ...}} at or after start, brace matched."""
    m = re.compile(r"\{\{\s*" + re.escape(name).replace(r"\ ", r"[ _]") + r"\s*\|", re.I).search(text, start)
    if not m:
        return None
    depth, i = 0, m.start()
    while i < len(text) - 1:
        pair = text[i:i + 2]
        if pair == "{{":
            depth += 1
            i += 2
            continue
        if pair == "}}":
            depth -= 1
            i += 2
            if depth == 0:
                return m.start(), i
            continue
        i += 1
    return None


def split_params(template_body: str) -> list[str]:
    """Split a template body on top level pipes (ignores pipes inside [[ ]] and {{ }})."""
    parts, buf, depth_sq, depth_br, i = [], [], 0, 0, 0
    while i < len(template_body):
        pair = template_body[i:i + 2]
        if pair == "[[":
            depth_sq += 1; buf.append(pair); i += 2; continue
        if pair == "]]":
            depth_sq -= 1; buf.append(pair); i += 2; continue
        if pair == "{{":
            depth_br += 1; buf.append(pair); i += 2; continue
        if pair == "}}":
            depth_br -= 1; buf.append(pair); i += 2; continue
        ch = template_body[i]
        if ch == "|" and depth_sq == 0 and depth_br == 0:
            parts.append("".join(buf)); buf = []
        else:
            buf.append(ch)
        i += 1
    parts.append("".join(buf))
    return parts


LINK_RE = re.compile(r"\[\[([^\[\]|]+)(?:\|([^\[\]]+))?\]\]")
MARKER_RE = re.compile(r"'''\s*(Seasonal charter|Seasonal|Charter)\s*:?\s*'''\s*:?", re.I)
NOTE_RE = re.compile(r"\s*\(([^()]*)\)")


def clean_title(title: str) -> str:
    title = title.split("#")[0].strip().replace("_", " ")
    return title[:1].upper() + title[1:]


@dataclass
class Service:
    airline: str
    airline_article: str
    destination_article: str
    destination_label: str
    kind: str = "year-round"        # year-round | seasonal | charter | seasonal charter
    begins: str | None = None
    ends: str | None = None
    resumes: str | None = None
    note: str | None = None
    source: str = "wikipedia"       # wikipedia | manual
    kind_source: str | None = None  # "manual" when a set override changed kind


def parse_note(note: str) -> dict:
    out = {"note": note}
    for key in ("begins", "ends", "resumes"):
        m = re.search(rf"\b{key}\s+(.+)", note, re.I)
        if m:
            out[key] = m.group(1).strip()
    return out


def parse_destinations_cell(airline: str, airline_article: str, cell: str) -> list[Service]:
    """Walk a destinations cell in order, tracking which section (year round, seasonal...) we're in."""
    services: list[Service] = []
    kind = "year-round"
    tokens = sorted(
        [(m.start(), "marker", m) for m in MARKER_RE.finditer(cell)]
        + [(m.start(), "link", m) for m in LINK_RE.finditer(cell)],
        key=lambda t: t[0],
    )
    for _, typ, m in tokens:
        if typ == "marker":
            kind = m.group(1).lower()
            continue
        target = clean_title(m.group(1))
        if target.lower().startswith(("file:", "image:", "category:")):
            continue
        svc = Service(
            airline=airline,
            airline_article=airline_article,
            destination_article=target,
            destination_label=(m.group(2) or m.group(1)).strip(),
            kind=kind,
        )
        note = NOTE_RE.match(cell, m.end())
        if note:
            for k, v in parse_note(note.group(1).strip()).items():
                setattr(svc, k, v)
        services.append(svc)
    return services


def parse_airline_cell(cell: str) -> tuple[str, str]:
    m = LINK_RE.search(cell)
    if not m:
        name = re.sub(r"<[^>]+>|'''|''", "", cell).strip()
        return name, name
    return (m.group(2) or m.group(1)).strip(), clean_title(m.group(1))


def passenger_section(wikitext: str) -> str:
    """Narrow to the Passenger subsection so the Cargo table is ignored."""
    m = re.search(r"^=+\s*Passenger[^=\n]*=+\s*$", wikitext, re.M | re.I)
    if not m:
        return wikitext
    rest = wikitext[m.end():]
    nxt = re.search(r"^=+[^=\n]+=+\s*$", rest, re.M)
    return rest[: nxt.start()] if nxt else rest


def parse_routes(wikitext: str) -> list[Service]:
    text = strip_noise(passenger_section(wikitext))
    span = find_template(text, "Airport destination list")
    if not span:
        raise ValueError("Couldn't find an {{Airport destination list}} template in the Passenger section")
    body = text[span[0] + 2: span[1] - 2]
    params = split_params(body)[1:]          # drop the template name
    named = [p for p in params if re.match(r"\s*[\w ]+\s*=", p) and not p.strip().startswith("[[")]
    positional = [p for p in params if p not in named]
    extra_cols = sum(1 for p in named if re.match(r"\s*\d+(st|nd|rd|th)coltitle\s*=", p, re.I))
    ncols = 2 + extra_cols

    services: list[Service] = []
    for i in range(0, len(positional) - 1, ncols):
        airline, article = parse_airline_cell(positional[i])
        if not airline:
            continue
        services.extend(parse_destinations_cell(airline, article, positional[i + 1]))
    return services


# --------------------------------------------------------------------------
# Manual overrides
# --------------------------------------------------------------------------
#
# data/overrides.json is hand edited and committed. It fixes data lag in
# either direction: "add" a route Wikipedia is missing (say a seasonal route
# that's paused right now), "remove" one that's listed but not really
# flying, or "set" the kind of a route Wikipedia labels wrong (say a seasonal
# route listed as year round). Every entry needs a reason, and a review_by
# date so stale overrides get flagged instead of quietly living forever.

KINDS = ("year-round", "seasonal", "charter", "seasonal charter")


def load_overrides(path: Path = OVERRIDES_FILE) -> list[dict]:
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    entries = data.get("overrides", []) if isinstance(data, dict) else data
    for i, e in enumerate(entries):
        if e.get("action") not in ("add", "remove", "set"):
            raise ValueError(f"Override #{i}: action must be 'add', 'remove' or 'set'")
        if not e.get("iata") or not e.get("reason"):
            raise ValueError(f"Override #{i}: iata and reason are required")
        if e["action"] in ("add", "set") and not e.get("airline"):
            raise ValueError(f"Override #{i}: an {e['action']} needs an airline")
        if e["action"] == "set" and e.get("kind") not in KINDS:
            raise ValueError(f"Override #{i}: a set needs a kind, one of {', '.join(KINDS)}")
        e["iata"] = e["iata"].upper()
    return entries


def override_services(overrides: list[dict]) -> list[Service]:
    """Turn 'add' overrides into Service rows, keyed by a synthetic iata: article."""
    out = []
    for e in overrides:
        if e["action"] != "add":
            continue
        out.append(Service(
            airline=e["airline"],
            airline_article=e["airline"],
            destination_article=f"iata:{e['iata']}",
            destination_label=e.get("city") or e["iata"],
            kind=e.get("kind", "seasonal"),
            begins=e.get("begins"), ends=e.get("ends"), resumes=e.get("resumes"),
            note=e.get("note"),
            source="manual",
        ))
    return out


def _matches(e: dict, code: str, airline: str) -> bool:
    return e["iata"] == code and (not e.get("airline") or e["airline"].lower() == airline.lower())


def review_overrides(overrides: list[dict], wiki_pairs: set[tuple[str, str]], today: str,
                     wiki_kinds: dict[tuple[str, str], set[str]] | None = None) -> list[str]:
    """Warnings for overrides that look stale: Wikipedia caught up, or review_by has passed.

    wiki_kinds maps (iata, airline lowercased) to the kinds Wikipedia gives that route.
    """
    warnings = []
    for e in overrides:
        label = f"{e['action']} {e['iata']}" + (f" ({e['airline']})" if e.get("airline") else "")
        listed = any(_matches(e, c, a) for c, a in wiki_pairs)
        if e["action"] == "add" and listed:
            warnings.append(f"{label}: Wikipedia lists this now, the override can probably go")
        if e["action"] == "remove" and not listed:
            warnings.append(f"{label}: Wikipedia no longer lists this, the override can probably go")
        if e["action"] == "set":
            kinds = (wiki_kinds or {}).get((e["iata"], e["airline"].lower()))
            if not kinds:
                warnings.append(f"{label}: Wikipedia doesn't list this route, so there's nothing to change")
            elif kinds == {e["kind"]}:
                warnings.append(f"{label}: Wikipedia says {e['kind']} now, the override can probably go")
        if e.get("review_by") and e["review_by"] < today:
            warnings.append(f"{label}: past its review_by date ({e['review_by']})")
    return warnings


# --------------------------------------------------------------------------
# Enrichment
# --------------------------------------------------------------------------

def fetch_wikitext() -> tuple[str, int | None]:
    data = http_json(WIKI_API, {
        "action": "parse", "page": PAGE_TITLE, "prop": "wikitext|revid",
        "format": "json", "formatversion": "2", "redirects": "1",
    })
    return data["parse"]["wikitext"], data["parse"].get("revid")


def resolve_titles(titles: list[str]) -> tuple[dict[str, str], dict[str, str]]:
    """Follow redirects. Returns (original -> canonical title, canonical -> Wikidata QID)."""
    canonical: dict[str, str] = {}
    qids: dict[str, str] = {}
    for i in range(0, len(titles), 50):
        batch = titles[i:i + 50]
        data = http_json(WIKI_API, {
            "action": "query", "titles": "|".join(batch), "redirects": "1",
            "prop": "pageprops", "ppprop": "wikibase_item",
            "format": "json", "formatversion": "2",
        })
        q = data.get("query", {})
        norm = {n["from"]: n["to"] for n in q.get("normalized", [])}
        redir = {r["from"]: r["to"] for r in q.get("redirects", [])}
        for t in batch:
            c = norm.get(t, t)
            canonical[t] = redir.get(c, c)
        for page in q.get("pages", []):
            qid = page.get("pageprops", {}).get("wikibase_item")
            if qid:
                qids[page["title"]] = qid
    return canonical, qids


def wikidata_iata(qids: list[str]) -> dict[str, str]:
    out: dict[str, str] = {}
    for i in range(0, len(qids), 50):
        data = http_json(WIKIDATA_API, {
            "action": "wbgetentities", "ids": "|".join(qids[i:i + 50]),
            "props": "claims", "format": "json",
        })
        for qid, ent in data.get("entities", {}).items():
            for claim in ent.get("claims", {}).get("P238", []):
                val = claim.get("mainsnak", {}).get("datavalue", {}).get("value")
                if val:
                    out[qid] = val
                    break
    return out


def load_ourairports() -> list[dict]:
    CACHE_DIR.mkdir(exist_ok=True)
    cache = CACHE_DIR / "ourairports_airports.csv"
    if not cache.exists() or (datetime.now().timestamp() - cache.stat().st_mtime) > 7 * 86400:
        cache.write_bytes(http_get(OURAIRPORTS_CSV))
    with cache.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def wiki_title_from_url(url: str) -> str | None:
    if "wikipedia.org/wiki/" not in url:
        return None
    return clean_title(urllib.parse.unquote(url.split("/wiki/", 1)[1]))


def haversine_mi(lat1, lon1, lat2, lon2) -> float:
    r = 3958.8
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def build_dataset(services: list[Service], offline: bool = False,
                  overrides: list[dict] | None = None) -> dict:
    overrides = overrides or []
    services = services + override_services(overrides)
    articles = sorted({s.destination_article for s in services if not s.destination_article.startswith("iata:")})
    airports = [] if offline else load_ourairports()
    by_iata = {a["iata_code"]: a for a in airports if a.get("iata_code")}
    by_title: dict[str, dict] = {}
    for a in airports:
        t = wiki_title_from_url(a.get("wikipedia_link", ""))
        if t and a.get("iata_code"):
            by_title.setdefault(t, a)

    article_iata: dict[str, str] = {}
    unresolved: list[str] = []
    if not offline:
        canonical, qids = resolve_titles(articles)
        missing_qids = {}
        for art in articles:
            c = canonical.get(art, art)
            hit = by_title.get(art) or by_title.get(c)
            if hit:
                article_iata[art] = hit["iata_code"]
            elif c in qids:
                missing_qids[art] = qids[c]
        if missing_qids:
            iata = wikidata_iata(sorted(set(missing_qids.values())))
            for art, qid in missing_qids.items():
                if qid in iata:
                    article_iata[art] = iata[qid]
        unresolved = [a for a in articles if a not in article_iata]
    for s in services:
        if s.destination_article.startswith("iata:"):
            article_iata[s.destination_article] = s.destination_article[5:]

    # Apply removals, and note which Wikipedia routes exist for the staleness check.
    wiki_pairs = {(article_iata.get(s.destination_article, ""), s.airline)
                  for s in services if s.source == "wikipedia"}
    wiki_kinds: dict[tuple[str, str], set[str]] = {}
    for s in services:
        if s.source == "wikipedia":
            key = (article_iata.get(s.destination_article, ""), s.airline.lower())
            wiki_kinds.setdefault(key, set()).add(s.kind)
    removes = [e for e in overrides if e["action"] == "remove"]
    removed = []
    kept = []
    for s in services:
        code = article_iata.get(s.destination_article, "")
        if s.source == "wikipedia" and any(_matches(e, code, s.airline) for e in removes):
            removed.append(f"{code} {s.airline}")
        else:
            kept.append(s)
    services = kept

    # Apply kind changes from "set" overrides.
    sets = [e for e in overrides if e["action"] == "set"]
    changed = []
    for s in services:
        code = article_iata.get(s.destination_article, "")
        for e in sets:
            if s.source == "wikipedia" and _matches(e, code, s.airline) and s.kind != e["kind"]:
                changed.append(f"{code} {s.airline} {s.kind} to {e['kind']}")
                s.kind, s.kind_source = e["kind"], "manual"

    origin = by_iata.get(ORIGIN_IATA)
    destinations: dict[str, dict] = {}
    for s in services:
        code = article_iata.get(s.destination_article, f"?{s.destination_label}")
        ap = by_iata.get(code, {})
        d = destinations.setdefault(code, {
            "iata": code if not code.startswith("?") else None,
            "label": s.destination_label,
            "airport_name": ap.get("name"),
            "city": ap.get("municipality") or s.destination_label,
            "region": ap.get("iso_region"),
            "country": ap.get("iso_country"),
            "lat": float(ap["latitude_deg"]) if ap.get("latitude_deg") else None,
            "lon": float(ap["longitude_deg"]) if ap.get("longitude_deg") else None,
            "distance_mi": None,
            "wikipedia_article": s.destination_article,
            "services": [],
        })
        svc = {k: v for k, v in asdict(s).items()
               if k not in ("destination_article", "destination_label") and v is not None}
        d["services"].append(svc)

    for d in destinations.values():
        if origin and d["lat"] is not None:
            d["distance_mi"] = round(haversine_mi(
                float(origin["latitude_deg"]), float(origin["longitude_deg"]), d["lat"], d["lon"]))
        kinds = {s["kind"] for s in d["services"]}
        d["year_round"] = "year-round" in kinds
        d["international"] = bool(d["country"]) and d["country"] != "US"

    ordered = sorted(destinations.values(), key=lambda d: (d["distance_mi"] is None, d["distance_mi"] or 0))
    return {
        "origin": ORIGIN_IATA,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "destination_count": len(ordered),
        "service_count": len(services),
        "unresolved_articles": unresolved,
        "overrides": {
            "added": [f"{s.destination_article[5:]} {s.airline}" for s in services if s.source == "manual"],
            "removed": removed,
            "changed": changed,
            "warnings": review_overrides(overrides, wiki_pairs, datetime.now().date().isoformat(), wiki_kinds),
        },
        "destinations": ordered,
    }


def write_outputs(dataset: dict, revid: int | None) -> None:
    DATA_DIR.mkdir(exist_ok=True)
    dataset["source"] = {
        "routes": f"https://en.wikipedia.org/wiki/{PAGE_TITLE.replace(' ', '_')}",
        "routes_revision": revid,
        "airports": "https://ourairports.com/data/",
    }
    (DATA_DIR / "routes.json").write_text(json.dumps(dataset, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    with (DATA_DIR / "routes.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["iata", "city", "country", "distance_mi", "airline", "kind", "begins", "ends", "resumes", "note",
                    "source", "kind_source"])
        for d in dataset["destinations"]:
            for s in d["services"]:
                w.writerow([d["iata"], d["city"], d["country"], d["distance_mi"], s["airline"], s["kind"],
                            s.get("begins"), s.get("ends"), s.get("resumes"), s.get("note"), s.get("source"),
                            s.get("kind_source")])


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--offline", metavar="WIKITEXT_FILE", help="parse a saved wikitext file, skip all network calls")
    args = ap.parse_args(argv)

    if args.offline:
        services = parse_routes(Path(args.offline).read_text(encoding="utf-8"))
        dataset = build_dataset(services, offline=True, overrides=load_overrides())
        print(json.dumps(dataset, indent=2))
        return 0

    wikitext, revid = fetch_wikitext()
    services = parse_routes(wikitext)
    dataset = build_dataset(services, overrides=load_overrides())
    write_outputs(dataset, revid)

    intl = sum(1 for d in dataset["destinations"] if d["international"])
    print(f"{dataset['destination_count']} nonstop destinations ({intl} international), "
          f"{dataset['service_count']} airline routes, from Wikipedia revision {revid}")
    ov = dataset["overrides"]
    if ov["added"] or ov["removed"] or ov["changed"]:
        print(f"Manual overrides: added {', '.join(ov['added']) or 'none'}; "
              f"removed {', '.join(ov['removed']) or 'none'}; changed {', '.join(ov['changed']) or 'none'}")
    for w in ov["warnings"]:
        print("Check override:", w, file=sys.stderr)
    if dataset["unresolved_articles"]:
        print("Couldn't find an IATA code for:", ", ".join(dataset["unresolved_articles"]), file=sys.stderr)
    print(f"Wrote {DATA_DIR / 'routes.json'} and {DATA_DIR / 'routes.csv'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
