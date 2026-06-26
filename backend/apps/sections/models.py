from django.db import models

from apps.base import TimeStampedModel


class Section(TimeStampedModel):
    property = models.ForeignKey(
        "properties.Property",
        on_delete=models.RESTRICT,
        related_name="sections",
    )
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["property", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["property", "name"],
                name="uq_section_property_name",
            ),
        ]

    def __str__(self):
        return f"{self.name} ({self.property.name})"
