from django.core.exceptions import ObjectDoesNotExist
from rest_framework import serializers

from .models import Payment, Receipt


class PaymentSerializer(serializers.ModelSerializer):
    student_name = serializers.SerializerMethodField()
    receipt_id = serializers.SerializerMethodField()
    receipt_number = serializers.SerializerMethodField()

    class Meta:
        model = Payment
        fields = [
            "id",
            "student",
            "student_name",
            "amount",
            "payment_date",
            "payment_method",
            "reference",
            "notes",
            "receipt_id",
            "receipt_number",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]

    def get_student_name(self, obj):
        return obj.student.full_name()

    def get_receipt_id(self, obj):
        try:
            return obj.receipt.id
        except ObjectDoesNotExist:
            return None

    def get_receipt_number(self, obj):
        try:
            return obj.receipt.receipt_number
        except ObjectDoesNotExist:
            return None

    def validate_reference(self, value):
        if value and Payment.objects.filter(reference=value).exclude(
            id=self.instance.id if self.instance else None
        ).exists():
            raise serializers.ValidationError(
                "A payment with this reference already exists."
            )
        return value


class ReceiptSerializer(serializers.ModelSerializer):
    payment_id = serializers.IntegerField(source="payment.id")
    receipt_number = serializers.CharField()
    issued_at = serializers.DateTimeField()
    outstanding_balance_after = serializers.DecimalField(max_digits=10, decimal_places=2)
    student_name = serializers.CharField()
    student_id_number = serializers.CharField()
    unit_name = serializers.CharField()
    property_name = serializers.CharField()
    amount = serializers.DecimalField(max_digits=10, decimal_places=2)
    payment_date = serializers.DateField()
    payment_method = serializers.CharField()
    reference = serializers.CharField()

    class Meta:
        model = Receipt
        fields = [
            "id",
            "payment_id",
            "receipt_number",
            "issued_at",
            "outstanding_balance_after",
            "student_name",
            "student_id_number",
            "unit_name",
            "property_name",
            "amount",
            "payment_date",
            "payment_method",
            "reference",
        ]
