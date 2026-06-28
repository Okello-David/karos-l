from django.urls import path

from . import views

urlpatterns = [
    path("backups/", views.BackupListCreateView.as_view(), name="backup-list"),
    path("backups/<int:pk>/", views.BackupDetailView.as_view(), name="backup-detail"),
    path("backups/<int:pk>/restore/", views.BackupRestoreView.as_view(), name="backup-restore"),
    path("backups/<int:pk>/validate/", views.BackupValidateView.as_view(), name="backup-validate"),
    path("backups/export/", views.ExportView.as_view(), name="backup-export"),
]
