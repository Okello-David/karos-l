from datetime import date

from django.contrib.auth.models import Group
from django.test import TestCase
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.occupants.models import Student

from .models import AuditLog
from .services import AuditService


class AuditModelTests(TestCase):

    def test_create_audit_log(self):
        user = User.objects.create_user(
            username="admin", password="pass123", is_superuser=True
        )
        log = AuditLog.objects.create(
            actor=user,
            entity_type=AuditLog.EntityType.OCCUPANT,
            entity_id=1,
            action=AuditLog.Action.CREATE,
            description="Occupant Jane Doe created.",
        )
        self.assertEqual(log.entity_type, "occupant")
        self.assertEqual(log.action, "create")
        self.assertIsNotNone(log.timestamp)
        self.assertEqual(str(log.actor), "admin")

    def test_audit_log_str(self):
        user = User.objects.create_user(
            username="admin", password="pass123", is_superuser=True
        )
        log = AuditLog.objects.create(
            actor=user,
            entity_type=AuditLog.EntityType.OCCUPANT,
            entity_id=42,
            action=AuditLog.Action.CREATE,
            description="test",
        )
        self.assertIn("Create", str(log))
        self.assertIn("Occupant", str(log))


class AuditServiceTests(TestCase):

    def setUp(self):
        self.actor = User.objects.create_user(
            username="admin", password="pass123", is_superuser=True
        )

    def test_log_creates_entry(self):
        log = AuditService.log(
            actor=self.actor,
            entity_type=AuditLog.EntityType.OCCUPANT,
            entity_id=1,
            action=AuditLog.Action.CREATE,
            description="Occupant created.",
        )
        self.assertIsNotNone(log.id)
        self.assertEqual(log.actor, self.actor)

    def test_list_logs_pagination(self):
        for i in range(5):
            AuditService.log(
                actor=self.actor,
                entity_type=AuditLog.EntityType.OCCUPANT,
                entity_id=i,
                action=AuditLog.Action.CREATE,
                description=f"Log {i}",
            )
        result = AuditService.list_logs(page=1, page_size=2)
        self.assertEqual(result["count"], 5)
        self.assertEqual(len(result["results"]), 2)
        self.assertEqual(result["total_pages"], 3)

    def test_list_logs_filter_by_entity_type(self):
        AuditService.log(
            actor=self.actor,
            entity_type=AuditLog.EntityType.OCCUPANT,
            entity_id=1,
            action=AuditLog.Action.CREATE,
            description="Occupant log",
        )
        AuditService.log(
            actor=self.actor,
            entity_type=AuditLog.EntityType.PAYMENT,
            entity_id=1,
            action=AuditLog.Action.RECORD_PAYMENT,
            description="Payment log",
        )
        result = AuditService.list_logs(entity_type="occupant")
        self.assertEqual(result["count"], 1)

    def test_list_logs_filter_by_action(self):
        AuditService.log(
            actor=self.actor,
            entity_type=AuditLog.EntityType.OCCUPANT,
            entity_id=1,
            action=AuditLog.Action.CREATE,
            description="Create",
        )
        AuditService.log(
            actor=self.actor,
            entity_type=AuditLog.EntityType.OCCUPANT,
            entity_id=2,
            action=AuditLog.Action.ARCHIVE,
            description="Archive",
        )
        result = AuditService.list_logs(action="archive")
        self.assertEqual(result["count"], 1)

    def test_get_log_returns_entry(self):
        log = AuditService.log(
            actor=self.actor,
            entity_type=AuditLog.EntityType.OCCUPANT,
            entity_id=1,
            action=AuditLog.Action.CREATE,
            description="test",
        )
        fetched = AuditService.get_log(log.id)
        self.assertEqual(fetched.id, log.id)

    def test_get_log_not_found(self):
        from apps.core.exceptions import NotFoundError
        with self.assertRaises(NotFoundError):
            AuditService.get_log(99999)


