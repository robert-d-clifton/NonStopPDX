# Design studies

The four design studies from the first design sessions, November 2026. Each one is a single HTML page you can open in a browser straight from this folder.

| Study | What it explored | Published copy |
|-------|------------------|----------------|
| [1](studies/1/index.html) | First direction: hand drawn maps, a split flap hero, two palettes | [Design Study 1](https://claude.ai/artifact/15bW7cP6BcAhYwuRbE8SQG) |
| [2](studies/2/index.html) | Glass, steel and carpet teal palette, four logo options, a board after the PDX flight boards | [Design Study 2](https://claude.ai/artifact/5sPVpsD48UCAdtbdMe6akm) |
| [3](studies/3/index.html) | Logo A against lowercase versions, three map projections, rivers on short routes | [Design Study 3](https://claude.ai/artifact/QoXFpV1NwhejU6xnStER5Y) |
| [4](studies/4/index.html) | The settled direction: logo A, the flat map, region colors on destination pages, the teal band | [Design Study 4](https://claude.ai/artifact/9VEKMaUAbsLiKPWx1gg5KT) |

Study 4 is the reference for the real site. Its map code (d3, a flat Natural Earth projection, route arcs, river labels) is the starting point for the Django templates.

The published copies are private to the project owner.

## Map data

`studies/shared/data.js` holds the route data as of November 7, 2026 plus simplified world coastlines and lakes. `studies/shared/detail.js` holds finer North American coastlines, lakes, rivers and state lines for close up maps. Both come from [Natural Earth](https://www.naturalearthdata.com/), which is public domain, trimmed and rounded to keep them small.

## Decisions

The decisions behind these studies are recorded in the planning doc's design sessions section.
