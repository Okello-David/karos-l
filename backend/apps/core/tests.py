from django.test import TestCase
from django.contrib.auth.models import Group
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.properties.models import Property


class DrfExceptionHandlerTests(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="testuser", password="testpass123",
        )
        self.token, _ = Token.objects.get_or_create(user=self.user)

    def test_unauthenticated_returns_json_detail(self):
        response = self.client.get("/api/occupants/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertIn("detail", response.data)
        self.assertIn("status_code", response.data)
        self.assertEqual(response.data["status_code"], 401)

    def test_not_found_returns_json_detail(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")
        response = self.client.get("/api/occupants/99999/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn("detail", response.data)
        self.assertIn("status_code", response.data)

    def test_validation_error_returns_json(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")
        response = self.client.post("/api/occupants/", {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("first_name", response.data)
        self.assertIn("status_code", response.data)
        self.assertEqual(response.data["status_code"], 400)


class ReleaseWorkflowAPITests(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.password = "releasepass123"
        self.user = User.objects.create_superuser(
            username="release-admin",
            email="release@example.com",
            password=self.password,
        )
        group, _ = Group.objects.get_or_create(name="Property Manager")
        self.user.groups.add(group)

    def test_release_workflow_api_chain(self):
        login = self.client.post(
            "/api/auth/login/",
            {"username": self.user.username, "password": self.password},
            format="json",
        )
        self.assertEqual(login.status_code, status.HTTP_200_OK)
        token = login.data["token"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token}")

        prop_resp = self.client.post(
            "/api/admin/properties/",
            {"name": "Release Property", "code": "REL01", "address": "Release Road"},
            format="json",
        )
        self.assertEqual(prop_resp.status_code, status.HTTP_201_CREATED)
        prop_id = prop_resp.data["id"]

        prop_get = self.client.get(f"/api/admin/properties/{prop_id}/")
        self.assertEqual(prop_get.status_code, status.HTTP_200_OK)
        self.assertEqual(prop_get.data["name"], "Release Property")

        section_resp = self.client.post(
            "/api/admin/sections/",
            {"property": prop_id, "name": "Release Block", "order": 0},
            format="json",
        )
        self.assertEqual(section_resp.status_code, status.HTTP_201_CREATED)
        section_id = section_resp.data["id"]

        unit_resp = self.client.post(
            "/api/admin/units/",
            {
                "section": section_id,
                "name": "Release Unit",
                "capacity": 2,
                "semester_price": "500000.00",
                "monthly_price": "200000.00",
            },
            format="json",
        )
        self.assertEqual(unit_resp.status_code, status.HTTP_201_CREATED)
        unit_id = unit_resp.data["id"]

        occupant_resp = self.client.post(
            "/api/occupants/",
            {
                "first_name": "Release",
                "last_name": "Student",
                "email": "release.student@example.com",
                "phone": "+256700111999",
                "student_id_number": "REL-STU-001",
                "national_id": "REL-NAT-001",
            },
            format="json",
        )
        self.assertEqual(occupant_resp.status_code, status.HTTP_201_CREATED)
        student_id = occupant_resp.data["id"]

        occupancy_resp = self.client.post(
            "/api/occupancy/",
            {
                "student": student_id,
                "unit": unit_id,
                "start_date": "2026-07-01",
                "billing_mode": "semester",
            },
            format="json",
        )
        self.assertEqual(occupancy_resp.status_code, status.HTTP_201_CREATED)

        payment_resp = self.client.post(
            "/api/payments/",
            {
                "student": student_id,
                "amount": "150000.00",
                "payment_date": "2026-07-01",
                "payment_method": "cash",
                "reference": "REL-PAY-001",
            },
            format="json",
        )
        self.assertEqual(payment_resp.status_code, status.HTTP_201_CREATED)
        self.assertIsNotNone(payment_resp.data["receipt_id"])
        self.assertIsNotNone(payment_resp.data["receipt_number"])

        receipt_resp = self.client.get(f"/api/payments/receipts/{payment_resp.data['receipt_id']}/")
        self.assertEqual(receipt_resp.status_code, status.HTTP_200_OK)
        self.assertEqual(receipt_resp.data["student_name"], "Release Student")

        dashboard_resp = self.client.get("/api/occupancy/summary/")
        self.assertEqual(dashboard_resp.status_code, status.HTTP_200_OK)
        self.assertEqual(dashboard_resp.data["total_occupied"], 1)
        self.assertEqual(dashboard_resp.data["total_students"], 1)

        explorer_resp = self.client.get("/api/properties/explorer/")
        self.assertEqual(explorer_resp.status_code, status.HTTP_200_OK)
        self.assertEqual(explorer_resp.data[0]["name"], "Release Property")
        self.assertEqual(explorer_resp.data[0]["sections"][0]["units"][0]["current_occupant_count"], 1)

        backup_resp = self.client.post("/api/backups/", {"notes": "release workflow"}, format="json")
        self.assertEqual(backup_resp.status_code, status.HTTP_201_CREATED)
        backup_id = backup_resp.data["id"]

        export_resp = self.client.get("/api/backups/export/?entity=occupants&file_format=csv")
        self.assertEqual(export_resp.status_code, status.HTTP_200_OK)
        self.assertIn(b"Release", export_resp.content)

        Property.objects.filter(id=prop_id).update(name="Modified Release Property")
        restore_resp = self.client.post(
            f"/api/backups/{backup_id}/restore/",
            {"backup_id": backup_id, "confirm": True},
            format="json",
        )
        self.assertEqual(restore_resp.status_code, status.HTTP_200_OK)
        self.assertEqual(Property.objects.get(id=prop_id).name, "Release Property")

        logout_resp = self.client.post("/api/auth/logout/")
        self.assertEqual(logout_resp.status_code, status.HTTP_200_OK)
        self.assertFalse(Token.objects.filter(key=token).exists())
