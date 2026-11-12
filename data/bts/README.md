# BTS monthly departures from PDX

`pdx_departures_by_month.json` counts flights leaving PDX each month, by airline and destination, from January 2024 to August 2026.

It was built from the Bureau of Transportation Statistics' monthly on time flight files (Reporting Carrier On Time Performance, 1987 to present), downloaded from https://transtats.bts.gov/PREZIP/. BTS data is a US government work in the public domain.

Format: `{"YYYY-MM": {"<airline code> <destination code>": flights}}`, for example `"2026-08": {"AS ANC": 124}`. Airline codes are BTS reporting codes, so some flights show under the regional airline that operates them, such as OO for SkyWest.

Limits: domestic flights by larger US airlines only, so it leaves out international routes and airlines such as Boutique Air, SeaPort Airlines and Sun Country. BTS publishes a few months behind.

It was used to check seasons and stopped routes in `docs/exceptions.md`. A script to rebuild it is still to come.
