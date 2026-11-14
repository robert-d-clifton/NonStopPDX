"""Merge edits from the NonStopPDX Motif Editor into data/drawings.json.

The editor saves each changed drawing as a document in its `drawings` collection, and the
assignments it changed in `assignments/all`. Export those documents to a folder (one JSON
file per document, as <folder>/drawings/<id>.json and <folder>/assignments/all.json), then:

    python3 tools/merge_drawings.py <folder>

Drawings in the folder replace the file's copy of the same id, new ones are added, and
changed assignments are applied. Standard library only.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

FILE = Path(__file__).resolve().parent.parent / "data" / "drawings.json"
SHAPES = {"circle", "ellipse", "rect", "poly", "hill", "wave", "line"}
COLORS = {"teal", "aqua", "lagoon", "glass", "water", "violet", "lime", "signal", "fir", "moss", "timber", "sand", "steel", "ink", "snow"}


def body(path: Path) -> dict:
    """A document as exported, with or without a wrapper around its fields."""
    doc = json.loads(path.read_text(encoding="utf-8"))
    for key in ("data", "fields", "document"):
        if isinstance(doc.get(key), dict) and ("shapes" in doc[key] or "map" in doc[key]):
            return doc[key]
    return doc


def check(drawing_id: str, drawing: dict) -> None:
    for i, s in enumerate(drawing.get("shapes", [])):
        if s.get("t") not in SHAPES:
            raise ValueError(f"{drawing_id}: shape {i + 1} has an unknown type {s.get('t')!r}")
        if s.get("c") not in COLORS:
            raise ValueError(f"{drawing_id}: shape {i + 1} has an unknown color {s.get('c')!r}")


def main(folder: Path) -> None:
    data = json.loads(FILE.read_text(encoding="utf-8"))
    changed, removed = [], []
    for path in sorted((folder / "drawings").glob("*.json")):
        drawing_id, doc = path.stem, body(path)
        if doc.get("deleted"):
            if data["drawings"].pop(drawing_id, None) is not None:
                removed.append(drawing_id)
            continue
        drawing = {k: doc[k] for k in ("name", "kind", "code", "shapes") if k in doc}
        check(drawing_id, drawing)
        if data["drawings"].get(drawing_id) != drawing:
            data["drawings"][drawing_id] = drawing
            changed.append(drawing_id)
    reassigned = []
    assignments_file = folder / "assignments" / "all.json"
    if assignments_file.exists():
        for code, drawing_id in body(assignments_file).get("map", {}).items():
            if drawing_id not in data["drawings"]:
                print(f"Skipping {code}: no drawing named {drawing_id!r}", file=sys.stderr)
                continue
            if data["assignments"].get(code) != drawing_id:
                data["assignments"][code] = drawing_id
                reassigned.append(f"{code} to {drawing_id}")
    missing = sorted(code for code, d in data["assignments"].items() if d not in data["drawings"])
    if missing:
        raise SystemExit(f"These destinations point at drawings that don't exist: {', '.join(missing)}")
    data["assignments"] = dict(sorted(data["assignments"].items()))
    FILE.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Drawings changed: {', '.join(changed) or 'none'}")
    print(f"Drawings removed: {', '.join(removed) or 'none'}")
    print(f"Destinations reassigned: {', '.join(reassigned) or 'none'}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    main(Path(sys.argv[1]))
