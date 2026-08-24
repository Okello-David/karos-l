from django.db import models
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.audit.models import AuditLog
from apps.audit.services import AuditService
from apps.core.exceptions import ConflictError, NotFoundError
from apps.core.permissions import CanManageOccupancy
from apps.properties.models import Property
from apps.occupants.models import Student
from apps.units.models import Unit

from .models import Occupancy
from .serializers import OccupancySerializer
from .services import OccupancyService


def _get_occupancy_or_error(pk):
    try:
        return OccupancyService.get_occupancy(pk)
    except NotFoundError as e:
        from rest_framework.exceptions import NotFound
        raise NotFound(detail=e.detail)


class OccupancyViewSet(viewsets.ViewSet):
    permission_classes = [CanManageOccupancy]

    def get_permissions(self):
        # `summary` is read-only aggregate data (counts, occupancy rate, property
        # breakdown) that the Dashboard/Overview page depends on for every
        # authenticated user, not just Property Managers — it carries no
        # per-occupant detail. Every other action here creates/modifies
        # occupancy records and stays Property-Manager-and-above only.
        if self.action == "summary":
            return [IsAuthenticated()]
        return super().get_permissions()

    def list(self, request):
        page = int(request.query_params.get("page", 1))
        page_size = int(request.query_params.get("page_size", 20))
        result = OccupancyService.list_occupancies(
            student_id=request.query_params.get("student_id"),
            unit_id=request.query_params.get("unit_id"),
            active_only=request.query_params.get("active_only"),
            page=page,
            page_size=page_size,
        )
        serializer = OccupancySerializer(result["results"], many=True)
        result["results"] = serializer.data
        return Response(result)

    def create(self, request):
        serializer = OccupancySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            occupancy = OccupancyService.assign_student(
                student_id=serializer.validated_data["student"].id,
                unit_id=serializer.validated_data["unit"].id,
                start_date=serializer.validated_data["start_date"],
                billing_mode=serializer.validated_data["billing_mode"],
            )
        except ConflictError as e:
            return Response({"detail": e.detail}, status=status.HTTP_409_CONFLICT)
        AuditService.log(
            actor=request.user,
            entity_type=AuditLog.EntityType.OCCUPANCY,
            entity_id=occupancy.id,
            action=AuditLog.Action.ASSIGN,
            description=f"Occupant {occupancy.student} assigned to {occupancy.unit.name} (billing: {occupancy.billing_mode}).",
            ip_address=request.META.get("REMOTE_ADDR"),
        )
        output = OccupancySerializer(occupancy)
        return Response(output.data, status=status.HTTP_201_CREATED)

    def retrieve(self, request, pk=None):
        occupancy = _get_occupancy_or_error(pk)
        serializer = OccupancySerializer(occupancy)
        return Response(serializer.data)

    def partial_update(self, request, pk=None):
        occupancy = _get_occupancy_or_error(pk)
        serializer = OccupancySerializer(occupancy, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        try:
            occupancy = OccupancyService.update_occupancy(
                occupancy.id,
                serializer.validated_data,
            )
        except ConflictError as e:
            return Response({"detail": e.detail}, status=status.HTTP_409_CONFLICT)
        AuditService.log(
            actor=request.user,
            entity_type=AuditLog.EntityType.OCCUPANCY,
            entity_id=occupancy.id,
            action=AuditLog.Action.UPDATE,
            description=f"Occupancy #{occupancy.id} updated (student: {occupancy.student}, unit: {occupancy.unit.name}).",
            ip_address=request.META.get("REMOTE_ADDR"),
        )
        output = OccupancySerializer(occupancy)
        return Response(output.data)

    @action(detail=True, methods=["post"])
    def checkout(self, request, pk=None):
        occupancy = _get_occupancy_or_error(pk)
        try:
            occupancy = OccupancyService.checkout_occupancy(occupancy.id)
        except ConflictError as e:
            return Response({"detail": e.detail}, status=status.HTTP_409_CONFLICT)
        AuditService.log(
            actor=request.user,
            entity_type=AuditLog.EntityType.OCCUPANCY,
            entity_id=occupancy.id,
            action=AuditLog.Action.CHECKOUT,
            description=f"Occupant {occupancy.student} checked out from {occupancy.unit.name}.",
            ip_address=request.META.get("REMOTE_ADDR"),
        )
        serializer = OccupancySerializer(occupancy)
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def summary(self, request):
        total_capacity = (
            Unit.objects.filter(is_active=True)
            .aggregate(total=models.Sum("capacity"))["total"]
            or 0
        )
        total_occupied = Occupancy.objects.filter(end_date__isnull=True).count()
        total_available = total_capacity - total_occupied
        total_students = Student.objects.count()
        active_students = Student.objects.filter(is_active=True).count()

        properties_data = []
        for prop in Property.objects.filter(is_active=True):
            prop_unit_ids = Unit.objects.filter(
                section__property=prop, is_active=True
            ).values("id")
            prop_capacity = (
                Unit.objects.filter(id__in=prop_unit_ids)
                .aggregate(total=models.Sum("capacity"))["total"]
                or 0
            )
            prop_occupied = Occupancy.objects.filter(
                unit_id__in=prop_unit_ids, end_date__isnull=True
            ).count()
            prop_available = prop_capacity - prop_occupied
            rate = round((prop_occupied / prop_capacity) * 100) if prop_capacity > 0 else 0
            properties_data.append({
                "id": prop.id,
                "name": prop.name,
                "total_capacity": prop_capacity,
                "occupied": prop_occupied,
                "available": prop_available,
                "occupancy_rate": rate,
            })

        return Response({
            "total_capacity": total_capacity,
            "total_occupied": total_occupied,
            "total_available": total_available,
            "total_students": total_students,
            "active_students": active_students,
            "properties": properties_data,
        })
