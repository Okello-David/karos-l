import json

from django.http import HttpResponse
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.audit.models import AuditLog
from apps.audit.services import AuditService
from apps.core.exceptions import ConflictError, NotFoundError
from apps.core.permissions import CanManageBackups

from .models import Backup
from .serializers import BackupDetailSerializer, BackupListSerializer, RestoreSerializer
from .services import BackupService, ExportService


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


class BackupListCreateView(APIView):
    permission_classes = [IsAuthenticated & CanManageBackups]

    def get(self, request):
        page = int(request.query_params.get("page", 1))
        page_size = int(request.query_params.get("page_size", 20))
        result = BackupService.list_backups(page=page, page_size=page_size)
        serializer = BackupListSerializer(result.pop("results"), many=True)
        result["results"] = serializer.data
        return Response(result)

    @_handle_exceptions
    def post(self, request):
        notes = request.data.get("notes", "")
        backup = BackupService.create_backup(user=request.user, notes=notes)
        AuditService.log(
            actor=request.user,
            entity_type=AuditLog.EntityType.BACKUP,
            entity_id=backup.id,
            action=AuditLog.Action.CREATE,
            description=f"Backup #{backup.id} created ({backup.metadata.get('total_records', '?')} records).",
            ip_address=request.META.get("REMOTE_ADDR"),
        )
        serializer = BackupDetailSerializer(backup)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class BackupDetailView(APIView):
    permission_classes = [IsAuthenticated & CanManageBackups]

    @_handle_exceptions
    def get(self, request, pk):
        backup = BackupService.get_backup(pk)
        serializer = BackupDetailSerializer(backup)
        return Response(serializer.data)


class BackupRestoreView(APIView):
    permission_classes = [IsAuthenticated & CanManageBackups]

    @_handle_exceptions
    def post(self, request, pk):
        serializer = RestoreSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        backup = BackupService.get_backup(pk)
        restored_counts = BackupService.restore_backup(backup)

        AuditService.log(
            actor=request.user,
            entity_type=AuditLog.EntityType.BACKUP,
            entity_id=backup.id,
            action=AuditLog.Action.OTHER,
            description=f"Restored from backup #{backup.id}: {json.dumps(restored_counts)}",
            ip_address=request.META.get("REMOTE_ADDR"),
        )

        return Response({
            "detail": "Restore completed successfully.",
            "restored_counts": restored_counts,
        })


class BackupValidateView(APIView):
    permission_classes = [IsAuthenticated & CanManageBackups]

    @_handle_exceptions
    def get(self, request, pk):
        backup = BackupService.get_backup(pk)
        BackupService.validate_backup(backup)
        return Response({
            "valid": True,
            "message": "Backup file is valid and ready for restore.",
        })


class ExportView(APIView):
    permission_classes = [IsAuthenticated & CanManageBackups]

    def get(self, request):
        entity = request.query_params.get("entity")
        file_format = request.query_params.get("file_format", "csv").lower()

        if file_format not in ("csv", "xlsx"):
            return Response(
                {"detail": "Unsupported format. Use 'csv' or 'xlsx'."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        export_map = {
            "occupants": ExportService.export_occupants,
            "occupancies": ExportService.export_occupancies,
            "payments": ExportService.export_payments,
            "receipts": ExportService.export_receipts,
        }

        export_fn = export_map.get(entity)
        if not export_fn:
            return Response(
                {"detail": f"Unknown entity '{entity}'. Supported: {', '.join(export_map.keys())}."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        content, filename, content_type = export_fn(file_format=file_format)

        AuditService.log(
            actor=request.user,
            entity_type=AuditLog.EntityType.BACKUP,
            action=AuditLog.Action.OTHER,
            description=f"Exported {entity} as {file_format.upper()}.",
            ip_address=request.META.get("REMOTE_ADDR"),
        )

        response = HttpResponse(content, content_type=content_type)
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response
