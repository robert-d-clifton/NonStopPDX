# SWIM collector

A trial of the FAA's SWIM flight data (TFMS R14 Flight Data, through the SWIM Cloud Distribution Service). It reads the subscription's queue and keeps airline flights to and from PDX, to learn which days and times each route runs, the aircraft used, and when seasonal service starts and stops.

## What it keeps

- Only flight records whose departure or arrival airport is KPDX.
- Only airlines listed in `data/swim_operators.json`, by the three letter code that starts their call signs. All private and charter flights are dropped as they arrive and never saved, which keeps aircraft on the FAA's LADD list off this system.
- Only records the FAA marks as unrestricted (sensitivity `A`).
- No position reports (`trackInformation`, `boundaryCrossingUpdate`).

Kept records are written as one line of XML each to `data/swim/flights-YYYY-MM-DD.xml.gz` (UTC days), which git ignores. The day's file is still open while the collector runs, so a reader should expect its end to be cut short. The log shows counts only.

## Running it

It needs the `SWIM_*` settings in `.env` (see `.env.example`), copied from the subscription's JMS connection details in the SCDS portal. It isn't started by a plain `docker compose up`:

    docker compose --profile swim up -d --build swim
    docker compose --profile swim logs -f swim
    docker compose --profile swim stop swim

## Terms to keep

The FAA's terms require the JMS connection method with compression on (the collector sets both), one subscription per product, and blocking LADD listed aircraft. Anything shown on the site from this feed must not be described as FAA data. It must never be the only source for anything safety related.
