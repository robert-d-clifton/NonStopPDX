"""Region groups for color coding, as settled in design study 4."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Region:
    key: str
    name: str
    color: str  # a CSS token from static/css/site.css
    codes: tuple[str, ...] = ()


REGIONS = (
    Region("nw", "Pacific Northwest", "var(--fir)", ("US-OR", "US-WA", "US-ID", "CA-BC")),
    Region("sw", "California and the Southwest", "var(--timber)", ("US-CA", "US-NV", "US-AZ", "US-NM")),
    Region("mt", "Mountain West", "var(--moss)", ("US-MT", "US-WY", "US-CO", "US-UT", "CA-AB")),
    Region("ce", "Central and East", "var(--glass)"),
    Region("ah", "Alaska and Hawaii", "var(--lagoon)", ("US-AK", "US-HI")),
    Region("in", "International", "var(--violet)"),
)
BY_KEY = {r.key: r for r in REGIONS}


def region_for(country: str, iso_region: str) -> Region:
    if country not in ("US", "CA"):
        return BY_KEY["in"]
    return next((r for r in REGIONS if iso_region in r.codes), BY_KEY["ce"])
