from datetime import date, timedelta

from django.test import TestCase
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.occupants.models import Student
from apps.properties.models import Property
from apps.sections.models import Section
from apps.units.models import Unit

from .models import Occupancy


class OccupancyAPITests(TestCase):

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
            semester_price=500000,
            monthly_price=200000,
        )
        self.student = Student.objects.create(
            first_name="John",
            last_name="Doe",
            email="john@example.com",
            student_id_number="STU001",
            national_id="NAT001",
        )

        self.list_url = "/api/occupancy/"
        self.assign_data = {
            "student": self.student.id,
            "unit": self.unit.id,
            "start_date": (date.today() - timedelta(days=1)).isoformat(),
            "billing_mode": "semester",
        }

    def _assign(self, **overrides):
        data = {**self.assign_data, **overrides}
        return self.client.post(self.list_url, data, format="json")

    # --- Authentication ---

    def test_unauthenticated(self):
        self.client.credentials()
        response = self._assign()
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    # --- Assign (Create) ---

    def test_assign_success(self):
        response = self._assign()
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["student"], self.student.id)
        self.assertEqual(response.data["unit"], self.unit.id)
        self.assertEqual(response.data["billing_mode"], "semester")
        self.assertTrue(response.data["is_active"])
        self.assertIsNone(response.data["end_date"])
        self.assertIn("student_full_name", response.data)
        self.assertIn("unit_name", response.data)
        self.assertIn("property_name", response.data)

    def test_assign_nonexistent_student(self):
        response = self._assign(student=99999)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_assign_nonexistent_unit(self):
        response = self._assign(unit=99999)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_assign_archived_student(self):
        self.student.is_active = False
        self.student.save()
        response = self._assign()
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertIn("archived", response.data["detail"].lower())

    def test_assign_duplicate_active_occupancy(self):
        self._assign()
        response = self._assign()
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertIn("already has an active occupancy", response.data["detail"])

    def test_assign_full_unit(self):
        self._assign()
        student2 = Student.objects.create(
            first_name="Jane", last_name="Smith", email="jane@example.com",
            student_id_number="STU002", national_id="NAT002",
        )
        response = self._assign(student=student2.id)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Occupancy.objects.filter(end_date__isnull=True).count(), 2)
        student3 = Student.objects.create(
            first_name="Alice", last_name="Brown", email="alice@example.com",
            student_id_number="STU003", national_id="NAT003",
        )
        response = self._assign(student=student3.id)
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertIn("full capacity", response.data["detail"])

    def test_assign_inactive_unit(self):
        self.unit.status = "maintenance"
        self.unit.save()
        response = self._assign()
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertIn("not available", response.data["detail"])

    def test_assign_without_start_date(self):
        response = self._assign(start_date="")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_assign_without_billing_mode(self):
        response = self._assign(billing_mode="")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    # --- Retrieve ---

    def test_retrieve_occupancy(self):
        create_resp = self._assign()
        occupancy_id = create_resp.data["id"]
        response = self.client.get(f"{self.list_url}{occupancy_id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], occupancy_id)
        self.assertEqual(response.data["student"], self.student.id)

    def test_retrieve_nonexistent(self):
        response = self.client.get(f"{self.list_url}99999/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    # --- List ---

    def test_list_empty(self):
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 0)

    def test_list_with_student_filter(self):
        self._assign()
        response = self.client.get(self.list_url, {"student_id": self.student.id})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)

    def test_list_with_active_only_filter(self):
        self._assign()
        occupancy = Occupancy.objects.get(student=self.student)
        occupancy.end_date = date.today()
        occupancy.is_active = False
        occupancy.save()
        response = self.client.get(self.list_url, {"active_only": "true"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 0)

    # --- Partial Update ---

    def test_update_occupancy(self):
        create_resp = self._assign()
        occupancy_id = create_resp.data["id"]
        response = self.client.patch(
            f"{self.list_url}{occupancy_id}/",
            {"billing_mode": "monthly"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["billing_mode"], "monthly")

    def test_update_nonexistent(self):
        response = self.client.patch(
            f"{self.list_url}99999/",
            {"billing_mode": "monthly"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    # --- Checkout ---

    def test_checkout_success(self):
        create_resp = self._assign()
        occupancy_id = create_resp.data["id"]
        response = self.client.post(f"{self.list_url}{occupancy_id}/checkout/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["end_date"], date.today().isoformat())
        self.assertFalse(response.data["is_active"])

    def test_checkout_twice(self):
        create_resp = self._assign()
        occupancy_id = create_resp.data["id"]
        self.client.post(f"{self.list_url}{occupancy_id}/checkout/")
        response = self.client.post(f"{self.list_url}{occupancy_id}/checkout/")
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertIn("already closed", response.data["detail"])

    def test_checkout_nonexistent(self):
        response = self.client.post(f"{self.list_url}99999/checkout/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_assign_after_checkout(self):
        create_resp = self._assign()
        occupancy_id = create_resp.data["id"]
        self.client.post(f"{self.list_url}{occupancy_id}/checkout/")
        response = self._assign()
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    # --- Summary ---

    def test_summary_empty(self):
        response = self.client.get(f"{self.list_url}summary/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["total_occupied"], 0)
        self.assertEqual(response.data["total_capacity"], self.unit.capacity)
        self.assertEqual(len(response.data["properties"]), 1)

    def test_summary_with_occupancy(self):
        self._assign()
        response = self.client.get(f"{self.list_url}summary/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["total_occupied"], 1)
        self.assertEqual(response.data["total_available"], self.unit.capacity - 1)

    def test_summary_unauthenticated(self):
        self.client.credentials()
        response = self.client.get(f"{self.list_url}summary/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
