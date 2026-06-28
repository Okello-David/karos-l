from django.db import models

from apps.core.mixins import TimeStampedModel
from apps.core.constants import PaymentMethod
from apps.core.validators import validate_positive


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


class Receipt(models.Model):
    payment = models.OneToOneField(
        Payment,
        on_delete=models.RESTRICT,
        related_name="receipt",
    )
    receipt_number = models.CharField(max_length=20, unique=True)
    issued_at = models.DateTimeField(auto_now_add=True)

    outstanding_balance_after = models.DecimalField(
        max_digits=10, decimal_places=2,
    )

    student_name = models.CharField(max_length=300)
    student_id_number = models.CharField(max_length=50, blank=True)
    unit_name = models.CharField(max_length=255)
    property_name = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_date = models.DateField()
    payment_method = models.CharField(max_length=10)
    reference = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-issued_at"]
        indexes = [
            models.Index(fields=["receipt_number"]),
            models.Index(fields=["student_name"]),
            models.Index(fields=["payment_date"]),
        ]

    def __str__(self):
        return f"{self.receipt_number} - {self.student_name}"
