from rest_framework import serializers

from apps.occupancy.models import Occupancy
from apps.sections.models import Section
from apps.units.models import Unit

from .models import Property


class PropertySerializer(serializers.ModelSerializer):
    class Meta:
        model = Property
        fields = ["id", "name"]


class UnitExplorerSerializer(serializers.ModelSerializer):
    current_occupant_count = serializers.SerializerMethodField()
    available_spaces = serializers.SerializerMethodField()
    is_full = serializers.SerializerMethodField()
    occupancy_percentage = serializers.SerializerMethodField()
    active_occupants = serializers.SerializerMethodField()

    class Meta:
        model = Unit
        fields = [
            "id", "name", "capacity",
            "semester_price", "monthly_price",
            "current_occupant_count", "available_spaces",
            "is_full", "occupancy_percentage",
            "active_occupants",
        ]

    def get_current_occupant_count(self, obj):
        active = getattr(obj, "active_occupancies", None)
        if active is not None:
            return len(active)
        return obj.current_occupant_count()

    def get_available_spaces(self, obj):
        return obj.capacity - self.get_current_occupant_count(obj)

    def get_is_full(self, obj):
        return self.get_current_occupant_count(obj) >= obj.capacity

    def get_occupancy_percentage(self, obj):
        if obj.capacity == 0:
            return 0
        return int(round((self.get_current_occupant_count(obj) / obj.capacity) * 100))

    def get_active_occupants(self, obj):
        active = getattr(obj, "active_occupancies", None)
        if active is not None:
            return [
                {"id": occ.student.id, "name": occ.student.full_name()}
                for occ in active
            ]
        return []


class SectionExplorerSerializer(serializers.ModelSerializer):
    units = UnitExplorerSerializer(many=True, read_only=True)

    class Meta:
        model = Section
        fields = ["id", "name", "units"]


class PropertyExplorerSerializer(serializers.ModelSerializer):
    sections = SectionExplorerSerializer(many=True, read_only=True)

    class Meta:
        model = Property
        fields = ["id", "name", "code", "sections"]
