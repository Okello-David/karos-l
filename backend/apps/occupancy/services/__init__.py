from datetime import date

from apps.core.exceptions import ConflictError, NotFoundError
from apps.occupants.models import Student
from apps.units.models import Unit

from ..models import Occupancy


class OccupancyService:

    @staticmethod
    def get_occupancy(occupancy_id):
        try:
            return Occupancy.objects.select_related(
                "student", "unit__section__property"
            ).get(id=occupancy_id)
        except Occupancy.DoesNotExist:
            raise NotFoundError("Occupancy not found.")

    @staticmethod
    def list_occupancies(*, student_id=None, unit_id=None, active_only=None, page=1, page_size=20):
        queryset = Occupancy.objects.select_related("student", "unit__section__property")

        if student_id:
            queryset = queryset.filter(student_id=student_id)
        if unit_id:
            queryset = queryset.filter(unit_id=unit_id)
        if active_only:
            queryset = queryset.filter(end_date__isnull=True)

        queryset = queryset.order_by("-start_date")

        total = queryset.count()
        start = (page - 1) * page_size
        end = start + page_size
        results = queryset[start:end]

        return {
            "count": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size,
            "results": list(results),
        }

    @staticmethod
    def assign_student(*, student_id, unit_id, start_date, billing_mode):
        try:
            student = Student.objects.get(id=student_id)
        except Student.DoesNotExist:
            raise NotFoundError("Occupant not found.")

        try:
            unit = Unit.objects.get(id=unit_id)
        except Unit.DoesNotExist:
            raise NotFoundError("Unit not found.")

        if not student.is_active:
            raise ConflictError("Cannot assign an archived occupant to a unit.")

        if Occupancy.objects.filter(student=student, end_date__isnull=True).exists():
            raise ConflictError("This occupant already has an active occupancy.")

        if unit.status != "active":
            raise ConflictError(f"Unit '{unit.name}' is not available.")

        if unit.is_full():
            raise ConflictError(
                f"Unit '{unit.name}' is at full capacity ({unit.capacity})."
            )

        agreed_price = (
            unit.semester_price if billing_mode == "semester" else unit.monthly_price
        )

        occupancy = Occupancy(
            student=student,
            unit=unit,
            start_date=start_date,
            billing_mode=billing_mode,
            agreed_price=agreed_price,
        )
        occupancy.save()
        return occupancy

    @staticmethod
    def checkout_occupancy(occupancy_id):
        occupancy = OccupancyService.get_occupancy(occupancy_id)

        if not occupancy.is_active:
            raise ConflictError("This occupancy is already closed.")

        occupancy.end_date = date.today()
        occupancy.is_active = False
        occupancy.save()
        return occupancy

    @staticmethod
    def update_occupancy(occupancy_id, data):
        occupancy = OccupancyService.get_occupancy(occupancy_id)

        allowed_fields = {"start_date", "end_date", "billing_mode"}
        for field in allowed_fields:
            if field in data:
                setattr(occupancy, field, data[field])

        occupancy.save()
        return occupancy
