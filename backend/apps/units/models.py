from django.db import models

from apps.core.constants import BillingMode
from apps.core.mixins import TimeStampedModel
from apps.core.validators import validate_positive


class UnitStatus(models.TextChoices):
    ACTIVE = "active", "Active"
    MAINTENANCE = "maintenance", "Maintenance"
    ARCHIVED = "archived", "Archived"


class Unit(TimeStampedModel):
    section = models.ForeignKey(
        "sections.Section",
        on_delete=models.RESTRICT,
        related_name="units",
    )
    name = models.CharField(max_length=255)
    capacity = models.PositiveSmallIntegerField(
        validators=[validate_positive],
        help_text="Maximum number of occupants",
    )
    status = models.CharField(
        max_length=20,
        choices=UnitStatus.choices,
        default=UnitStatus.ACTIVE,
    )
    order = models.PositiveSmallIntegerField(default=0)
    semester_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[validate_positive],
    )
    monthly_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[validate_positive],
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["section", "order", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["section", "name"],
                name="uq_unit_section_name",
            ),
        ]
        indexes = [
            models.Index(fields=["capacity"]),
            models.Index(fields=["status"]),
        ]

    def save(self, *args, **kwargs):
        self.is_active = (self.status == UnitStatus.ACTIVE)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} ({self.section.property.name} / {self.section.name})"

    def current_occupant_count(self):
        return self.occupancies.filter(end_date__isnull=True).count()

    def is_full(self):
        return self.current_occupant_count() >= self.capacity


class PricingRule(TimeStampedModel):
    unit = models.ForeignKey(
        Unit,
        on_delete=models.CASCADE,
        related_name="pricing_rules",
    )
    billing_mode = models.CharField(
        max_length=10,
        choices=BillingMode.choices,
    )
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[validate_positive],
    )
    effective_date = models.DateField()

    class Meta:
        ordering = ["-effective_date"]
        indexes = [
            models.Index(fields=["unit", "effective_date"]),
        ]

    def __str__(self):
        return f"{self.unit.name} - {self.billing_mode} - {self.price} (from {self.effective_date})"
