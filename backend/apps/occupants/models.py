from django.db import models

from apps.core.mixins import TimeStampedModel


class Student(TimeStampedModel):
    first_name = models.CharField(max_length=150)
    last_name = models.CharField(max_length=150)
    email = models.EmailField(unique=True, blank=True, null=True)
    phone = models.CharField(max_length=20, blank=True)
    student_id_number = models.CharField(
        max_length=50,
        unique=True,
        blank=True,
        null=True,
        help_text="External identifier from the educational institution",
    )
    national_id = models.CharField(
        max_length=50,
        unique=True,
        blank=True,
        null=True,
        help_text="Government-issued national identification number",
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["last_name", "first_name"]
        indexes = [
            models.Index(fields=["last_name", "first_name"]),
        ]

    def __str__(self):
        return f"{self.first_name} {self.last_name}"

    def full_name(self):
        return f"{self.first_name} {self.last_name}"
