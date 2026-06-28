from decimal import Decimal

from rest_framework import serializers

from apps.payments.services import PaymentService

from .models import Unit


class UnitSerializer(serializers.ModelSerializer):
    current_occupant_count = serializers.SerializerMethodField()
    available_spaces = serializers.SerializerMethodField()
    is_full = serializers.SerializerMethodField()

    class Meta:
        model = Unit
        fields = [
            "id",
            "name",
            "capacity",
            "current_occupant_count",
            "available_spaces",
            "is_full",
        ]

    def get_current_occupant_count(self, obj):
        return obj.current_occupant_count()

    def get_available_spaces(self, obj):
        return obj.capacity - obj.current_occupant_count()

    def get_is_full(self, obj):
        return obj.is_full()


class UnitDetailSerializer(serializers.ModelSerializer):
    section_name = serializers.CharField(source="section.name")
    property_name = serializers.CharField(source="section.property.name")
    current_occupant_count = serializers.SerializerMethodField()
    available_spaces = serializers.SerializerMethodField()
    is_full = serializers.SerializerMethodField()
    current_occupants = serializers.SerializerMethodField()
    occupancy_history = serializers.SerializerMethodField()

    class Meta:
        model = Unit
        fields = [
            "id", "name", "capacity",
            "semester_price", "monthly_price",
            "section_name", "property_name",
            "current_occupant_count", "available_spaces", "is_full",
            "current_occupants", "occupancy_history",
        ]

    def get_current_occupant_count(self, obj):
        return obj.current_occupant_count()

    def get_available_spaces(self, obj):
        return obj.capacity - obj.current_occupant_count()

    def get_is_full(self, obj):
        return obj.current_occupant_count() >= obj.capacity

    def get_current_occupants(self, obj):
        active_occs = obj.occupancies.filter(
            end_date__isnull=True
        ).select_related("student")
        result = []
        for occ in active_occs:
            student = occ.student
            balance = PaymentService.calculate_student_balance(student.id)
            result.append({
                "id": student.id,
                "name": student.full_name(),
                "occupancy_id": occ.id,
                "start_date": occ.start_date.isoformat(),
                "billing_mode": occ.billing_mode,
                "balance": balance["balance"],
                "has_balance": Decimal(balance["balance"]) > 0,
            })
        return result

    def get_occupancy_history(self, obj):
        occs = obj.occupancies.select_related("student").order_by("-start_date")[:10]
        return [
            {
                "id": occ.id,
                "student_name": occ.student.full_name(),
                "start_date": occ.start_date.isoformat(),
                "end_date": occ.end_date.isoformat() if occ.end_date else None,
                "is_active": occ.is_active,
            }
            for occ in occs
        ]
