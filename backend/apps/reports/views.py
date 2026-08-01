from datetime import date

from django.http import HttpResponse
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.audit.models import AuditLog
from apps.audit.services import AuditService
from apps.backup.services import ExportService
from apps.core.permissions import IsPropertyManager

from .services import (
    FINANCIAL_COLUMNS,
    OCCUPANCY_COLUMNS,
    OCCUPANTS_COLUMNS,
    ReportService,
    headers_for,
)


def _parse_date(value, field_name):
    """Return (date, error_response). An absent value is not an error."""
    if not value:
        return None, None
    try:
        return date.fromisoformat(value), None
    except ValueError:
        return None, Response(
            {"detail": f"{field_name} must be an ISO date (YYYY-MM-DD)."},
            status=status.HTTP_400_BAD_REQUEST,
        )


class BaseReportView(APIView):
    """Shared JSON-or-download behaviour for the report endpoints.

    Matches the permission convention used by every other business endpoint.
    """

    permission_classes = [IsAuthenticated | IsPropertyManager]

    # Set by subclasses.
    report_name = None
    columns = None

    def build(self, request):
        raise NotImplementedError

    def get(self, request):
        file_format = request.query_params.get("file_format")

        result = self.build(request)
        if isinstance(result, Response):  # a validation error from build()
            return result

        if file_format is None:
            return Response(result)

        file_format = file_format.lower()
        if file_format not in ("csv", "xlsx"):
            return Response(
                {"detail": "Unsupported format. Use 'csv' or 'xlsx'."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Reuses the same writer as Backup & Export, so a report downloads in
        # exactly the format users already get elsewhere.
        content, filename, content_type = ExportService._write_export(
            result["rows"],
            headers_for(self.columns),
            file_format,
            f"{self.report_name}_report",
        )

        AuditService.log(
            actor=request.user,
            entity_type=AuditLog.EntityType.BACKUP,
            action=AuditLog.Action.OTHER,
            description=f"Exported {self.report_name} report as {file_format.upper()}.",
            ip_address=request.META.get("REMOTE_ADDR"),
        )

        response = HttpResponse(content, content_type=content_type)
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response


class OccupancyReportView(BaseReportView):
    report_name = "occupancy"
    columns = OCCUPANCY_COLUMNS

    def build(self, request):
        return ReportService.occupancy_report()


class FinancialReportView(BaseReportView):
    report_name = "financial"
    columns = FINANCIAL_COLUMNS

    def build(self, request):
        start_date, error = _parse_date(request.query_params.get("start_date"), "start_date")
        if error:
            return error
        end_date, error = _parse_date(request.query_params.get("end_date"), "end_date")
        if error:
            return error

        if start_date and end_date and end_date < start_date:
            return Response(
                {"detail": "end_date must be on or after start_date."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return ReportService.financial_report(start_date=start_date, end_date=end_date)


class OccupantsReportView(BaseReportView):
    report_name = "occupants"
    columns = OCCUPANTS_COLUMNS

    def build(self, request):
        return ReportService.occupants_report()
