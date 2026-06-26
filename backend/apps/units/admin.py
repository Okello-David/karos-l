from django.contrib import admin

from .models import Unit


class OccupancyInline(admin.TabularInline):
    from apps.occupancy.models import Occupancy
    model = Occupancy
    extra = 0
    fields = ["student", "start_date", "end_date", "billing_mode", "is_active"]
    show_change_link = True
    autocomplete_fields = ["student"]


@admin.register(Unit)
class UnitAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "property_name",
        "section",
        "capacity",
        "occupancy_status",
        "semester_price",
        "monthly_price",
        "is_active",
    ]
    list_filter = ["is_active", "section__property", "section"]
    search_fields = ["name", "section__name", "section__property__name"]
    ordering = ["section__property", "section", "name"]
    readonly_fields = ["created_at", "updated_at"]
    autocomplete_fields = ["section"]
    list_select_related = ["section__property"]
    inlines = [OccupancyInline]

    fieldsets = [
        ("Location", {
            "fields": ["section", "name"],
        }),
        ("Capacity & Pricing", {
            "fields": [
                "capacity",
                ("semester_price", "monthly_price"),
            ],
        }),
        ("Status", {
            "fields": ["is_active"],
        }),
        ("Audit", {
            "fields": ["created_at", "updated_at"],
            "classes": ["collapse"],
        }),
    ]

    @admin.display(description="Property", ordering="section__property__name")
    def property_name(self, obj):
        return obj.section.property.name

    @admin.display(description="Occupancy")
    def occupancy_status(self, obj):
        current = obj.current_occupant_count()
        return f"{current} / {obj.capacity}"
