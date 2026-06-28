from django.db.models import Q

from apps.core.exceptions import NotFoundError

from ..models import Student


class StudentService:

    @staticmethod
    def list_students(*, search=None, status=None, page=1, page_size=20):
        queryset = Student.objects.all()

        if status == "active":
            queryset = queryset.filter(is_active=True)
        elif status == "archived":
            queryset = queryset.filter(is_active=False)

        if search:
            queryset = queryset.filter(
                Q(first_name__icontains=search)
                | Q(last_name__icontains=search)
                | Q(phone__icontains=search)
                | Q(student_id_number__icontains=search)
                | Q(national_id__icontains=search)
            )

        queryset = queryset.order_by("last_name", "first_name")

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
    def get_student(student_id):
        try:
            return Student.objects.get(id=student_id)
        except Student.DoesNotExist:
            raise NotFoundError("Occupant not found.")

    @staticmethod
    def create_student(data):
        return Student.objects.create(**data)

    @staticmethod
    def update_student(student, data):
        for field, value in data.items():
            setattr(student, field, value)
        student.save()
        return student

    @staticmethod
    def archive_student(student):
        student.is_active = False
        student.save()
        return student
