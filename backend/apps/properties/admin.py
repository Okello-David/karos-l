from django.contrib import admin

from .models import Property


class SectionInline(admin.TabularInline):
    from apps.sections.models import Section
    model = Section
    extra = 0
    fields = ["name", "is_active"]
    show_change_link = True


@admin.register(Property)
class PropertyAdmin(admin.ModelAdmin):
    list_display = ["name", "code", "section_count", "is_active", "created_at", "updated_at"]
    list_filter = ["is_active"]
    search_fields = ["name", "code", "address"]
    ordering = ["name"]
    readonly_fields = ["created_at", "updated_at"]
    inlines = [SectionInline]

    fieldsets = [
        ("Identification", {
            "fields": ["name", "code"],
        }),
        ("Details", {
            "fields": ["address", "description"],
        }),
        ("Status", {
            "fields": ["is_active"],
        }),
        ("Audit", {
            "fields": ["created_at", "updated_at"],
            "classes": ["collapse"],
        }),
    ]

    @admin.display(description="Sections")
    def section_count(self, obj):
        return obj.sections.count()
