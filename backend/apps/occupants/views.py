from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.audit.models import AuditLog
from apps.audit.services import AuditService
from apps.core.exceptions import NotFoundError
from apps.core.permissions import CanManageOccupants

from .serializers import StudentSerializer
from .services import StudentService


def _get_student_or_error(pk):
    try:
        return StudentService.get_student(pk)
    except NotFoundError as e:
        from rest_framework.exceptions import NotFound
        raise NotFound(detail=e.detail)


class StudentViewSet(viewsets.ViewSet):
    permission_classes = [CanManageOccupants]

    def list(self, request):
        page = int(request.query_params.get("page", 1))
        page_size = int(request.query_params.get("page_size", 20))
        result = StudentService.list_students(
            search=request.query_params.get("search"),
            status=request.query_params.get("status"),
            page=page,
            page_size=page_size,
        )
        serializer = StudentSerializer(result["results"], many=True)
        result["results"] = serializer.data
        return Response(result)

    def create(self, request):
        serializer = StudentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        student = StudentService.create_student(serializer.validated_data)
        AuditService.log(
            actor=request.user,
            entity_type=AuditLog.EntityType.OCCUPANT,
            entity_id=student.id,
            action=AuditLog.Action.CREATE,
            description=f"Occupant {student.first_name} {student.last_name} created.",
            ip_address=request.META.get("REMOTE_ADDR"),
        )
        output = StudentSerializer(student)
        return Response(output.data, status=status.HTTP_201_CREATED)

    def retrieve(self, request, pk=None):
        student = _get_student_or_error(pk)
        serializer = StudentSerializer(student)
        return Response(serializer.data)

    def update(self, request, pk=None):
        student = _get_student_or_error(pk)
        serializer = StudentSerializer(student, data=request.data, partial=False)
        serializer.is_valid(raise_exception=True)
        student = StudentService.update_student(student, serializer.validated_data)
        AuditService.log(
            actor=request.user,
            entity_type=AuditLog.EntityType.OCCUPANT,
            entity_id=student.id,
            action=AuditLog.Action.UPDATE,
            description=f"Occupant {student.first_name} {student.last_name} updated.",
            ip_address=request.META.get("REMOTE_ADDR"),
        )
        output = StudentSerializer(student)
        return Response(output.data)

    def partial_update(self, request, pk=None):
        student = _get_student_or_error(pk)
        serializer = StudentSerializer(student, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        student = StudentService.update_student(student, serializer.validated_data)
        AuditService.log(
            actor=request.user,
            entity_type=AuditLog.EntityType.OCCUPANT,
            entity_id=student.id,
            action=AuditLog.Action.UPDATE,
            description=f"Occupant {student.first_name} {student.last_name} partially updated.",
            ip_address=request.META.get("REMOTE_ADDR"),
        )
        output = StudentSerializer(student)
        return Response(output.data)

    @action(detail=True, methods=["post"])
    def archive(self, request, pk=None):
        student = _get_student_or_error(pk)
        if not student.is_active:
            return Response(
                {"detail": "This occupant is already archived."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        StudentService.archive_student(student)
        AuditService.log(
            actor=request.user,
            entity_type=AuditLog.EntityType.OCCUPANT,
            entity_id=student.id,
            action=AuditLog.Action.ARCHIVE,
            description=f"Occupant {student.first_name} {student.last_name} archived.",
            ip_address=request.META.get("REMOTE_ADDR"),
        )
        return Response({"detail": "Occupant archived successfully."})
