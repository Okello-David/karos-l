from rest_framework import serializers

from .models import Backup


class BackupListSerializer(serializers.ModelSerializer):
    created_by_name = serializers.SerializerMethodField()

    class Meta:
        model = Backup
        fields = [
            "id",
            "created_by",
            "created_by_name",
            "created_at",
            "status",
            "file_size",
            "metadata",
            "notes",
        ]

    def get_created_by_name(self, obj):
        return obj.created_by.username if obj.created_by else "System"


class BackupDetailSerializer(serializers.ModelSerializer):
    created_by_name = serializers.SerializerMethodField()

    class Meta:
        model = Backup
        fields = [
            "id",
            "created_by",
            "created_by_name",
            "created_at",
            "status",
            "file_path",
            "file_size",
            "metadata",
            "notes",
        ]

    def get_created_by_name(self, obj):
        return obj.created_by.username if obj.created_by else "System"


class RestoreSerializer(serializers.Serializer):
    backup_id = serializers.IntegerField()
    confirm = serializers.BooleanField(required=True)

    def validate_confirm(self, value):
        if not value:
            raise serializers.ValidationError("You must confirm the restore operation.")
        return value
