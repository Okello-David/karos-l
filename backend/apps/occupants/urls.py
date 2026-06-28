from django.urls import path

from . import views

urlpatterns = [
    path("", views.StudentViewSet.as_view({"get": "list", "post": "create"}), name="occupant-list"),
    path("<int:pk>/", views.StudentViewSet.as_view({"get": "retrieve", "put": "update", "patch": "partial_update"}), name="occupant-detail"),
    path("<int:pk>/archive/", views.StudentViewSet.as_view({"post": "archive"}), name="occupant-archive"),
]
