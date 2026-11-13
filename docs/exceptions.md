# Known differences from FlyPDX

FlyPDX's [nonstop page](https://www.flypdx.com/NonstopDestinations) is our validation
source, checked by hand. Where we have real evidence that it's wrong or behind, like
BTS flight counts, the evidence wins and the difference is written down here.

For the Phase 0 gate, differences in destinations and airlines count. Differences in
season labels are recorded but don't block it.

BTS means the on time flight data from the Bureau of Transportation Statistics, which
covers US airlines' domestic flights only, January 2024 to August 2026 as of this check.

## Airline check, 2026-11-07

Compared against Wikipedia revision 1382252995 plus overrides.

### Fixed with overrides

| Code | City | Airline | Change | Evidence |
|------|------|---------|--------|----------|
| HNL | Honolulu | Alaska Airlines | Added | FlyPDX lists it. BTS shows about 80 flights a month since January 2026. |
| PHL | Philadelphia | Alaska Airlines | Added, seasonal | FlyPDX lists it. BTS shows daily flights since May 2026. |
| PHX | Phoenix | Frontier Airlines | Removed | FlyPDX doesn't list it. No BTS flights since March 2026. Wikipedia caught up by 2026-11-12, so the override was deleted. |

### Dropped since

| Code | City | Airline | When | Evidence |
|------|------|---------|------|----------|
| JAC | Jackson | Alaska Airlines | Wikipedia dropped it by revision 1385089230 (2026-11-12) | No published nonstop flights between PDX and JAC as of 2026-11-12. Its story file stays in `stories/` in case it returns. |

### Off season, so FlyPDX doesn't list them right now

FlyPDX appears to drop seasonal routes while they're off season. We keep them, since
the app should show seasonal routes year round.

| Code | City | Airline | When BTS shows flights |
|------|------|---------|------------------------|
| ATW | Appleton | Allegiant Air | About May to October |
| CVG | Cincinnati | Allegiant Air | About May to October |
| DSM | Des Moines | Allegiant Air | About May to October |
| FNT | Flint | Allegiant Air | About June to September |
| GRR | Grand Rapids | Allegiant Air | About May to August |
| IND | Indianapolis | Allegiant Air | About June to September |
| IDA | Idaho Falls | Allegiant Air | Winter and summer, off in spring and fall |
| MSY | New Orleans | Alaska Airlines | January to May, added through an override |

### Still open

| Code | City | Airline | Difference | What we know |
|------|------|---------|------------|--------------|
| AUS | Austin | Southwest Airlines | FlyPDX only | No BTS flights at all, so possibly a new route. |
| BNA | Nashville | Southwest Airlines | FlyPDX only | 9 BTS flights in summer 2025, none since. |
| BUR | Burbank | Southwest Airlines | Wikipedia only | Last BTS flights November 2025 to January 2026, so it may return for the holidays. |
| RDM | Redmond | SeaPort Airlines | Wikipedia only | FlyPDX listed it on 2026-11-03 but not on 2026-11-07. Not in BTS. |
| HDN | Hayden | Alaska Airlines | Listed by both | Future route, begins February 11, 2027. |

### Season labels that disagree

Recorded only, not overridden. BTS checks the domestic ones.

| Code | City | Airline | Ours | FlyPDX | BTS |
|------|------|---------|------|--------|-----|
| ATL | Atlanta | Alaska Airlines | Year round | Seasonal | Gap in January and February each year |
| IAD | Washington Dulles | United Airlines | Year round | Seasonal | Gap in January and February each year |
| EWR | Newark | United Airlines | Year round | Seasonal | Daily all year, twice daily in summer |
| MCI | Kansas City | Alaska Airlines | Year round | Seasonal | Every month since starting in August 2025 |
| LIH | Lihue | Alaska Airlines | Year round | Seasonal | Off June to October 2025, daily all of 2026 so far |
| PVU | Provo | Allegiant Air | Year round | Seasonal | Almost every month, gap in March and April 2026 |
| MSP | Minneapolis | Sun Country Airlines | Year round | Seasonal | Not in BTS |
| YVR | Vancouver | Alaska Airlines | Year round | Seasonal | Not in BTS |
| KEF | Reykjavík | Icelandair | Seasonal | Year round | Not in BTS |
| BFI | Seattle Boeing Field | SeaPort Airlines | Year round | Seasonal | Not in BTS |

## Destination check, 2026-11-03

Both lists had 90 destinations. Hayden (future route) was on Wikipedia only, and New
Orleans (paused seasonal route) was on FlyPDX only, so it was added through an override.

# OpenSky hand check

The first OpenSky pull (2026-10-29 to 2026-11-04 UTC) didn't match eight year round
destinations to an arrival airport. Each was checked by hand on 2026-11-06.

| Code | City | Finding |
|------|------|---------|
| BIL | Billings | Flying. Alaska AS 2161, seen every day as QXE2161 with no arrival estimate. |
| EAT | Wenatchee | Flying. Alaska AS 2445, seen every day as QXE2445 with no arrival estimate. |
| IDA | Idaho Falls | Flying. Alaska AS 3452, seen as SKW3452 with no arrival estimate. |
| LIH | Lihue | Flying. Alaska AS 927, seen as ASA927 with no arrival estimate. |
| GDL | Guadalajara | Flying. Volaris, seen as VOI1871 and VOI1873, mostly with no arrival estimate. |
| PDT | Pendleton | Flying. Boutique Air 352, 354 and 356, seen every day as BTQ flights with no arrival estimate. |
| MEX | Mexico City | Not flying yet. Aeroméxico resumes January 21, 2027, which Wikipedia already notes. |
| AZA | Mesa | Seasonal, but Wikipedia says year round. See below. |

Lesson: a flight with no arrival estimate hides a real route, so "not seen" on its
own proves nothing.

## AZA, Allegiant to Phoenix Mesa Gateway

Wikipedia has listed this route as year round since August 2024, when an edit
changed it from seasonal. BTS on time data shows the same pattern three years
running: flights on Sundays and Thursdays from about mid February to mid August,
and none from September to January.

| Year | Months with flights |
|------|---------------------|
| 2024 | January to August |
| 2025 | February to August |
| 2026 | February to August |

Allegiant's booking calendar on 2026-11-06 showed Sunday and Thursday flights for
January through April 2027. A set override in data/overrides.json marks the route
seasonal, with a review by date of 2027-09-01.
