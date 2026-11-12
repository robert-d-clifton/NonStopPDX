from django.contrib import admin

from .models import Airline, Airport, Override, Route, SyncRun, WeeklySnapshot


class RouteInline(admin.TabularInline):
    model = Route
    extra = 0
    fields = ["airline", "kind", "begins", "resumes", "ends", "source", "kind_source", "active"]
    autocomplete_fields = ["airline"]


@admin.register(Airport)
class AirportAdmin(admin.ModelAdmin):
    list_display = ["iata", "city", "country", "region", "distance_mi", "is_destination"]
    list_filter = ["is_destination", "country"]
    search_fields = ["iata", "city", "name"]
    inlines = [RouteInline]


@admin.register(Airline)
class AirlineAdmin(admin.ModelAdmin):
    search_fields = ["name"]


@admin.register(Route)
class RouteAdmin(admin.ModelAdmin):
    list_display = ["destination", "airline", "kind", "begins", "resumes", "source", "kind_source", "active", "last_seen"]
    list_filter = ["active", "kind", "source", "airline"]
    search_fields = ["destination__iata", "destination__city", "airline__name"]
    autocomplete_fields = ["destination", "airline"]


@admin.register(Override)
class OverrideAdmin(admin.ModelAdmin):
    list_display = ["action", "iata", "airline", "kind", "review_by", "reason"]
    list_filter = ["action"]
    search_fields = ["iata", "airline", "reason"]
    fieldsets = [
        (None, {
            "fields": ["action", "iata", "city", "airline", "kind", "reason", "added", "review_by", "note"],
            "description": "data/overrides.json is the source of truth. After changing overrides here, "
                           "run manage.py export_overrides and commit the file, or the next import will undo the change.",
        }),
    ]


@admin.register(SyncRun)
class SyncRunAdmin(admin.ModelAdmin):
    list_display = ["kind", "started_at", "ok", "revision", "destinations", "routes", "dropped"]
    list_filter = ["kind", "ok"]
    readonly_fields = [f.name for f in SyncRun._meta.fields]


@admin.register(WeeklySnapshot)
class WeeklySnapshotAdmin(admin.ModelAdmin):
    list_display = ["airport", "week_start", "departures", "source"]
    list_filter = ["week_start"]
    search_fields = ["airport__iata", "airport__city"]
