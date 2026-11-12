from django.db import models

from .regions import region_for

KINDS = [
    ("year-round", "Year round"),
    ("seasonal", "Seasonal"),
    ("charter", "Charter"),
    ("seasonal charter", "Seasonal charter"),
]


class Airport(models.Model):
    iata = models.CharField("IATA code", max_length=3, unique=True)
    name = models.CharField(max_length=200, blank=True)
    city = models.CharField(max_length=120, blank=True)
    country = models.CharField(max_length=2, blank=True, help_text="ISO country code")
    region = models.CharField(max_length=10, blank=True, help_text="ISO region, like US-OR")
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    distance_mi = models.PositiveIntegerField("miles from PDX", null=True, blank=True)
    wikipedia_article = models.CharField(max_length=200, blank=True)
    is_destination = models.BooleanField(default=False, help_text="Has at least one active nonstop route from PDX")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["city"]

    def __str__(self):
        return f"{self.iata} {self.city}"

    @property
    def international(self) -> bool:
        return bool(self.country) and self.country != "US"

    @property
    def region_group(self):
        return region_for(self.country, self.region)


class Airline(models.Model):
    name = models.CharField(max_length=120, unique=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Route(models.Model):
    """One airline flying nonstop from PDX to one destination."""

    destination = models.ForeignKey(Airport, on_delete=models.CASCADE, related_name="routes")
    airline = models.ForeignKey(Airline, on_delete=models.PROTECT, related_name="routes")
    kind = models.CharField(max_length=20, choices=KINDS, default="year-round")
    begins = models.CharField(max_length=60, blank=True, help_text="As written on Wikipedia")
    ends = models.CharField(max_length=60, blank=True)
    resumes = models.CharField(max_length=60, blank=True)
    note = models.CharField(max_length=200, blank=True)
    source = models.CharField(max_length=20, default="wikipedia", help_text="wikipedia, or manual for an add override")
    kind_source = models.CharField(max_length=20, blank=True, help_text="manual when a set override changed the kind")
    active = models.BooleanField(default=True, help_text="Turned off when a sync no longer finds the route")
    first_seen = models.DateTimeField(null=True, blank=True)
    last_seen = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["destination__city", "airline__name"]
        constraints = [models.UniqueConstraint(fields=["destination", "airline"], name="unique_route")]

    def __str__(self):
        return f"PDX to {self.destination.iata} on {self.airline}"


class Override(models.Model):
    """A hand made fix for source lag. data/overrides.json is the source of truth; see import_overrides."""

    ACTIONS = [("add", "Add a route"), ("remove", "Remove a route"), ("set", "Set a route's kind")]

    action = models.CharField(max_length=10, choices=ACTIONS)
    iata = models.CharField("IATA code", max_length=3)
    city = models.CharField(max_length=120, blank=True)
    airline = models.CharField(max_length=120, blank=True, help_text="Required for add and set")
    kind = models.CharField(max_length=20, choices=KINDS, blank=True)
    reason = models.TextField()
    added = models.DateField(null=True, blank=True)
    review_by = models.DateField(null=True, blank=True)
    note = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return f"{self.action} {self.iata}" + (f" ({self.airline})" if self.airline else "")

    def as_dict(self) -> dict:
        """The shape sync.pdx_routes expects, leaving out empty fields."""
        out = {"action": self.action, "iata": self.iata.upper()}
        for key in ("city", "airline", "kind", "reason", "note"):
            if getattr(self, key):
                out[key] = getattr(self, key)
        for key in ("added", "review_by"):
            if getattr(self, key):
                out[key] = getattr(self, key).isoformat()
        return out


class SyncRun(models.Model):
    """One run of a sync job, kept as an audit trail."""

    KINDS = [("routes", "Wikipedia routes"), ("opensky", "OpenSky departures")]

    kind = models.CharField(max_length=20, choices=KINDS)
    started_at = models.DateTimeField()
    finished_at = models.DateTimeField(null=True, blank=True)
    ok = models.BooleanField(default=False)
    revision = models.BigIntegerField(null=True, blank=True, help_text="Wikipedia revision read")
    destinations = models.PositiveIntegerField(default=0)
    routes = models.PositiveIntegerField(default=0)
    dropped = models.PositiveIntegerField(default=0, help_text="Routes turned off because the sources no longer list them")
    warnings = models.JSONField(default=list, blank=True)
    message = models.TextField(blank=True)

    class Meta:
        ordering = ["-started_at"]

    def __str__(self):
        return f"{self.get_kind_display()} at {self.started_at:%Y-%m-%d %H:%M}"


class WeeklySnapshot(models.Model):
    """Departures OpenSky observed to one destination in one week. Arrival airports are estimates."""

    airport = models.ForeignKey(Airport, on_delete=models.CASCADE, related_name="snapshots")
    week_start = models.DateField()
    departures = models.PositiveIntegerField()
    source = models.CharField(max_length=20, default="opensky")

    class Meta:
        ordering = ["-week_start", "airport__city"]
        constraints = [models.UniqueConstraint(fields=["airport", "week_start", "source"], name="unique_weekly_snapshot")]

    def __str__(self):
        return f"{self.airport.iata} week of {self.week_start}: {self.departures}"
