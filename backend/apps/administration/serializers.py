from django.contrib.auth.models import Group
from rest_framework import serializers

from apps.accounts.models import User
from apps.properties.models import Property
from apps.sections.models import Section
from apps.units.models import PricingRule, Unit


class AdminPropertySerializer(serializers.ModelSerializer):
    class Meta:
        model = Property
        fields = ["id", "name", "code", "address", "description", "is_active", "created_at", "updated_at"]
        read_only_fields = ["created_at", "updated_at"]


class AdminSectionSerializer(serializers.ModelSerializer):
    property_name = serializers.CharField(source="property.name", read_only=True)

    class Meta:
        model = Section
        fields = ["id", "property", "property_name", "name", "description", "is_active", "order", "created_at", "updated_at"]
        read_only_fields = ["created_at", "updated_at"]


class AdminSectionReorderSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    order = serializers.IntegerField()


class AdminUnitSerializer(serializers.ModelSerializer):
    section_name = serializers.CharField(source="section.name", read_only=True)
    property_name = serializers.CharField(source="section.property.name", read_only=True)

    class Meta:
        model = Unit
        fields = [
            "id", "section", "section_name", "property_name",
            "name", "capacity", "status", "order",
            "semester_price", "monthly_price",
            "is_active", "created_at", "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at", "is_active"]


class PricingRuleSerializer(serializers.ModelSerializer):
    unit_name = serializers.CharField(source="unit.name", read_only=True)

    class Meta:
        model = PricingRule
        fields = ["id", "unit", "unit_name", "billing_mode", "price", "effective_date", "created_at"]
        read_only_fields = ["created_at"]

    def validate(self, data):
        if data.get("price") is not None and data["price"] <= 0:
            raise serializers.ValidationError({"price": "Price must be positive."})
        return data


class AdminUserSerializer(serializers.ModelSerializer):
    groups = serializers.PrimaryKeyRelatedField(
        many=True, queryset=Group.objects.all(), required=False
    )
    group_names = serializers.ListField(
        child=serializers.CharField(), read_only=True, source="groups.values_list('name', flat=True)"
    )

    class Meta:
        model = User
        fields = [
            "id", "username", "email", "first_name", "last_name",
            "is_active", "is_staff", "is_superuser",
            "groups", "group_names",
            "date_joined", "last_login",
        ]
        read_only_fields = ["date_joined", "last_login", "is_superuser"]

    def create(self, validated_data):
        groups_data = validated_data.pop("groups", [])
        password = validated_data.pop("password", None)
        user = User(**validated_data)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save()
        user.groups.set(groups_data)
        return user

    def update(self, instance, validated_data):
        groups_data = validated_data.pop("groups", None)
        password = validated_data.pop("password", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if password:
            instance.set_password(password)
        instance.save()
        if groups_data is not None:
            instance.groups.set(groups_data)
        return instance


class AdminUserCreateSerializer(AdminUserSerializer):
    password = serializers.CharField(write_only=True, required=False, allow_blank=True)

    class Meta(AdminUserSerializer.Meta):
        fields = AdminUserSerializer.Meta.fields + ["password"]


class GroupSerializer(serializers.ModelSerializer):
    class Meta:
        model = Group
        fields = ["id", "name"]
