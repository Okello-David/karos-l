from django.conf import settings
from django.db import models


class AuditLog(models.Model):

    class EntityType(models.TextChoices):
        OCCUPANT = "occupant", "Occupant"
        OCCUPANCY = "occupancy", "Occupancy"
        PAYMENT = "payment", "Payment"
        RECEIPT = "receipt", "Receipt"
        PROPERTY = "property", "Property"
        SECTION = "section", "Section"
        UNIT = "unit", "Unit"
        PRICING_RULE = "pricing_rule", "Pricing Rule"
        USER = "user", "User"
        BACKUP = "backup", "Backup"

    class Action(models.TextChoices):
        CREATE = "create", "Create"
        UPDATE = "update", "Update"
        DELETE = "delete", "Delete"
        ARCHIVE = "archive", "Archive"
        ASSIGN = "assign", "Assign"
        CHECKOUT = "checkout", "Checkout"
        RECORD_PAYMENT = "record_payment", "Record Payment"
        LOGIN = "login", "Login"
        OTHER = "other", "Other"

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_logs",
    )
    entity_type = models.CharField(max_length=20, choices=EntityType.choices)
    entity_id = models.PositiveBigIntegerField(null=True, blank=True)
    action = models.CharField(max_length=20, choices=Action.choices)
    description = models.TextField()
    changes = models.JSONField(null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-timestamp"]
        indexes = [
            models.Index(fields=["entity_type", "entity_id"]),
            models.Index(fields=["action"]),
            models.Index(fields=["actor"]),
        ]

    def __str__(self):
        return f"{self.get_action_display()} {self.get_entity_type_display()} #{self.entity_id} by {self.actor} at {self.timestamp}"
