from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.occupancy.models import Occupancy
from apps.occupants.models import Student
from apps.properties.models import Property
from apps.sections.models import Section
from apps.units.models import Unit

from .models import Payment, Receipt
from .services import PaymentService


class PaymentAPITests(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="admin", password="pass123", is_staff=True
        )
        self.token = Token.objects.create(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")

        self.property = Property.objects.create(
            name="Test Property", code="TST01"
        )
        self.section = Section.objects.create(
            property=self.property, name="Section A"
        )
        self.unit = Unit.objects.create(
            section=self.section,
            name="Room 1",
            capacity=2,
            semester_price=Decimal("500000.00"),
            monthly_price=Decimal("200000.00"),
        )
        self.student = Student.objects.create(
            first_name="John",
            last_name="Doe",
            email="john@example.com",
            student_id_number="STU001",
            national_id="NAT001",
        )

        self.list_url = "/api/payments/"
        self.payment_data = {
            "student": self.student.id,
            "amount": "150000.00",
            "payment_date": date.today().isoformat(),
            "payment_method": "cash",
            "reference": "REF001",
            "notes": "First payment",
        }

    def _record(self, **overrides):
        data = {**self.payment_data, **overrides}
        return self.client.post(self.list_url, data, format="json")

    def _create_occupancy(self, student=None, unit=None, start_date=None, billing_mode="semester"):
        s = student or self.student
        u = unit or self.unit
        sd = start_date or (date.today() - timedelta(days=60))
        return Occupancy.objects.create(
            student=s, unit=u, start_date=sd, billing_mode=billing_mode,
        )

    # --- Authentication ---

    def test_unauthenticated(self):
        self.client.credentials()
        response = self._record()
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    # --- Create ---

    def test_record_payment_success(self):
        response = self._record()
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["amount"], "150000.00")
        self.assertEqual(response.data["payment_method"], "cash")
        self.assertEqual(response.data["reference"], "REF001")
        self.assertEqual(response.data["notes"], "First payment")
        self.assertIn("student_name", response.data)
        self.assertEqual(response.data["student_name"], "John Doe")

    def test_record_payment_no_reference(self):
        response = self._record(reference="")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["reference"], "")

    def test_record_payment_no_notes(self):
        response = self._record(notes="")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["notes"], "")

    def test_record_payment_archived_student(self):
        self.student.is_active = False
        self.student.save()
        response = self._record()
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertIn("archived", response.data["detail"].lower())

    def test_record_payment_nonexistent_student(self):
        response = self._record(student=99999)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_record_payment_for_student_without_id_number(self):
        student = Student.objects.create(
            first_name="Jane",
            last_name="NoId",
            email="jane.noid@example.com",
        )
        response = self._record(student=student.id, reference="REF-NOID")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        receipt = Payment.objects.get(id=response.data["id"]).receipt
        self.assertEqual(receipt.student_id_number, "")

    def test_record_payment_rolls_back_if_receipt_generation_fails(self):
        with patch.object(
            PaymentService, "_generate_receipt", side_effect=RuntimeError("boom")
        ):
            with self.assertRaises(RuntimeError):
                PaymentService.record_payment(
                    student_id=self.student.id,
                    amount=Decimal("150000.00"),
                    payment_date=date.today(),
                    payment_method="cash",
                    reference="REF-ROLLBACK",
                )
        self.assertFalse(
            Payment.objects.filter(reference="REF-ROLLBACK").exists()
        )

    def test_record_payment_duplicate_reference(self):
        self._record()
        response = self._record(reference="REF001")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("reference", response.data)

    def test_record_payment_missing_amount(self):
        response = self._record(amount="")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_record_payment_missing_date(self):
        response = self._record(payment_date="")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_record_payment_missing_method(self):
        response = self._record(payment_method="")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_record_payment_negative_amount(self):
        response = self._record(amount="-100.00")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_record_payment_zero_amount(self):
        response = self._record(amount="0.00")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    # --- Retrieve ---

    def test_retrieve_payment(self):
        create_resp = self._record()
        payment_id = create_resp.data["id"]
        response = self.client.get(f"{self.list_url}{payment_id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], payment_id)
        self.assertEqual(response.data["amount"], "150000.00")

    def test_retrieve_nonexistent(self):
        response = self.client.get(f"{self.list_url}99999/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    # --- List ---

    def test_list_empty(self):
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 0)

    def test_list_payments(self):
        self._record()
        self._record(amount="200000.00", reference="REF002")
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 2)

    def test_list_filter_by_student(self):
        self._record()
        student2 = Student.objects.create(
            first_name="Jane", last_name="Smith", email="jane@example.com",
            student_id_number="STU002", national_id="NAT002",
        )
        self._record(student=student2.id, reference="REF002")
        response = self.client.get(self.list_url, {"student_id": self.student.id})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)

    def test_list_filter_by_method(self):
        self._record()
        self._record(payment_method="transfer", reference="REF002")
        response = self.client.get(self.list_url, {"payment_method": "transfer"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)

    def test_list_filter_by_date_range(self):
        self._record(payment_date="2026-01-15", reference="REF002")
        self._record(payment_date="2026-06-15", reference="REF003")
        response = self.client.get(self.list_url, {
            "date_from": "2026-06-01", "date_to": "2026-06-30",
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)

    def test_list_filter_by_search(self):
        self._record()
        response = self.client.get(self.list_url, {"search": "REF001"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)

    def test_list_payment_without_receipt(self):
        Payment.objects.create(
            student=self.student,
            amount=Decimal("150000.00"),
            payment_date=date.today(),
            payment_method="cash",
        )
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["results"][0]["receipt_id"], None)
        self.assertEqual(response.data["results"][0]["receipt_number"], None)

    def test_list_filter_by_property(self):
        self._create_occupancy(student=self.student, unit=self.unit)
        self._record()
        # Create student in a different property
        prop2 = Property.objects.create(name="Other", code="TST02")
        sec2 = Section.objects.create(property=prop2, name="Sec B")
        unit2 = Unit.objects.create(
            section=sec2, name="Room 2", capacity=1,
            semester_price=300000, monthly_price=150000,
        )
        student2 = Student.objects.create(
            first_name="Jane", last_name="Smith", email="jane@example.com",
            student_id_number="STU002", national_id="NAT002",
        )
        self._create_occupancy(student=student2, unit=unit2)
        self._record(student=student2.id, reference="REF002")
        response = self.client.get(self.list_url, {"property_id": self.property.id})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)

    # --- Balance ---

    def test_balance_no_occupancy_no_payment(self):
        response = self.client.get(
            f"{self.list_url}student_balance/",
            {"student_id": self.student.id},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["total_charges"], "0.00")
        self.assertEqual(response.data["total_paid"], "0.00")
        self.assertEqual(response.data["balance"], "0.00")

    def test_balance_semester_occupancy_no_payment(self):
        self._create_occupancy(billing_mode="semester")
        response = self.client.get(
            f"{self.list_url}student_balance/",
            {"student_id": self.student.id},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(Decimal(response.data["total_charges"]), self.unit.semester_price)
        self.assertEqual(response.data["total_paid"], "0.00")
        self.assertEqual(Decimal(response.data["balance"]), self.unit.semester_price)

    def test_balance_monthly_occupancy(self):
        self._create_occupancy(
            billing_mode="monthly",
            start_date=date.today() - timedelta(days=45),
        )
        response = self.client.get(
            f"{self.list_url}student_balance/",
            {"student_id": self.student.id},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # 45 days = 2 months (ceil(45/30) = 2)
        expected = self.unit.monthly_price * 2
        self.assertEqual(Decimal(response.data["total_charges"]), expected)

    def test_balance_monthly_uses_snapshot_as_monthly_rate(self):
        Occupancy.objects.create(
            student=self.student,
            unit=self.unit,
            start_date=date.today() - timedelta(days=45),
            billing_mode="monthly",
            agreed_price=Decimal("180000.00"),
        )
        response = self.client.get(
            f"{self.list_url}student_balance/",
            {"student_id": self.student.id},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(Decimal(response.data["total_charges"]), Decimal("360000.00"))

    def test_balance_with_payment(self):
        self._create_occupancy(billing_mode="semester")
        self._record(amount="50000.00", reference="REF001")
        response = self.client.get(
            f"{self.list_url}student_balance/",
            {"student_id": self.student.id},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        expected_balance = self.unit.semester_price - Decimal("50000.00")
        self.assertEqual(Decimal(response.data["balance"]), expected_balance)

    def test_balance_no_student_id(self):
        response = self.client.get(f"{self.list_url}student_balance/")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_balance_nonexistent_student(self):
        response = self.client.get(
            f"{self.list_url}student_balance/",
            {"student_id": 99999},
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    # --- Overdue ---

    def test_overdue_empty(self):
        response = self.client.get(f"{self.list_url}overdue/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 0)

    def test_overdue_with_balance(self):
        self._create_occupancy(billing_mode="semester")
        response = self.client.get(f"{self.list_url}overdue/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(
            Decimal(response.data["results"][0]["balance"]),
            self.unit.semester_price,
        )

    def test_overdue_excludes_settled(self):
        self._create_occupancy(billing_mode="semester")
        self._record(amount=str(self.unit.semester_price), reference="FULL")
        response = self.client.get(f"{self.list_url}overdue/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 0)

    def test_overdue_unauthenticated(self):
        self.client.credentials()
        response = self.client.get(f"{self.list_url}overdue/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class ReceiptAPITests(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="admin", password="pass123", is_staff=True
        )
        self.token = Token.objects.create(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")

        self.property = Property.objects.create(
            name="Test Property", code="TST01"
        )
        self.section = Section.objects.create(
            property=self.property, name="Section A"
        )
        self.unit = Unit.objects.create(
            section=self.section,
            name="Room 1",
            capacity=2,
            semester_price=Decimal("500000.00"),
            monthly_price=Decimal("200000.00"),
        )
        self.student = Student.objects.create(
            first_name="John",
            last_name="Doe",
            email="john@example.com",
            student_id_number="STU001",
            national_id="NAT001",
        )

        self.payment_url = "/api/payments/"
        self.receipt_url = "/api/payments/receipts/"
        self.payment_data = {
            "student": self.student.id,
            "amount": "150000.00",
            "payment_date": date.today().isoformat(),
            "payment_method": "cash",
            "reference": "REF001",
            "notes": "First payment",
        }

    def _record(self, **overrides):
        data = {**self.payment_data, **overrides}
        return self.client.post(self.payment_url, data, format="json")

    def _create_occupancy(self, start_date=None, billing_mode="semester"):
        sd = start_date or (date.today() - timedelta(days=60))
        return Occupancy.objects.create(
            student=self.student, unit=self.unit,
            start_date=sd, billing_mode=billing_mode,
        )

    # --- Receipt auto-generation ---

    def test_receipt_created_on_payment(self):
        self._create_occupancy()
        response = self._record()
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        receipt = Receipt.objects.filter(payment_id=response.data["id"]).first()
        self.assertIsNotNone(receipt)
        self.assertTrue(receipt.receipt_number.startswith("RCP-"))

    def test_receipt_contains_correct_data(self):
        self._create_occupancy()
        response = self._record()
        receipt = Receipt.objects.get(payment_id=response.data["id"])
        self.assertEqual(receipt.student_name, "John Doe")
        self.assertEqual(receipt.student_id_number, "STU001")
        self.assertEqual(receipt.amount, Decimal("150000.00"))
        self.assertEqual(receipt.payment_method, "cash")
        self.assertEqual(receipt.reference, "REF001")
        self.assertEqual(receipt.unit_name, "Room 1")
        self.assertEqual(receipt.property_name, "Test Property")

    def test_receipt_outstanding_balance(self):
        self._create_occupancy(billing_mode="semester")
        self._record(amount="50000.00", reference="REF001")
        receipt = Receipt.objects.first()
        expected_balance = self.unit.semester_price - Decimal("50000.00")
        self.assertEqual(receipt.outstanding_balance_after, expected_balance)

    # --- Receipt list ---

    def test_list_receipts_empty(self):
        response = self.client.get(self.receipt_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 0)

    def test_list_receipts(self):
        self._create_occupancy()
        self._record()
        self._record(amount="200000.00", reference="REF002")
        response = self.client.get(self.receipt_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 2)

    def test_list_receipts_pagination(self):
        self._create_occupancy()
        for i in range(25):
            self._record(
                amount="10000.00",
                reference=f"REF{i:03d}",
            )
        response = self.client.get(self.receipt_url, {"page_size": 10})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 25)
        self.assertEqual(len(response.data["results"]), 10)
        self.assertEqual(response.data["total_pages"], 3)

    def test_list_receipts_unauthenticated(self):
        self.client.credentials()
        response = self.client.get(self.receipt_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    # --- Receipt search ---

    def test_search_receipt_by_number(self):
        self._create_occupancy()
        self._record()
        receipt = Receipt.objects.first()
        response = self.client.get(self.receipt_url, {"search": receipt.receipt_number})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)

    def test_search_receipt_by_occupant_name(self):
        self._create_occupancy()
        self._record()
        response = self.client.get(self.receipt_url, {"search": "John"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)

    def test_search_receipt_by_reference(self):
        self._create_occupancy()
        self._record()
        response = self.client.get(self.receipt_url, {"search": "REF001"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)

    def test_search_receipt_no_results(self):
        self._create_occupancy()
        self._record()
        response = self.client.get(self.receipt_url, {"search": "Nonexistent"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 0)

    # --- Receipt retrieve ---

    def test_retrieve_receipt(self):
        self._create_occupancy()
        self._record()
        receipt = Receipt.objects.first()
        response = self.client.get(f"{self.receipt_url}{receipt.id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["receipt_number"], receipt.receipt_number)
        self.assertEqual(response.data["student_name"], "John Doe")
        self.assertEqual(response.data["amount"], "150000.00")

    def test_retrieve_nonexistent_receipt(self):
        response = self.client.get(f"{self.receipt_url}99999/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    # --- Receipt PDF ---

    def test_receipt_pdf_download(self):
        self._create_occupancy()
        self._record()
        receipt = Receipt.objects.first()
        response = self.client.get(f"{self.receipt_url}{receipt.id}/pdf/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response["Content-Type"],
            "application/pdf",
        )
        self.assertIn(
            receipt.receipt_number,
            response["Content-Disposition"],
        )

    def test_receipt_pdf_nonexistent(self):
        response = self.client.get(f"{self.receipt_url}99999/pdf/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
