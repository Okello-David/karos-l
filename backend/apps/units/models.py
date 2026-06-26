from django.core.exceptions import ValidationError
from django.db import models

from apps.base import TimeStampedModel


def validate_positive(value):
    if value <= 0:
        raise ValidationError(f"{value} is not a positive number.")


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
        ordering = ["section", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["section", "name"],
                name="uq_unit_section_name",
            ),
        ]
        indexes = [
            models.Index(fields=["capacity"]),
            models.Index(fields=["is_active"]),
        ]

    def __str__(self):
        return f"{self.name} ({self.section.property.name} / {self.section.name})"

    def current_occupant_count(self):
        return self.occupancies.filter(end_date__isnull=True).count()

    def is_full(self):
        return self.current_occupant_count() >= self.capacity
