from django.test import TestCase
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.occupancy.models import Occupancy
from apps.occupants.models import Student
from apps.sections.models import Section
from apps.units.models import Unit

from .models import Property


class PropertyExplorerAPITests(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="admin", password="pass123", is_staff=True
        )
        self.token = Token.objects.create(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")
        self.url = "/api/properties/explorer/"

        self.prop = Property.objects.create(
            name="Main Campus", code="MC01"
        )
        self.section = Section.objects.create(
            property=self.prop, name="Block A"
        )
        self.unit = Unit.objects.create(
            section=self.section,
            name="Room 101",
            capacity=2,
            semester_price=500000,
            monthly_price=200000,
        )
        self.student = Student.objects.create(
            first_name="John", last_name="Doe",
            email="john@example.com",
            student_id_number="STU001", national_id="NAT001",
        )

    def test_explorer_unauthenticated(self):
        self.client.credentials()
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_explorer_returns_properties(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["name"], "Main Campus")
        self.assertEqual(response.data[0]["code"], "MC01")

    def test_explorer_returns_nested_sections(self):
        Section.objects.create(property=self.prop, name="Block B")
        response = self.client.get(self.url)
        self.assertEqual(len(response.data[0]["sections"]), 2)
        names = {s["name"] for s in response.data[0]["sections"]}
        self.assertIn("Block A", names)
        self.assertIn("Block B", names)

    def test_explorer_returns_nested_units(self):
        response = self.client.get(self.url)
        sections = response.data[0]["sections"]
        self.assertEqual(len(sections[0]["units"]), 1)
        unit = sections[0]["units"][0]
        self.assertEqual(unit["name"], "Room 101")
        self.assertEqual(unit["capacity"], 2)
        self.assertEqual(unit["current_occupant_count"], 0)
        self.assertFalse(unit["is_full"])
        self.assertEqual(unit["occupancy_percentage"], 0)
        self.assertEqual(unit["active_occupants"], [])

    def test_explorer_excludes_inactive_properties(self):
        Property.objects.create(name="Inactive", code="IN01", is_active=False)
        response = self.client.get(self.url)
        self.assertEqual(len(response.data), 1)

    def test_explorer_excludes_inactive_sections(self):
        Section.objects.create(property=self.prop, name="Inactive Block", is_active=False)
        response = self.client.get(self.url)
        self.assertEqual(len(response.data[0]["sections"]), 1)

    def test_explorer_excludes_inactive_units(self):
        Unit.objects.create(
            section=self.section, name="Inactive Room", capacity=1,
            semester_price=300000, monthly_price=150000, status="maintenance",
        )
        response = self.client.get(self.url)
        self.assertEqual(len(response.data[0]["sections"][0]["units"]), 1)

    def test_explorer_occupant_count_and_active_occupants(self):
        Occupancy.objects.create(
            student=self.student, unit=self.unit,
            start_date="2026-01-01", billing_mode="semester",
        )
        response = self.client.get(self.url)
        unit = response.data[0]["sections"][0]["units"][0]
        self.assertEqual(unit["current_occupant_count"], 1)
        self.assertEqual(unit["available_spaces"], 1)
        self.assertFalse(unit["is_full"])
        self.assertEqual(unit["occupancy_percentage"], 50)
        self.assertEqual(len(unit["active_occupants"]), 1)
        self.assertEqual(unit["active_occupants"][0]["name"], "John Doe")

    def test_explorer_full_unit(self):
        student2 = Student.objects.create(
            first_name="Jane", last_name="Smith",
            email="jane@example.com",
            student_id_number="STU002", national_id="NAT002",
        )
        Occupancy.objects.create(
            student=self.student, unit=self.unit,
            start_date="2026-01-01", billing_mode="semester",
        )
        Occupancy.objects.create(
            student=student2, unit=self.unit,
            start_date="2026-01-01", billing_mode="semester",
        )
        response = self.client.get(self.url)
        unit = response.data[0]["sections"][0]["units"][0]
        self.assertEqual(unit["current_occupant_count"], 2)
        self.assertEqual(unit["available_spaces"], 0)
        self.assertTrue(unit["is_full"])
        self.assertEqual(unit["occupancy_percentage"], 100)
        self.assertEqual(len(unit["active_occupants"]), 2)

    def test_explorer_search_by_unit_name(self):
        Section.objects.create(property=self.prop, name="Block B")
        Unit.objects.create(
            section=self.section, name="Room 102", capacity=2,
            semester_price=400000, monthly_price=180000,
        )
        response = self.client.get(self.url, {"search": "101"})
        self.assertEqual(len(response.data), 1)
        units = response.data[0]["sections"][0]["units"]
        self.assertEqual(len(units), 1)
        self.assertEqual(units[0]["name"], "Room 101")

    def test_explorer_search_by_occupant_name(self):
        Occupancy.objects.create(
            student=self.student, unit=self.unit,
            start_date="2026-01-01", billing_mode="semester",
        )
        response = self.client.get(self.url, {"search": "John"})
        self.assertEqual(len(response.data), 1)
        unit = response.data[0]["sections"][0]["units"][0]
        self.assertEqual(unit["name"], "Room 101")

    def test_explorer_search_no_results(self):
        response = self.client.get(self.url, {"search": "Nonexistent"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 0)

    def test_explorer_search_returns_only_matching_property(self):
        prop2 = Property.objects.create(name="Other Campus", code="OC01")
        sec2 = Section.objects.create(property=prop2, name="Building X")
        Unit.objects.create(
            section=sec2, name="Suite 1", capacity=2,
            semester_price=600000, monthly_price=250000,
        )
        response = self.client.get(self.url, {"search": "Room 101"})
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["name"], "Main Campus")
