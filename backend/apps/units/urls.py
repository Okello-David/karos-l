from django.urls import path

from . import views

urlpatterns = [
    path("", views.UnitListView.as_view(), name="unit-list"),
    path("<int:pk>/detail/", views.UnitDetailView.as_view(), name="unit-detail"),
]
