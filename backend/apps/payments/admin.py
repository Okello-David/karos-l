from django.contrib import admin

from .models import Payment


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = [
        "student",
        "amount",
        "payment_date",
        "payment_method",
        "reference",
    ]
    list_filter = ["payment_method", "payment_date"]
    search_fields = [
        "student__first_name",
        "student__last_name",
        "student__student_id_number",
        "reference",
    ]
    ordering = ["-payment_date", "-created_at"]
    readonly_fields = ["created_at", "updated_at"]
    autocomplete_fields = ["student"]
    list_select_related = ["student"]
    date_hierarchy = "payment_date"

    fieldsets = [
        ("Student", {
            "fields": ["student"],
        }),
        ("Payment Details", {
            "fields": [
                ("amount", "payment_date"),
                "payment_method",
                "reference",
            ],
        }),
        ("Notes", {
            "fields": ["notes"],
        }),
        ("Audit", {
            "fields": ["created_at", "updated_at"],
            "classes": ["collapse"],
        }),
    ]
