from django.db.models import Sum, Count, Q
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.occupancy.models import Occupancy
from apps.units.models import Unit
from apps.occupants.models import Student
from apps.payments.models import Payment


class DashboardSummaryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        total_capacity = (
            Unit.objects.filter(is_active=True)
            .aggregate(total=Sum("capacity"))["total"]
            or 0
        )
        total_occupied = Occupancy.objects.filter(end_date__isnull=True).count()
        total_available = total_capacity - total_occupied

        total_students = Student.objects.filter(is_active=True).count()

        recent_payments = (
            Payment.objects
            .select_related("student")
            .order_by("-payment_date", "-created_at")[:10]
        )
        recent_payments_data = [
            {
                "id": p.id,
                "student_name": p.student.full_name(),
                "amount": str(p.amount),
                "payment_date": p.payment_date.isoformat(),
                "payment_method": p.payment_method,
            }
            for p in recent_payments
        ]

        occupancy_rate = (
            round((total_occupied / total_capacity) * 100)
            if total_capacity > 0 else 0
        )

        return Response({
            "total_capacity": total_capacity,
            "total_occupied": total_occupied,
            "total_available": total_available,
            "occupancy_rate": occupancy_rate,
            "total_students": total_students,
            "recent_payments": recent_payments_data,
        })
