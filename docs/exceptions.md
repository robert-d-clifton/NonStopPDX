# Known differences from FlyPDX

Checked 2026-11-03 against https://www.flypdx.com/NonstopDestinations
using Wikipedia revision 1382252995. Both lists have 90 destinations.

| Code | City | Where it shows up | Why |
|------|------|-------------------|-----|
| HDN | Hayden | Wikipedia only | Future route, Alaska begins February 11, 2027. Expected. |
| MSY | New Orleans | FlyPDX only | Alaska seasonal route, paused right now. Added through data/overrides.json, review by 2027-02-01. |

SeaPort Airlines (RDM, BFI) is confirmed by FlyPDX, so it's not an exception.

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
