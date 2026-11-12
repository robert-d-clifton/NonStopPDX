from django.db import models


class Story(models.Model):
    """A destination's story. stories/<IATA>.md is the source of truth; see import_stories and export_stories."""

    STATUSES = [("placeholder", "Placeholder"), ("draft", "Draft"), ("ready", "Ready")]

    airport = models.OneToOneField("routes.Airport", on_delete=models.CASCADE, related_name="story")
    status = models.CharField(max_length=20, choices=STATUSES, default="placeholder")
    headline = models.CharField(max_length=200, blank=True)
    body = models.TextField(blank=True, help_text="Markdown")
    photo = models.CharField(max_length=300, blank=True, help_text="Path or link to a photo")
    photo_credit = models.CharField(max_length=300, blank=True)
    credits = models.CharField(max_length=500, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["airport__city"]
        verbose_name_plural = "stories"

    def __str__(self):
        return f"{self.airport.iata} story ({self.status})"
