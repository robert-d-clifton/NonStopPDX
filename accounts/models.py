from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """Our own user model from day one, so fields can be added later without a painful migration."""

    class Meta:
        db_table = "accounts_user"


class SavedDestination(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="saved_destinations")
    airport = models.ForeignKey("routes.Airport", on_delete=models.CASCADE, related_name="saved_by")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["user", "airport"], name="unique_saved_destination")]
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user} saved {self.airport.iata}"
