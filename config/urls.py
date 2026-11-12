from django.contrib import admin
from django.urls import include, path

admin.site.site_header = "NonStopPDX admin"
admin.site.site_title = "NonStopPDX admin"
admin.site.index_title = "Routes, stories and accounts"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("routes.urls")),
]
