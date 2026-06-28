from django.urls import path

from . import views

urlpatterns = [
    path("", views.OccupancyViewSet.as_view({
        "get": "list",
        "post": "create",
    })),
    path("<int:pk>/", views.OccupancyViewSet.as_view({
        "get": "retrieve",
        "patch": "partial_update",
    })),
    path("<int:pk>/checkout/", views.OccupancyViewSet.as_view({
        "post": "checkout",
    })),
    path("summary/", views.OccupancyViewSet.as_view({
        "get": "summary",
    })),
]
