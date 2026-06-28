from django.urls import path

from . import views

urlpatterns = [
    path("", views.AuditLogListView.as_view(), name="audit-list"),
    path("<int:pk>/", views.AuditLogDetailView.as_view(), name="audit-detail"),
    path("entity-types/", views.AuditEntityTypesView.as_view(), name="audit-entity-types"),
    path("actions/", views.AuditActionsView.as_view(), name="audit-actions"),
]
