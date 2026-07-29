from django.contrib.auth.models import Group
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.accounts.models import User
from apps.audit.models import AuditLog
from apps.audit.services import AuditService
from apps.core.exceptions import ConflictError, NotFoundError
from apps.core.permissions import IsPropertyManager
from apps.properties.models import Property
from apps.sections.models import Section
from apps.units.models import PricingRule, Unit

from .serializers import (
    AdminPropertySerializer,
    AdminSectionReorderSerializer,
    AdminSectionSerializer,
    AdminUnitSerializer,
    AdminUserCreateSerializer,
    AdminUserSerializer,
    GroupSerializer,
    PricingRuleSerializer,
)
from .services import AdminService


def _handle_exceptions(fn):
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except NotFoundError as e:
            from rest_framework.exceptions import NotFound
            raise NotFound(detail=e.detail)
        except ConflictError as e:
            return Response({"detail": e.detail}, status=status.HTTP_409_CONFLICT)
    return wrapper


class AdminPropertyViewSet(viewsets.ViewSet):
    permission_classes = [IsPropertyManager]

    def list(self, request):
        properties = AdminService.list_properties()
        serializer = AdminPropertySerializer(properties, many=True)
        return Response(serializer.data)

    @_handle_exceptions
    def retrieve(self, request, pk=None):
        prop = AdminService.get_property(pk)
        serializer = AdminPropertySerializer(prop)
        return Response(serializer.data)

    def create(self, request):
        serializer = AdminPropertySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        prop = AdminService.create_property(serializer.validated_data)
        AuditService.log(
            actor=request.user,
            entity_type=AuditLog.EntityType.PROPERTY,
            entity_id=prop.id,
            action=AuditLog.Action.CREATE,
            description=f"Property '{prop.name}' created.",
            ip_address=request.META.get("REMOTE_ADDR"),
        )
        return Response(AdminPropertySerializer(prop).data, status=status.HTTP_201_CREATED)

    def update(self, request, pk=None):
        prop = AdminService.get_property(pk)
        serializer = AdminPropertySerializer(prop, data=request.data, partial=False)
        serializer.is_valid(raise_exception=True)
        prop = AdminService.update_property(prop, serializer.validated_data)
        AuditService.log(
            actor=request.user,
            entity_type=AuditLog.EntityType.PROPERTY,
            entity_id=prop.id,
            action=AuditLog.Action.UPDATE,
            description=f"Property '{prop.name}' updated.",
            ip_address=request.META.get("REMOTE_ADDR"),
        )
        return Response(AdminPropertySerializer(prop).data)

    @_handle_exceptions
    def partial_update(self, request, pk=None):
        prop = AdminService.get_property(pk)
        serializer = AdminPropertySerializer(prop, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        prop = AdminService.update_property(prop, serializer.validated_data)
        AuditService.log(
            actor=request.user,
            entity_type=AuditLog.EntityType.PROPERTY,
            entity_id=prop.id,
            action=AuditLog.Action.UPDATE,
            description=f"Property '{prop.name}' partially updated.",
            ip_address=request.META.get("REMOTE_ADDR"),
        )
        return Response(AdminPropertySerializer(prop).data)

    @_handle_exceptions
    @action(detail=True, methods=["post"])
    def archive(self, request, pk=None):
        prop = AdminService.archive_property(pk)
        AuditService.log(
            actor=request.user,
            entity_type=AuditLog.EntityType.PROPERTY,
            entity_id=prop.id,
            action=AuditLog.Action.ARCHIVE,
            description=f"Property '{prop.name}' archived.",
            ip_address=request.META.get("REMOTE_ADDR"),
        )
        return Response(AdminPropertySerializer(prop).data)


class AdminSectionViewSet(viewsets.ViewSet):
    permission_classes = [IsPropertyManager]

    def list(self, request):
        property_id = request.query_params.get("property_id")
        sections = AdminService.list_sections(property_id=property_id)
        serializer = AdminSectionSerializer(sections, many=True)
        return Response(serializer.data)

    @_handle_exceptions
    def retrieve(self, request, pk=None):
        section = AdminService.get_section(pk)
        serializer = AdminSectionSerializer(section)
        return Response(serializer.data)

    @_handle_exceptions
    def create(self, request):
        serializer = AdminSectionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        section = AdminService.create_section(serializer.validated_data)
        AuditService.log(
            actor=request.user,
            entity_type=AuditLog.EntityType.SECTION,
            entity_id=section.id,
            action=AuditLog.Action.CREATE,
            description=f"Section '{section.name}' created (property: {section.property.name}).",
            ip_address=request.META.get("REMOTE_ADDR"),
        )
        return Response(AdminSectionSerializer(section).data, status=status.HTTP_201_CREATED)

    @_handle_exceptions
    def update(self, request, pk=None):
        section = AdminService.get_section(pk)
        serializer = AdminSectionSerializer(section, data=request.data, partial=False)
        serializer.is_valid(raise_exception=True)
        section = AdminService.update_section(section, serializer.validated_data)
        AuditService.log(
            actor=request.user,
            entity_type=AuditLog.EntityType.SECTION,
            entity_id=section.id,
            action=AuditLog.Action.UPDATE,
            description=f"Section '{section.name}' updated.",
            ip_address=request.META.get("REMOTE_ADDR"),
        )
        return Response(AdminSectionSerializer(section).data)

    @_handle_exceptions
    def partial_update(self, request, pk=None):
        section = AdminService.get_section(pk)
        serializer = AdminSectionSerializer(section, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        section = AdminService.update_section(section, serializer.validated_data)
        AuditService.log(
            actor=request.user,
            entity_type=AuditLog.EntityType.SECTION,
            entity_id=section.id,
            action=AuditLog.Action.UPDATE,
            description=f"Section '{section.name}' partially updated.",
            ip_address=request.META.get("REMOTE_ADDR"),
        )
        return Response(AdminSectionSerializer(section).data)

    @_handle_exceptions
    @action(detail=True, methods=["post"])
    def archive(self, request, pk=None):
        section = AdminService.archive_section(pk)
        AuditService.log(
            actor=request.user,
            entity_type=AuditLog.EntityType.SECTION,
            entity_id=section.id,
            action=AuditLog.Action.ARCHIVE,
            description=f"Section '{section.name}' archived.",
            ip_address=request.META.get("REMOTE_ADDR"),
        )
        return Response(AdminSectionSerializer(section).data)

    @action(detail=False, methods=["post"])
    def reorder(self, request):
        serializer = AdminSectionReorderSerializer(data=request.data, many=True)
        serializer.is_valid(raise_exception=True)
        AdminService.reorder_sections(serializer.validated_data)
        AuditService.log(
            actor=request.user,
            entity_type=AuditLog.EntityType.SECTION,
            action=AuditLog.Action.UPDATE,
            description="Sections reordered.",
            ip_address=request.META.get("REMOTE_ADDR"),
        )
        return Response({"detail": "Sections reordered."})


class AdminUnitViewSet(viewsets.ViewSet):
    permission_classes = [IsPropertyManager]

    def list(self, request):
        section_id = request.query_params.get("section_id")
        status_filter = request.query_params.get("status")
        units = AdminService.list_units(section_id=section_id, status=status_filter)
        serializer = AdminUnitSerializer(units, many=True)
        return Response(serializer.data)

    @_handle_exceptions
    def retrieve(self, request, pk=None):
        unit = AdminService.get_unit(pk)
        serializer = AdminUnitSerializer(unit)
        return Response(serializer.data)

    @_handle_exceptions
    def create(self, request):
        serializer = AdminUnitSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        unit = AdminService.create_unit(serializer.validated_data)
        AuditService.log(
            actor=request.user,
            entity_type=AuditLog.EntityType.UNIT,
            entity_id=unit.id,
            action=AuditLog.Action.CREATE,
            description=f"Unit '{unit.name}' created in section '{unit.section.name}'.",
            ip_address=request.META.get("REMOTE_ADDR"),
        )
        return Response(AdminUnitSerializer(unit).data, status=status.HTTP_201_CREATED)

    @_handle_exceptions
    def update(self, request, pk=None):
        unit = AdminService.get_unit(pk)
        serializer = AdminUnitSerializer(unit, data=request.data, partial=False)
        serializer.is_valid(raise_exception=True)
        unit = AdminService.update_unit(unit, serializer.validated_data)
        AuditService.log(
            actor=request.user,
            entity_type=AuditLog.EntityType.UNIT,
            entity_id=unit.id,
            action=AuditLog.Action.UPDATE,
            description=f"Unit '{unit.name}' updated.",
            ip_address=request.META.get("REMOTE_ADDR"),
        )
        return Response(AdminUnitSerializer(unit).data)

    @_handle_exceptions
    def partial_update(self, request, pk=None):
        unit = AdminService.get_unit(pk)
        serializer = AdminUnitSerializer(unit, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        unit = AdminService.update_unit(unit, serializer.validated_data)
        AuditService.log(
            actor=request.user,
            entity_type=AuditLog.EntityType.UNIT,
            entity_id=unit.id,
            action=AuditLog.Action.UPDATE,
            description=f"Unit '{unit.name}' partially updated.",
            ip_address=request.META.get("REMOTE_ADDR"),
        )
        return Response(AdminUnitSerializer(unit).data)

    @_handle_exceptions
    @action(detail=True, methods=["post"])
    def archive(self, request, pk=None):
        unit = AdminService.archive_unit(pk)
        AuditService.log(
            actor=request.user,
            entity_type=AuditLog.EntityType.UNIT,
            entity_id=unit.id,
            action=AuditLog.Action.ARCHIVE,
            description=f"Unit '{unit.name}' archived.",
            ip_address=request.META.get("REMOTE_ADDR"),
        )
        return Response(AdminUnitSerializer(unit).data)


class PricingRuleViewSet(viewsets.ViewSet):
    permission_classes = [IsPropertyManager]

    def list(self, request):
        unit_id = request.query_params.get("unit_id")
        billing_mode = request.query_params.get("billing_mode")
        rules = AdminService.list_pricing_rules(unit_id=unit_id, billing_mode=billing_mode)
        serializer = PricingRuleSerializer(rules, many=True)
        return Response(serializer.data)

    @_handle_exceptions
    def retrieve(self, request, pk=None):
        rule = AdminService.get_pricing_rule(pk)
        serializer = PricingRuleSerializer(rule)
        return Response(serializer.data)

    def create(self, request):
        serializer = PricingRuleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        rule = AdminService.create_pricing_rule(serializer.validated_data)
        AuditService.log(
            actor=request.user,
            entity_type=AuditLog.EntityType.PRICING_RULE,
            entity_id=rule.id,
            action=AuditLog.Action.CREATE,
            description=f"Pricing rule for unit '{rule.unit.name}' ({rule.billing_mode}, {rule.price}).",
            ip_address=request.META.get("REMOTE_ADDR"),
        )
        return Response(PricingRuleSerializer(rule).data, status=status.HTTP_201_CREATED)

    @_handle_exceptions
    def update(self, request, pk=None):
        rule = AdminService.get_pricing_rule(pk)
        serializer = PricingRuleSerializer(rule, data=request.data, partial=False)
        serializer.is_valid(raise_exception=True)
        rule = AdminService.update_pricing_rule(rule, serializer.validated_data)
        AuditService.log(
            actor=request.user,
            entity_type=AuditLog.EntityType.PRICING_RULE,
            entity_id=rule.id,
            action=AuditLog.Action.UPDATE,
            description=f"Pricing rule #{rule.id} updated.",
            ip_address=request.META.get("REMOTE_ADDR"),
        )
        return Response(PricingRuleSerializer(rule).data)

    @_handle_exceptions
    def partial_update(self, request, pk=None):
        rule = AdminService.get_pricing_rule(pk)
        serializer = PricingRuleSerializer(rule, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        rule = AdminService.update_pricing_rule(rule, serializer.validated_data)
        AuditService.log(
            actor=request.user,
            entity_type=AuditLog.EntityType.PRICING_RULE,
            entity_id=rule.id,
            action=AuditLog.Action.UPDATE,
            description=f"Pricing rule #{rule.id} partially updated.",
            ip_address=request.META.get("REMOTE_ADDR"),
        )
        return Response(PricingRuleSerializer(rule).data)

    @_handle_exceptions
    def destroy(self, request, pk=None):
        rule = AdminService.get_pricing_rule(pk)
        unit_name = rule.unit.name
        rule.delete()
        AuditService.log(
            actor=request.user,
            entity_type=AuditLog.EntityType.PRICING_RULE,
            entity_id=pk,
            action=AuditLog.Action.DELETE,
            description=f"Pricing rule for unit '{unit_name}' deleted.",
            ip_address=request.META.get("REMOTE_ADDR"),
        )
        return Response(status=status.HTTP_204_NO_CONTENT)


class AdminUserViewSet(viewsets.ViewSet):
    permission_classes = [IsPropertyManager]

    def list(self, request):
        users = AdminService.list_users()
        serializer = AdminUserSerializer(users, many=True)
        return Response(serializer.data)

    @_handle_exceptions
    def retrieve(self, request, pk=None):
        user = AdminService.get_user(pk)
        serializer = AdminUserSerializer(user)
        return Response(serializer.data)

    def create(self, request):
        serializer = AdminUserCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = AdminService.create_user(serializer.validated_data)
        AuditService.log(
            actor=request.user,
            entity_type=AuditLog.EntityType.USER,
            entity_id=user.id,
            action=AuditLog.Action.CREATE,
            description=f"User '{user.username}' created.",
            ip_address=request.META.get("REMOTE_ADDR"),
        )
        return Response(AdminUserSerializer(user).data, status=status.HTTP_201_CREATED)

    @_handle_exceptions
    def update(self, request, pk=None):
        user = AdminService.get_user(pk)
        serializer = AdminUserCreateSerializer(user, data=request.data, partial=False)
        serializer.is_valid(raise_exception=True)
        user = AdminService.update_user(user, serializer.validated_data)
        AuditService.log(
            actor=request.user,
            entity_type=AuditLog.EntityType.USER,
            entity_id=user.id,
            action=AuditLog.Action.UPDATE,
            description=f"User '{user.username}' updated.",
            ip_address=request.META.get("REMOTE_ADDR"),
        )
        return Response(AdminUserSerializer(user).data)

    @_handle_exceptions
    def partial_update(self, request, pk=None):
        user = AdminService.get_user(pk)
        serializer = AdminUserCreateSerializer(user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        user = AdminService.update_user(user, serializer.validated_data)
        AuditService.log(
            actor=request.user,
            entity_type=AuditLog.EntityType.USER,
            entity_id=user.id,
            action=AuditLog.Action.UPDATE,
            description=f"User '{user.username}' partially updated.",
            ip_address=request.META.get("REMOTE_ADDR"),
        )
        return Response(AdminUserSerializer(user).data)

    @action(detail=False, methods=["get"])
    def groups(self, request):
        groups = AdminService.list_groups()
        serializer = GroupSerializer(groups, many=True)
        return Response(serializer.data)

    @_handle_exceptions
    @action(detail=True, methods=["post"])
    def toggle_active(self, request, pk=None):
        user = AdminService.get_user(pk)
        new_status = not user.is_active
        user.is_active = new_status
        user.save()
        AuditService.log(
            actor=request.user,
            entity_type=AuditLog.EntityType.USER,
            entity_id=user.id,
            action=AuditLog.Action.UPDATE,
            description=f"User '{user.username}' {'activated' if new_status else 'deactivated'}.",
            ip_address=request.META.get("REMOTE_ADDR"),
        )
        return Response(AdminUserSerializer(user).data)
