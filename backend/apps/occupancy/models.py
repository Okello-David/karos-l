from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from apps.choices import BillingMode


class Occupancy(models.Model):
    student = models.ForeignKey(
        "occupants.Student",
        on_delete=models.RESTRICT,
        related_name="occupancies",
    )
    unit = models.ForeignKey(
        "units.Unit",
        on_delete=models.RESTRICT,
        related_name="occupancies",
    )
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True, help_text="Null means currently active")
    billing_mode = models.CharField(
        max_length=10,
        choices=BillingMode.choices,
        default=BillingMode.SEMESTER,
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = "occupancies"
        ordering = ["-start_date"]
        constraints = [
            models.CheckConstraint(
                condition=Q(end_date__isnull=True) | Q(end_date__gt=models.F("start_date")),
                name="ck_occupancy_end_date_after_start",
            ),
        ]
        indexes = [
            models.Index(fields=["start_date"]),
            models.Index(
                fields=["student"],
                condition=Q(end_date__isnull=True),
                name="idx_occ_active_student",
            ),
            models.Index(
                fields=["unit"],
                condition=Q(end_date__isnull=True),
                name="idx_occ_active_unit",
            ),
        ]

    def clean(self):
        if self.end_date and self.end_date <= self.start_date:
            raise ValidationError({"end_date": "End date must be after start date."})
        if self.end_date is None:
            active_exists = (
                Occupancy.objects
                .filter(student=self.student, end_date__isnull=True)
                .exclude(pk=self.pk)
                .exists()
            )
            if active_exists:
                raise ValidationError(
                    "This student already has an active occupancy. "
                    "Close it before creating a new one."
                )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        end = self.end_date or "present"
        return f"{self.student.full_name()} in {self.unit.name} ({self.start_date} - {end})"
