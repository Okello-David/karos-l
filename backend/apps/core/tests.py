from decimal import Decimal

from django.test import TestCase
from django.contrib.auth.models import Group
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.occupants.models import Student
from apps.occupancy.models import Occupancy
from apps.payments.models import Payment
from apps.properties.models import Property
from apps.sections.models import Section
from apps.units.models import Unit


class DrfExceptionHandlerTests(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="testuser", password="testpass123",
        )
        group, _ = Group.objects.get_or_create(name="Property Manager")
        self.user.groups.add(group)
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


class HealthCheckTests(TestCase):

    def test_health_check_ok_no_auth_required(self):
        client = APIClient()
        response = client.get("/api/health/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "ok")
        self.assertEqual(response.data["database"], "ok")


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


class AuthorizationMatrixTests(TestCase):
    """Cross-role regression coverage for the RBAC hardening pass (see
    docs/ARCHITECTURE_DECISIONS.md and docs/SECURITY_HARDENING.md).

    Explicitly guards against two things recurring:
    - the original permission gap (IsAuthenticated | IsPropertyManager no-op) —
      a plain authenticated ("Staff") user gaining write access merely by being
      authenticated;
    - an ID-substitution bypass — supplying a real, existing object's ID does
      not unlock access a role wouldn't otherwise have; the permission check
      runs before the object is ever looked up, regardless of whether that ID
      is valid, someone else's, or fabricated.
    """

    def setUp(self):
        self.staff_user = User.objects.create_user(username="staffonly", password="pass123")
        self.staff_token = Token.objects.create(user=self.staff_user)

        self.manager_user = User.objects.create_user(username="pmuser", password="pass123")
        manager_group, _ = Group.objects.get_or_create(name="Property Manager")
        self.manager_user.groups.add(manager_group)
        self.manager_token = Token.objects.create(user=self.manager_user)

        self.super_user = User.objects.create_superuser(
            username="superuser1", email="super1@example.com", password="pass123"
        )
        self.super_token = Token.objects.create(user=self.super_user)

        # Real, pre-existing objects — used to prove that a valid ID doesn't
        # bypass the permission check for a role that shouldn't have access.
        self.property = Property.objects.create(name="Matrix Property", code="MTX01")
        self.section = Section.objects.create(property=self.property, name="Block A")
        self.unit = Unit.objects.create(
            section=self.section, name="Room 1", capacity=2,
            semester_price=Decimal("500000.00"), monthly_price=Decimal("200000.00"),
        )
        self.student = Student.objects.create(
            first_name="Matrix", last_name="Student", email="matrix@example.com",
            student_id_number="MTX-STU-001", national_id="MTX-NAT-001",
        )
        self.occupancy = Occupancy.objects.create(
            student=self.student, unit=self.unit,
            start_date="2026-01-01", billing_mode="semester",
        )
        self.payment = Payment.objects.create(
            student=self.student, amount=Decimal("100000.00"),
            payment_date="2026-01-01", payment_method="cash", reference="MTX-PAY-001",
        )

    def _client(self, token):
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
        return client

    # --- Elevation prevention: authentication alone never grants write access ---

    def test_staff_cannot_create_occupant(self):
        response = self._client(self.staff_token).post("/api/occupants/", {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_staff_cannot_record_payment(self):
        response = self._client(self.staff_token).post("/api/payments/", {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_staff_cannot_assign_occupancy(self):
        response = self._client(self.staff_token).post("/api/occupancy/", {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_staff_cannot_create_property(self):
        response = self._client(self.staff_token).post("/api/admin/properties/", {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    # --- ID substitution: a real, existing object ID does not bypass the check ---

    def test_staff_cannot_update_real_occupant_by_id(self):
        response = self._client(self.staff_token).patch(
            f"/api/occupants/{self.student.id}/", {"first_name": "Changed"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.student.refresh_from_db()
        self.assertEqual(self.student.first_name, "Matrix")

    def test_staff_cannot_archive_real_property_by_id(self):
        response = self._client(self.staff_token).post(f"/api/admin/properties/{self.property.id}/archive/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.property.refresh_from_db()
        self.assertTrue(self.property.is_active)

    def test_property_manager_cannot_reset_real_users_password_by_id(self):
        """The specific escalation this sprint closed: a Property Manager must not be
        able to reach a real user account's password field via any object ID."""
        original_hash = self.super_user.password
        response = self._client(self.manager_token).patch(
            f"/api/admin/users/{self.super_user.id}/", {"password": "hijacked"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.super_user.refresh_from_db()
        self.assertEqual(self.super_user.password, original_hash)

    # --- Staff read access is deliberately asymmetric — see the RBAC matrix ---
    #
    # Properties/sections/units/dashboard/reports/receipts stay open to any authenticated
    # user (viewing that data was never the audit's concern). Occupants/occupancy/payments
    # are scoped to Property Manager for EVERY action on the viewset, including list/
    # retrieve, not just writes — these ViewSets bundle read and write actions under one
    # permission_classes, and the original decision was that this whole surface (not just
    # its write actions) is Property-Manager-and-above only. Documented explicitly here so
    # it's a deliberate, tested boundary rather than an undocumented surprise.

    def test_staff_can_read_properties(self):
        response = self._client(self.staff_token).get("/api/properties/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_staff_cannot_read_occupants(self):
        response = self._client(self.staff_token).get("/api/occupants/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_staff_cannot_read_payments(self):
        response = self._client(self.staff_token).get("/api/payments/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_staff_can_read_occupancy_summary(self):
        """The Dashboard/Overview page depends on this aggregate endpoint for every
        authenticated user, not just Property Managers — see get_permissions() on
        OccupancyViewSet. Regression guard: this must not get swept into the
        Property-Manager-only gate along with occupancy's other (write) actions."""
        response = self._client(self.staff_token).get("/api/occupancy/summary/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    # --- Property Manager: full business write access, no admin/user access ---

    def test_property_manager_can_write_business_data(self):
        response = self._client(self.manager_token).patch(
            f"/api/admin/properties/{self.property.id}/", {"name": "Renamed"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_property_manager_cannot_view_audit_log(self):
        response = self._client(self.manager_token).get("/api/audit/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_property_manager_cannot_manage_backups(self):
        response = self._client(self.manager_token).get("/api/backups/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    # --- Super Administrator: full access, including user/audit/backup surfaces ---

    def test_superuser_can_manage_users(self):
        response = self._client(self.super_token).get("/api/admin/users/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_superuser_can_view_audit_log(self):
        response = self._client(self.super_token).get("/api/audit/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_superuser_can_write_business_data(self):
        response = self._client(self.super_token).post("/api/payments/", {
            "student": self.student.id, "amount": "50000.00",
            "payment_date": "2026-01-02", "payment_method": "cash",
        }, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
