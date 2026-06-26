from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.translation import gettext_lazy as _

from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = [
        "username",
        "email",
        "first_name",
        "last_name",
        "is_staff",
        "is_active",
        "date_joined",
    ]
    list_filter = ["is_staff", "is_superuser", "is_active", "groups"]
    search_fields = ["username", "email", "first_name", "last_name"]
    ordering = ["username"]
    readonly_fields = ["last_login", "date_joined"]

    fieldsets = [
        (None, {
            "fields": ["username", "password"],
        }),
        (_("Personal info"), {
            "fields": [("first_name", "last_name"), "email"],
        }),
        (_("Permissions"), {
            "fields": [
                "is_active",
                "is_staff",
                "is_superuser",
                "groups",
                "user_permissions",
            ],
        }),
        (_("Important dates"), {
            "fields": ["last_login", "date_joined"],
            "classes": ["collapse"],
        }),
    ]

    add_fieldsets = [
        (
            None,
            {
                "classes": ["wide"],
                "fields": ["username", "email", "password1", "password2"],
            },
        ),
    ]
