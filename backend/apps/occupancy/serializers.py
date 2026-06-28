from rest_framework import serializers

from .models import Occupancy


class OccupancySerializer(serializers.ModelSerializer):
    student_full_name = serializers.SerializerMethodField()
    unit_name = serializers.SerializerMethodField()
    property_name = serializers.SerializerMethodField()

    class Meta:
        model = Occupancy
        fields = [
            "id",
            "student",
            "student_full_name",
            "unit",
            "unit_name",
            "property_name",
            "start_date",
            "end_date",
            "billing_mode",
            "is_active",
            "created_at",
        ]
        read_only_fields = ["is_active", "created_at"]

    def get_student_full_name(self, obj):
        return obj.student.full_name()

    def get_unit_name(self, obj):
        return obj.unit.name

    def get_property_name(self, obj):
        return obj.unit.section.property.name
