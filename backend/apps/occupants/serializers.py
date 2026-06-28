from rest_framework import serializers

from .models import Student


class StudentSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = Student
        fields = [
            "id",
            "first_name",
            "last_name",
            "full_name",
            "email",
            "phone",
            "student_id_number",
            "national_id",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]

    def get_full_name(self, obj):
        return obj.full_name()

    def validate_phone(self, value):
        if value and not value.isdigit() and not value.startswith("+"):
            raise serializers.ValidationError(
                "Phone number must contain only digits and may start with +."
            )
        return value

    def validate_email(self, value):
        if value and Student.objects.filter(email=value).exclude(id=self.instance.id if self.instance else None).exists():
            raise serializers.ValidationError("A student with this email already exists.")
        return value
