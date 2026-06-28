from decimal import Decimal
from datetime import date

from django.contrib.auth.models import Group
from django.test import TestCase

from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.properties.models import Property
from apps.sections.models import Section
from apps.units.models import PricingRule, Unit, UnitStatus


class AdminAPITests(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="admin", password="pass123", is_staff=True
        )
        self.token = Token.objects.create(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")

        self.prop = Property.objects.create(
            name="Test Property", code="TST01", address="123 Main St"
        )
        self.section = Section.objects.create(
            property=self.prop, name="Block A", order=0
        )
        self.unit = Unit.objects.create(
            section=self.section, name="Room 1", capacity=2,
            semester_price=Decimal("500000.00"),
            monthly_price=Decimal("200000.00"),
        )

        self.admin_url = "/api/admin/"

    # ---- Properties ----

    def test_list_properties(self):
        response = self.client.get(f"{self.admin_url}properties/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

    def test_create_property(self):
        data = {"name": "New Prop", "code": "NEW01", "address": "456 Oak St"}
        response = self.client.post(f"{self.admin_url}properties/", data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["name"], "New Prop")

    def test_create_property_duplicate_code(self):
        data = {"name": "Duplicate", "code": "TST01"}
        response = self.client.post(f"{self.admin_url}properties/", data, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_retrieve_property(self):
        response = self.client.get(f"{self.admin_url}properties/{self.prop.id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["name"], "Test Property")

    def test_update_property(self):
        data = {"name": "Updated", "code": "TST01"}
        response = self.client.put(
            f"{self.admin_url}properties/{self.prop.id}/", data, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["name"], "Updated")

    def test_partial_update_property(self):
        data = {"description": "New description"}
        response = self.client.patch(
            f"{self.admin_url}properties/{self.prop.id}/", data, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["description"], "New description")

    def test_archive_property(self):
        self.unit.status = "archived"
        self.unit.save()
        self.section.is_active = False
        self.section.save()
        response = self.client.post(
            f"{self.admin_url}properties/{self.prop.id}/archive/"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.prop.refresh_from_db()
        self.assertFalse(self.prop.is_active)

    def test_archive_property_with_active_sections(self):
        Section.objects.create(property=self.prop, name="Another Block")
        response = self.client.post(
            f"{self.admin_url}properties/{self.prop.id}/archive/"
        )
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)

    def test_archive_nonexistent_property(self):
        response = self.client.post(f"{self.admin_url}properties/99999/archive/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_properties_unauthenticated(self):
        self.client.credentials()
        response = self.client.get(f"{self.admin_url}properties/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    # ---- Sections ----

    def test_list_sections(self):
        response = self.client.get(f"{self.admin_url}sections/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

    def test_list_sections_filter_by_property(self):
        response = self.client.get(
            f"{self.admin_url}sections/?property_id={self.prop.id}"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

        response = self.client.get(f"{self.admin_url}sections/?property_id=99999")
        self.assertEqual(len(response.data), 0)

    def test_create_section(self):
        data = {"property": self.prop.id, "name": "Block B", "order": 1}
        response = self.client.post(f"{self.admin_url}sections/", data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["name"], "Block B")

    def test_create_section_duplicate_name(self):
        data = {"property": self.prop.id, "name": "Block A"}
        response = self.client.post(f"{self.admin_url}sections/", data, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_retrieve_section(self):
        response = self.client.get(f"{self.admin_url}sections/{self.section.id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["name"], "Block A")

    def test_update_section(self):
        data = {"property": self.prop.id, "name": "Block A Renamed"}
        response = self.client.put(
            f"{self.admin_url}sections/{self.section.id}/", data, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["name"], "Block A Renamed")

    def test_archive_section(self):
        self.unit.status = "archived"
        self.unit.save()
        response = self.client.post(
            f"{self.admin_url}sections/{self.section.id}/archive/"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.section.refresh_from_db()
        self.assertFalse(self.section.is_active)

    def test_archive_section_with_active_units(self):
        Unit.objects.create(
            section=self.section, name="Room 2", capacity=1,
            semester_price=300000, monthly_price=100000,
        )
        response = self.client.post(
            f"{self.admin_url}sections/{self.section.id}/archive/"
        )
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)

    def test_reorder_sections(self):
        sec2 = Section.objects.create(
            property=self.prop, name="Block B", order=1
        )
        data = [
            {"id": self.section.id, "order": 1},
            {"id": sec2.id, "order": 0},
        ]
        response = self.client.post(
            f"{self.admin_url}sections/reorder/", data, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        sec2.refresh_from_db()
        self.assertEqual(sec2.order, 0)

    # ---- Units ----

    def test_list_units(self):
        response = self.client.get(f"{self.admin_url}units/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

    def test_list_units_filter_by_section(self):
        response = self.client.get(
            f"{self.admin_url}units/?section_id={self.section.id}"
        )
        self.assertEqual(len(response.data), 1)

    def test_list_units_filter_by_status(self):
        response = self.client.get(f"{self.admin_url}units/?status=active")
        self.assertEqual(len(response.data), 1)
        response = self.client.get(f"{self.admin_url}units/?status=maintenance")
        self.assertEqual(len(response.data), 0)

    def test_create_unit(self):
        data = {
            "section": self.section.id,
            "name": "Room 2",
            "capacity": 1,
            "semester_price": "300000.00",
            "monthly_price": "150000.00",
        }
        response = self.client.post(f"{self.admin_url}units/", data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["name"], "Room 2")
        self.assertEqual(response.data["status"], "active")

    def test_create_unit_duplicate(self):
        data = {
            "section": self.section.id,
            "name": "Room 1",
            "capacity": 2,
            "semester_price": "500000.00",
            "monthly_price": "200000.00",
        }
        response = self.client.post(f"{self.admin_url}units/", data, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_retrieve_unit(self):
        response = self.client.get(f"{self.admin_url}units/{self.unit.id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["name"], "Room 1")

    def test_update_unit(self):
        data = {
            "section": self.section.id,
            "name": "Room 1 Updated",
            "capacity": 3,
            "semester_price": "600000.00",
            "monthly_price": "250000.00",
        }
        response = self.client.put(
            f"{self.admin_url}units/{self.unit.id}/", data, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["name"], "Room 1 Updated")
        self.assertEqual(response.data["capacity"], 3)

    def test_partial_update_unit_status(self):
        data = {"status": "maintenance"}
        response = self.client.patch(
            f"{self.admin_url}units/{self.unit.id}/", data, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "maintenance")
        self.assertFalse(response.data["is_active"])

    def test_archive_unit(self):
        response = self.client.post(
            f"{self.admin_url}units/{self.unit.id}/archive/"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.unit.refresh_from_db()
        self.assertEqual(self.unit.status, "archived")

    def test_archive_unit_not_found(self):
        response = self.client.post(f"{self.admin_url}units/99999/archive/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    # ---- Pricing Rules ----

    def test_list_pricing_rules_empty(self):
        response = self.client.get(f"{self.admin_url}pricing-rules/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 0)

    def test_create_pricing_rule(self):
        data = {
            "unit": self.unit.id,
            "billing_mode": "semester",
            "price": "450000.00",
            "effective_date": "2026-06-01",
        }
        response = self.client.post(
            f"{self.admin_url}pricing-rules/", data, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["billing_mode"], "semester")

    def test_list_pricing_rules(self):
        PricingRule.objects.create(
            unit=self.unit, billing_mode="semester",
            price=Decimal("450000.00"), effective_date=date(2026, 6, 1),
        )
        PricingRule.objects.create(
            unit=self.unit, billing_mode="monthly",
            price=Decimal("180000.00"), effective_date=date(2026, 6, 1),
        )
        response = self.client.get(f"{self.admin_url}pricing-rules/")
        self.assertEqual(len(response.data), 2)

    def test_create_pricing_rule_invalid_price(self):
        data = {
            "unit": self.unit.id,
            "billing_mode": "semester",
            "price": "-100.00",
            "effective_date": "2026-06-01",
        }
        response = self.client.post(
            f"{self.admin_url}pricing-rules/", data, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_delete_pricing_rule(self):
        rule = PricingRule.objects.create(
            unit=self.unit, billing_mode="semester",
            price=Decimal("450000.00"), effective_date=date(2026, 6, 1),
        )
        response = self.client.delete(
            f"{self.admin_url}pricing-rules/{rule.id}/"
        )
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(PricingRule.objects.count(), 0)

    # ---- Users ----

    def test_list_users(self):
        response = self.client.get(f"{self.admin_url}users/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(response.data), 1)

    def test_list_groups(self):
        Group.objects.get_or_create(name="Custom Role")
        response = self.client.get(f"{self.admin_url}users/groups/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(response.data), 1)

    def test_create_user(self):
        data = {
            "username": "newuser",
            "email": "new@example.com",
            "password": "secret123",
            "is_staff": True,
        }
        response = self.client.post(f"{self.admin_url}users/", data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["username"], "newuser")
        self.assertTrue(response.data["is_staff"])

    def test_toggle_user_active(self):
        user2 = User.objects.create_user(
            username="testuser", password="pass123"
        )
        self.assertTrue(user2.is_active)
        response = self.client.post(
            f"{self.admin_url}users/{user2.id}/toggle-active/"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        user2.refresh_from_db()
        self.assertFalse(user2.is_active)

    def test_users_unauthenticated(self):
        self.client.credentials()
        response = self.client.get(f"{self.admin_url}users/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
