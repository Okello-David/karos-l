from django.core.exceptions import ValidationError
from django.db import models

from apps.base import TimeStampedModel
from apps.choices import PaymentMethod


def validate_positive(value):
    if value <= 0:
        raise ValidationError(f"{value} is not a positive number.")


class Payment(TimeStampedModel):
    student = models.ForeignKey(
        "occupants.Student",
        on_delete=models.RESTRICT,
        related_name="payments",
    )
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[validate_positive],
    )
    payment_date = models.DateField()
    payment_method = models.CharField(
        max_length=10,
        choices=PaymentMethod.choices,
    )
    reference = models.CharField(
        max_length=255,
        blank=True,
        help_text="External transaction reference",
    )
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-payment_date", "-created_at"]
        indexes = [
            models.Index(fields=["student", "payment_date"]),
            models.Index(fields=["payment_date"]),
        ]

    def __str__(self):
        return f"{self.student.full_name()} - {self.amount} ({self.payment_date})"
