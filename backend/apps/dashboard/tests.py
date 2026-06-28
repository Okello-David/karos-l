from django.test import TestCase
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.properties.models import Property
from apps.sections.models import Section
from apps.units.models import Unit
from apps.occupants.models import Student
from apps.occupancy.models import Occupancy
from apps.payments.models import Payment


class DashboardTests(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.url = "/api/dashboard/"
        self.user = User.objects.create_user(
            username="manager", password="testpass123", is_staff=True,
        )
        self.token, _ = Token.objects.get_or_create(user=self.user)

        prop = Property.objects.create(name="Test Property", code="TP")
        section = Section.objects.create(name="Section A", property=prop)
        self.unit = Unit.objects.create(
            name="Unit 1", section=section, capacity=2,
            semester_price=1000, monthly_price=500,
        )
        self.student = Student.objects.create(
            first_name="John", last_name="Doe",
            email="john@example.com", is_active=True,
        )

    def test_unauthenticated(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_dashboard_summary(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.data
        self.assertIn("total_capacity", data)
        self.assertIn("total_occupied", data)
        self.assertIn("total_available", data)
        self.assertIn("occupancy_rate", data)
        self.assertIn("total_students", data)
        self.assertIn("recent_payments", data)
        self.assertEqual(data["total_capacity"], 2)
        self.assertEqual(data["total_occupied"], 0)
        self.assertEqual(data["total_students"], 1)

    def test_dashboard_with_occupancy(self):
        Occupancy.objects.create(
            student=self.student, unit=self.unit,
            start_date="2026-01-01", billing_mode="semester",
        )
        Payment.objects.create(
            student=self.student, amount=500,
            payment_date="2026-01-15", payment_method="cash",
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.data
        self.assertEqual(data["total_occupied"], 1)
        self.assertEqual(data["total_available"], 1)
        self.assertEqual(len(data["recent_payments"]), 1)
        self.assertEqual(data["recent_payments"][0]["amount"], "500.00")

    def test_dashboard_property_manager_access(self):
        from django.contrib.auth.models import Group
        group, _ = Group.objects.get_or_create(name="Property Manager")
        self.user.groups.add(group)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
