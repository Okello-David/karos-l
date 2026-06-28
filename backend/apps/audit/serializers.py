from django.contrib.auth import get_user_model
from rest_framework import serializers

from .models import AuditLog

User = get_user_model()


class AuditActorSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "username"]


class AuditLogSerializer(serializers.ModelSerializer):
    actor = AuditActorSerializer(read_only=True)
    entity_type_display = serializers.SerializerMethodField()
    action_display = serializers.SerializerMethodField()

    class Meta:
        model = AuditLog
        fields = [
            "id",
            "actor",
            "entity_type",
            "entity_type_display",
            "entity_id",
            "action",
            "action_display",
            "description",
            "changes",
            "ip_address",
            "timestamp",
        ]

    def get_entity_type_display(self, obj):
        return obj.get_entity_type_display()

    def get_action_display(self, obj):
        return obj.get_action_display()
