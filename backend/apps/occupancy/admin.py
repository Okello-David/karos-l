from django.contrib import admin

from .models import Occupancy


@admin.register(Occupancy)
class OccupancyAdmin(admin.ModelAdmin):
    list_display = [
        "student",
        "unit",
        "property_via_unit",
        "start_date",
        "end_date",
        "billing_mode",
        "is_active",
    ]
    list_filter = [
        "billing_mode",
        "is_active",
        "start_date",
        "unit__section__property",
    ]
    search_fields = [
        "student__first_name",
        "student__last_name",
        "student__student_id_number",
        "unit__name",
        "unit__section__name",
    ]
    ordering = ["-start_date"]
    readonly_fields = ["created_at"]
    autocomplete_fields = ["student", "unit"]
    list_select_related = ["student", "unit__section__property"]
    date_hierarchy = "start_date"

    fieldsets = [
        ("Student & Unit", {
            "fields": ["student", "unit"],
        }),
        ("Period", {
            "fields": [("start_date", "end_date")],
        }),
        ("Billing", {
            "fields": ["billing_mode"],
        }),
        ("Status", {
            "fields": ["is_active"],
        }),
        ("Audit", {
            "fields": ["created_at"],
            "classes": ["collapse"],
        }),
    ]

    @admin.display(description="Property", ordering="unit__section__property__name")
    def property_via_unit(self, obj):
        return obj.unit.section.property.name
