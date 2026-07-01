import datetime
from datetime import date
from decimal import Decimal

from django.db import transaction
from django.db.models import Q, Sum

from apps.core.exceptions import ConflictError, NotFoundError
from apps.occupancy.models import Occupancy
from apps.occupants.models import Student
from apps.units.models import Unit

from ..models import Payment, Receipt


class PaymentService:

    @staticmethod
    def get_payment(payment_id):
        try:
            return Payment.objects.select_related(
                "student"
            ).get(id=payment_id)
        except Payment.DoesNotExist:
            raise NotFoundError("Payment not found.")

    @staticmethod
    def list_payments(
        *,
        search=None,
        property_id=None,
        student_id=None,
        payment_method=None,
        date_from=None,
        date_to=None,
        page=1,
        page_size=20,
    ):
        queryset = Payment.objects.select_related("student")

        if search:
            queryset = queryset.filter(
                Q(student__first_name__icontains=search)
                | Q(student__last_name__icontains=search)
                | Q(student__student_id_number__icontains=search)
                | Q(reference__icontains=search)
            )

        if property_id:
            student_ids = (
                Occupancy.objects
                .filter(unit__section__property_id=property_id)
                .values_list("student_id", flat=True)
                .distinct()
            )
            queryset = queryset.filter(student_id__in=list(student_ids))

        if student_id:
            queryset = queryset.filter(student_id=student_id)

        if payment_method:
            queryset = queryset.filter(payment_method=payment_method)

        if date_from:
            queryset = queryset.filter(payment_date__gte=date_from)

        if date_to:
            queryset = queryset.filter(payment_date__lte=date_to)

        queryset = queryset.order_by("-payment_date", "-created_at")

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
    def record_payment(*, student_id, amount, payment_date, payment_method, reference="", notes=""):
        try:
            student = Student.objects.get(id=student_id)
        except Student.DoesNotExist:
            raise NotFoundError("Occupant not found.")

        if not student.is_active:
            raise ConflictError("Cannot record a payment for an archived occupant.")

        if reference:
            existing = Payment.objects.filter(reference=reference).first()
            if existing:
                raise ConflictError(
                    f"A payment with reference '{reference}' was already recorded "
                    f"on {existing.payment_date} ({existing.amount})."
                )

        payment = Payment(
            student=student,
            amount=amount,
            payment_date=payment_date,
            payment_method=payment_method,
            reference=reference,
            notes=notes,
        )
        with transaction.atomic():
            payment.full_clean()
            payment.save()
            PaymentService._generate_receipt(payment)

        return payment

    @staticmethod
    def _generate_receipt_number():
        year = datetime.date.today().year
        prefix = f"RCP-{year}-"
        last = Receipt.objects.filter(
            receipt_number__startswith=prefix
        ).order_by("receipt_number").last()
        if last:
            last_num = int(last.receipt_number.split("-")[-1])
            new_num = last_num + 1
        else:
            new_num = 1
        return f"{prefix}{new_num:05d}"

    @staticmethod
    def _generate_receipt(payment):
        balance_info = PaymentService.calculate_student_balance(payment.student_id)
        active_occ = Occupancy.objects.filter(
            student=payment.student, end_date__isnull=True
        ).select_related("unit__section__property").first()

        unit_name = ""
        property_name = ""
        if active_occ:
            unit_name = active_occ.unit.name
            property_name = active_occ.unit.section.property.name

        receipt = Receipt(
            payment=payment,
            receipt_number=PaymentService._generate_receipt_number(),
            outstanding_balance_after=Decimal(balance_info["balance"]),
            student_name=payment.student.full_name(),
            student_id_number=payment.student.student_id_number or "",
            unit_name=unit_name,
            property_name=property_name,
            amount=payment.amount,
            payment_date=payment.payment_date,
            payment_method=payment.payment_method,
            reference=payment.reference,
        )
        receipt.save()
        return receipt

    @staticmethod
    def get_receipt(receipt_id):
        try:
            return Receipt.objects.get(id=receipt_id)
        except Receipt.DoesNotExist:
            raise NotFoundError("Receipt not found.")

    @staticmethod
    def list_receipts(
        *,
        search=None,
        date_from=None,
        date_to=None,
        page=1,
        page_size=20,
    ):
        queryset = Receipt.objects.all()

        if search:
            queryset = queryset.filter(
                Q(receipt_number__icontains=search)
                | Q(student_name__icontains=search)
                | Q(reference__icontains=search)
            )

        if date_from:
            queryset = queryset.filter(payment_date__gte=date_from)

        if date_to:
            queryset = queryset.filter(payment_date__lte=date_to)

        queryset = queryset.order_by("-issued_at")

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
    def _calculate_occupancy_charge(occupancy):
        unit = occupancy.unit
        if occupancy.billing_mode == "semester":
            return occupancy.agreed_price if occupancy.agreed_price is not None else unit.semester_price

        monthly_rate = occupancy.agreed_price if occupancy.agreed_price is not None else unit.monthly_price
        end = occupancy.end_date or date.today()
        days = (end - occupancy.start_date).days
        months = (days + 29) // 30
        if months < 1:
            months = 1
        return monthly_rate * Decimal(months)

    @staticmethod
    def calculate_student_balance(student_id):
        try:
            student = Student.objects.get(id=student_id)
        except Student.DoesNotExist:
            raise NotFoundError("Occupant not found.")

        occupancies = Occupancy.objects.filter(student=student).select_related("unit")

        total_charges = Decimal("0.00")
        occupancy_details = []

        for occ in occupancies:
            charge = PaymentService._calculate_occupancy_charge(occ)
            total_charges += charge
            occupancy_details.append({
                "occupancy_id": occ.id,
                "unit_name": occ.unit.name,
                "start_date": occ.start_date.isoformat(),
                "end_date": occ.end_date.isoformat() if occ.end_date else None,
                "billing_mode": occ.billing_mode,
                "charge": str(charge),
            })

        total_paid = (
            Payment.objects.filter(student=student)
            .aggregate(total=Sum("amount"))["total"]
            or Decimal("0.00")
        )

        balance = total_charges - total_paid

        return {
            "student_id": student.id,
            "student_name": student.full_name(),
            "total_charges": str(total_charges),
            "total_paid": str(total_paid),
            "balance": str(balance),
            "occupancies": occupancy_details,
        }

    @staticmethod
    def list_overdue_students():
        students = Student.objects.filter(is_active=True).prefetch_related(
            "occupancies__unit__section__property",
        )
        overdue_list = []

        for student in students:
            occupancies = [occ for occ in student.occupancies.all()]

            total_charges = Decimal("0.00")
            active_occ = None
            for occ in occupancies:
                charge = PaymentService._calculate_occupancy_charge(occ)
                total_charges += charge
                if occ.end_date is None:
                    active_occ = occ

            total_paid = (
                Payment.objects.filter(student=student)
                .aggregate(total=Sum("amount"))["total"]
                or Decimal("0.00")
            )

            balance = total_charges - total_paid
            if balance > 0:
                overdue_list.append({
                    "student_id": student.id,
                    "student_name": student.full_name(),
                    "balance": str(balance),
                    "unit_name": active_occ.unit.name if active_occ else None,
                    "property_name": active_occ.unit.section.property.name if active_occ else None,
                })

        overdue_list.sort(key=lambda x: Decimal(x["balance"]), reverse=True)
        return overdue_list
