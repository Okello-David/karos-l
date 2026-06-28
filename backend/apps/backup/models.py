from django.conf import settings
from django.db import models


class Backup(models.Model):

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        IN_PROGRESS = "in_progress", "In Progress"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="backups",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    file_path = models.CharField(max_length=500, blank=True)
    file_size = models.PositiveBigIntegerField(null=True, blank=True, help_text="Size in bytes")
    metadata = models.JSONField(null=True, blank=True, help_text="Backup metadata (record counts, etc.)")
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Backup #{self.id} ({self.created_at:%Y-%m-%d %H:%M}) - {self.status}"
