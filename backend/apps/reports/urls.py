from django.urls import path

from . import views

urlpatterns = [
    path("occupancy/", views.OccupancyReportView.as_view(), name="report-occupancy"),
    path("financial/", views.FinancialReportView.as_view(), name="report-financial"),
    path("occupants/", views.OccupantsReportView.as_view(), name="report-occupants"),
]