class AuditAPITests(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.superuser = User.objects.create_user(
            username="super", password="pass123", is_superuser=True
        )
        self.super_token = Token.objects.create(user=self.superuser)
        self.normal_user = User.objects.create_user(
            username="normal", password="pass123", is_staff=True
        )
        self.normal_token = Token.objects.create(user=self.normal_user)
        self.list_url = "/api/audit/"

        for i in range(3):
            AuditService.log(
                actor=self.superuser,
                entity_type=AuditLog.EntityType.OCCUPANT,
                entity_id=i,
                action=AuditLog.Action.CREATE,
                description=f"Log {i}",
            )

    def test_list_requires_auth(self):
        self.client.credentials()
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_list_requires_superuser(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.normal_token.key}")
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_list_returns_logs(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.super_token.key}")
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 3)

    def test_list_pagination(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.super_token.key}")
        response = self.client.get(f"{self.list_url}?page=1&page_size=1")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["total_pages"], 3)

    def test_filter_by_entity_type(self):
        AuditService.log(
            actor=self.superuser,
            entity_type=AuditLog.EntityType.PAYMENT,
            entity_id=1,
            action=AuditLog.Action.RECORD_PAYMENT,
            description="Payment log",
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.super_token.key}")
        response = self.client.get(f"{self.list_url}?entity_type=payment")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)

    def test_detail_returns_log(self):
        log = AuditService.log(
            actor=self.superuser,
            entity_type=AuditLog.EntityType.OCCUPANT,
            entity_id=10,
            action=AuditLog.Action.CREATE,
            description="Detail test",
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.super_token.key}")
        response = self.client.get(f"{self.list_url}{log.id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["description"], "Detail test")

    def test_entity_types_endpoint(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.super_token.key}")
        response = self.client.get(f"{self.list_url}entity-types/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(len(response.data) > 0)

    def test_actions_endpoint(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.super_token.key}")
        response = self.client.get(f"{self.list_url}actions/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(len(response.data) > 0)


class AuditIntegrationTests(TestCase):
    """Verify audit logs are created when actions happen via API."""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="admin", password="pass123", is_staff=True
        )
        group, _ = Group.objects.get_or_create(name="Property Manager")
        self.user.groups.add(group)
        self.token = Token.objects.create(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")

    def test_occupant_create_logs_audit(self):
        response = self.client.post("/api/occupants/", {
            "first_name": "John",
            "last_name": "Smith",
            "email": "john@example.com",
            "phone": "+256700111333",
            "student_id_number": "STU999",
            "national_id": "NAT999",
        }, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        logs = AuditLog.objects.filter(entity_type="occupant", action="create")
        self.assertEqual(logs.count(), 1)
        self.assertIn("John Smith", logs.first().description)

    def test_occupant_archive_logs_audit(self):
        student = Student.objects.create(
            first_name="Jane", last_name="Doe",
            email="jane@test.com", phone="+256700111444",
            student_id_number="STU001", national_id="NAT001",
        )
        response = self.client.post(f"/api/occupants/{student.id}/archive/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        logs = AuditLog.objects.filter(
            entity_type="occupant", entity_id=student.id, action="archive"
        )
        self.assertEqual(logs.count(), 1)

    def test_occupancy_assign_logs_audit(self):
        from apps.properties.models import Property
        from apps.sections.models import Section
        from apps.units.models import Unit

        prop = Property.objects.create(name="Test Property", code="TP")
        section = Section.objects.create(name="Test Section", property=prop)
        unit = Unit.objects.create(
            name="A1", capacity=2, section=section,
            semester_price=1000, monthly_price=500,
        )
        student = Student.objects.create(
            first_name="Test", last_name="Student",
            email="test@test.com", phone="+256700111555",
            student_id_number="STU002", national_id="NAT002",
        )

        response = self.client.post("/api/occupancy/", {
            "student": student.id,
            "unit": unit.id,
            "start_date": date.today().isoformat(),
            "billing_mode": "semester",
        }, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        logs = AuditLog.objects.filter(entity_type="occupancy", action="assign")
        self.assertEqual(logs.count(), 1)

    def test_payment_record_logs_audit(self):
        from apps.properties.models import Property
        from apps.sections.models import Section
        from apps.units.models import Unit
        from apps.occupancy.models import Occupancy

        prop = Property.objects.create(name="Prop P", code="PP")
        section = Section.objects.create(name="Sec S", property=prop)
        unit = Unit.objects.create(
            name="B1", capacity=2, section=section,
            semester_price=1000, monthly_price=500,
        )
        student = Student.objects.create(
            first_name="Pay", last_name="Test",
            email="pay@test.com", phone="+256700111666",
            student_id_number="STU003", national_id="NAT003",
        )
        Occupancy.objects.create(
            student=student, unit=unit, start_date=date.today(),
            billing_mode="monthly", agreed_price=500,
        )

        response = self.client.post("/api/payments/", {
            "student": student.id,
            "amount": "500.00",
            "payment_date": date.today().isoformat(),
            "payment_method": "cash",
        }, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        logs = AuditLog.objects.filter(entity_type="payment", action="record_payment")
        self.assertEqual(logs.count(), 1)
