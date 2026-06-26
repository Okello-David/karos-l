from django.contrib import admin

from .models import Section


class UnitInline(admin.TabularInline):
    from apps.units.models import Unit
    model = Unit
    extra = 0
    fields = ["name", "capacity", "semester_price", "monthly_price", "is_active"]
    show_change_link = True


@admin.register(Section)
class SectionAdmin(admin.ModelAdmin):
    list_display = ["name", "property", "unit_count", "is_active", "created_at", "updated_at"]
    list_filter = ["is_active", "property"]
    search_fields = ["name", "property__name"]
    ordering = ["property", "name"]
    readonly_fields = ["created_at", "updated_at"]
    autocomplete_fields = ["property"]
    list_select_related = ["property"]
    inlines = [UnitInline]

    fieldsets = [
        ("Property", {
            "fields": ["property", "name"],
        }),
        ("Details", {
            "fields": ["description"],
        }),
        ("Status", {
            "fields": ["is_active"],
        }),
        ("Audit", {
            "fields": ["created_at", "updated_at"],
            "classes": ["collapse"],
        }),
    ]

    @admin.display(description="Units")
    def unit_count(self, obj):
        return obj.units.count()
