from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.exceptions import NotFoundError
from apps.core.permissions import CanViewAuditLog

from .models import AuditLog
from .serializers import AuditLogSerializer
from .services import AuditService


class AuditLogListView(APIView):
    permission_classes = [IsAuthenticated & CanViewAuditLog]

    def get(self, request):
        params = request.query_params
        result = AuditService.list_logs(
            entity_type=params.get("entity_type"),
            entity_id=params.get("entity_id"),
            action=params.get("action"),
            actor_id=params.get("actor_id"),
            date_from=params.get("date_from"),
            date_to=params.get("date_to"),
            page=int(params.get("page", 1)),
            page_size=int(params.get("page_size", 20)),
        )
        serializer = AuditLogSerializer(result.pop("results"), many=True)
        result["results"] = serializer.data
        return Response(result)


class AuditLogDetailView(APIView):
    permission_classes = [IsAuthenticated & CanViewAuditLog]

    def get(self, request, pk):
        try:
            log = AuditService.get_log(pk)
        except NotFoundError as e:
            from rest_framework.exceptions import NotFound
            raise NotFound(detail=e.detail)
        serializer = AuditLogSerializer(log)
        return Response(serializer.data)


class AuditEntityTypesView(APIView):
    permission_classes = [IsAuthenticated & CanViewAuditLog]

    def get(self, request):
        choices = [{"value": v, "label": l} for v, l in AuditLog.EntityType.choices]
        return Response(choices)


class AuditActionsView(APIView):
    permission_classes = [IsAuthenticated & CanViewAuditLog]

    def get(self, request):
        choices = [{"value": v, "label": l} for v, l in AuditLog.Action.choices]
        return Response(choices)
