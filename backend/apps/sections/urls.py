from django.urls import path

from . import views

urlpatterns = [
    path("", views.SectionListView.as_view(), name="section-list"),
]
