from django.contrib import admin
from django.db.models import Prefetch

from apps.occupancy.models import Occupancy
from apps.payments.models import Payment

from .models import Student


class OccupancyInline(admin.TabularInline):
    model = Occupancy
    extra = 0
    fields = ["unit", "start_date", "end_date", "billing_mode"]
    show_change_link = True
    autocomplete_fields = ["unit"]
    ordering = ["-start_date"]


class PaymentInline(admin.TabularInline):
    model = Payment
    extra = 0
    fields = ["amount", "payment_date", "payment_method", "reference"]
    show_change_link = True
    ordering = ["-payment_date"]


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = [
        "last_name",
        "first_name",
        "email",
        "phone",
        "student_id_number",
        "current_unit",
        "is_active",
    ]
    list_filter = ["is_active"]
    search_fields = ["first_name", "last_name", "email", "student_id_number", "phone"]
    ordering = ["last_name", "first_name"]
    readonly_fields = ["created_at", "updated_at"]
    inlines = [OccupancyInline, PaymentInline]

    fieldsets = [
        ("Name", {
            "fields": [("first_name", "last_name")],
        }),
        ("Contact", {
            "fields": ["email", "phone"],
        }),
        ("Identification", {
            "fields": ["student_id_number"],
        }),
        ("Status", {
            "fields": ["is_active"],
        }),
        ("Audit", {
            "fields": ["created_at", "updated_at"],
            "classes": ["collapse"],
        }),
    ]

    @admin.display(description="Current Unit")
    def current_unit(self, obj):
        active = getattr(obj, "_active_occupancy", None)
        if active:
            return str(active.unit)
        return "—"

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .prefetch_related(
                Prefetch(
                    "occupancies",
                    queryset=Occupancy.objects.filter(
                        end_date__isnull=True
                    ).select_related("unit__section__property"),
                    to_attr="_active_occupancy",
                )
            )
        )
