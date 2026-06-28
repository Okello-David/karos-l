from django.urls import path

from . import views

urlpatterns = [
    path("", views.DashboardSummaryView.as_view(), name="dashboard-summary"),
]
