from django.contrib import admin

from .models import Story


@admin.register(Story)
class StoryAdmin(admin.ModelAdmin):
    list_display = ["airport", "status", "headline", "updated_at"]
    list_filter = ["status"]
    search_fields = ["airport__iata", "airport__city", "headline", "body"]
    autocomplete_fields = ["airport"]
    fieldsets = [
        (None, {
            "fields": ["airport", "status", "headline", "body", "photo", "photo_credit", "credits"],
            "description": "The stories folder is the source of truth. After editing here, run manage.py export_stories "
                           "and commit the files, or the next import will undo the change.",
        }),
    ]
