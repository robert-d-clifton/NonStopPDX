"""Destination drawings from data/drawings.json, read once and again whenever the file changes."""

from __future__ import annotations

import json
from functools import lru_cache

from django.conf import settings


@lru_cache(maxsize=2)
def _load(mtime: float) -> dict:
    return json.loads(settings.DRAWINGS_FILE.read_text(encoding="utf-8"))


def drawing_for(iata: str) -> list | None:
    """The shapes of the drawing assigned to a destination, or None if it has none."""
    path = settings.DRAWINGS_FILE
    if not path.exists():
        return None
    data = _load(path.stat().st_mtime)
    drawing = data["drawings"].get(data["assignments"].get(iata, ""))
    return drawing["shapes"] if drawing else None
