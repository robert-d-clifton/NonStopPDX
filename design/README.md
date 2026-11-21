# Design studies

The four design studies from the first design sessions, November 2026. Each one is a single HTML page you can open in a browser straight from this folder.

| Study | What it explored | Published copy |
|-------|------------------|----------------|
| [1](studies/1/index.html) | First direction: hand drawn maps, a split flap hero, two palettes | [Design Study 1](https://claude.ai/artifact/15bW7cP6BcAhYwuRbE8SQG) |
| [2](studies/2/index.html) | Glass, steel and carpet teal palette, four logo options, a board after the PDX flight boards | [Design Study 2](https://claude.ai/artifact/5sPVpsD48UCAdtbdMe6akm) |
| [3](studies/3/index.html) | Logo A against lowercase versions, three map projections, rivers on short routes | [Design Study 3](https://claude.ai/artifact/QoXFpV1NwhejU6xnStER5Y) |
| [4](studies/4/index.html) | The settled direction: logo A, the flat map, region colors on destination pages, the teal band | [Design Study 4](https://claude.ai/artifact/9VEKMaUAbsLiKPWx1gg5KT) |
| [5](studies/5/index.html) | Terminal map: a transit style diagram, a flat plan and a raised model, all from OpenStreetMap outlines, each with a destination inset | [Design Study 5](https://claude.ai/artifact/GPk22dPBdu5SBhoL9VNnFF) |

Study 5 is built from `studies/5/source.html` and `studies/5/terminal.json` (building outlines, gates and places from OpenStreetMap, © OpenStreetMap contributors, ODbL). Run `python3 design/studies/5/build.py` after editing either.

Study 4 is the reference for the real site. Its map code (d3, a flat Natural Earth projection, route arcs, river labels) is the starting point for the Django templates.

The published copies are private to the project owner.

## Map data

`studies/shared/data.js` holds the route data as of November 7, 2026 plus simplified world coastlines and lakes. `studies/shared/detail.js` holds finer North American coastlines, lakes, rivers and state lines for close up maps. Both come from [Natural Earth](https://www.naturalearthdata.com/), which is public domain, trimmed and rounded to keep them small.

## Decisions

The decisions behind these studies are recorded in the planning doc's design sessions section.

## Motif editor

`motif-editor/index.html` is the source of the [NonStopPDX Motif Editor](https://claude.ai/artifact/3pvz3VMi4CTPCASE51MkP8), where destination drawings are edited shape by shape and assigned to destinations. The page holds the starter drawings and default assignments. Edits are saved in the published page's own storage (`drawings` and `assignments/all`), not in this file, so the published copy is the one to use. This copy is for rebuilding or republishing it.

### Putting edits on the site

The site draws from `data/drawings.json`: every drawing, plus which drawing each destination uses. To bring in edits made in the editor:

1. Export the editor's saved documents to a folder, one JSON file each: `drawings/<id>.json` and `assignments/all.json`. In a Claude session, ask to "update the drawings" and Claude reads them from the editor's storage.
2. Run `python3 tools/merge_drawings.py <folder>`. It replaces edited drawings, adds new ones, applies changed assignments, and refuses a destination that points at a drawing that doesn't exist.
3. Commit `data/drawings.json`. The site picks up the change without a restart.
