"""Create a placeholder story file for every destination that doesn't have one yet.

Run from the project root, after sync.pdx_routes has written data/routes.json:
    python3 -m sync.seed_stories

Each story lives in stories/<IATA>.md: a few fields at the top, then the story
itself. Existing files are never touched, so it's safe to rerun after new
routes show up. It also lists stories whose destination has left the route
list, so they can be kept, reworked or removed by hand.

Standard library only.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from sync.pdx_routes import DATA_DIR, ROOT

STORIES_DIR = ROOT / "stories"

TEMPLATE = """---
iata: {iata}
city: {city}
status: placeholder
headline:
photo:
photo_credit:
credits:
---

Story to come.
"""


def placeholder(destination: dict) -> str:
    return TEMPLATE.format(iata=destination["iata"], city=destination.get("city") or "")


def seed(destinations: list[dict], stories_dir: Path = STORIES_DIR) -> tuple[list[str], list[str]]:
    """Write missing placeholders. Returns (codes created, codes with a story but no route)."""
    stories_dir.mkdir(exist_ok=True)
    codes = sorted(d["iata"] for d in destinations if d.get("iata"))
    by_code = {d["iata"]: d for d in destinations if d.get("iata")}
    created = []
    for code in codes:
        path = stories_dir / f"{code}.md"
        if not path.exists():
            path.write_text(placeholder(by_code[code]), encoding="utf-8")
            created.append(code)
    orphans = sorted(p.stem for p in stories_dir.glob("*.md") if p.stem not in by_code and p.stem != "README")
    return created, orphans


def main() -> int:
    routes = json.loads((DATA_DIR / "routes.json").read_text(encoding="utf-8"))
    created, orphans = seed(routes["destinations"])
    print(f"Created {len(created)} placeholder stories" + (f": {', '.join(created)}" if created else ""))
    if orphans:
        print("Stories with no current route:", ", ".join(orphans), file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
