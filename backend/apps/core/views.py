from django.db import connection
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response


@api_view(["GET"])
@permission_classes([AllowAny])
def health_check(request):
    """Liveness/readiness probe for container orchestration. No auth required."""
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        db_ok = True
    except Exception:
        db_ok = False

    body = {"status": "ok" if db_ok else "degraded", "database": "ok" if db_ok else "unavailable"}
    return Response(body, status=200 if db_ok else 503)
