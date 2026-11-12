from django.urls import path

from . import views

app_name = "routes"

urlpatterns = [
    path("", views.departures, name="departures"),
]
