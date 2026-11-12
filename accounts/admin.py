from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import SavedDestination, User


class SavedDestinationInline(admin.TabularInline):
    model = SavedDestination
    extra = 0
    autocomplete_fields = ["airport"]


@admin.register(User)
class NonStopUserAdmin(UserAdmin):
    inlines = [SavedDestinationInline]


@admin.register(SavedDestination)
class SavedDestinationAdmin(admin.ModelAdmin):
    list_display = ["user", "airport", "created_at"]
    autocomplete_fields = ["user", "airport"]
