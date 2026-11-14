from django.urls import path

from . import views

app_name = "routes"

urlpatterns = [
    path("", views.home, name="home"),
    path("to/<str:code>/", views.destination, name="destination"),
    path("airlines/", views.airlines, name="airlines"),
    path("airlines/<slug:slug>/", views.airline, name="airline"),
]
