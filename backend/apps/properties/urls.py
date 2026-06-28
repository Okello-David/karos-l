from django.urls import path

from . import views

urlpatterns = [
    path("", views.PropertyListView.as_view(), name="property-list"),
    path("explorer/", views.PropertyExplorerView.as_view(), name="property-explorer"),
]
