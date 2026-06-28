import json
import os

from django.test import TestCase
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from apps.accounts.models import User

from .models import Backup
from .services import BackupService, ExportService


class BackupModelTests(TestCase):

    def test_create_backup_model(self):
        user = User.objects.create_user(
            username="admin", password="pass123", is_superuser=True
        )
        backup = Backup.objects.create(
            created_by=user,
            status=Backup.Status.COMPLETED,
            file_path="/tmp/test.json",
            file_size=1024,
            metadata={"total_records": 10},
        )
        self.assertEqual(str(backup.status), "completed")
        self.assertIn("Backup", str(backup))

    def test_backup_default_pending(self):
        backup = Backup.objects.create()
        self.assertEqual(backup.status, Backup.Status.PENDING)


class BackupServiceTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username="admin", password="pass123", is_superuser=True
        )

    def test_create_backup_success(self):
        backup = BackupService.create_backup(user=self.user, notes="test backup")
        self.assertEqual(backup.status, Backup.Status.COMPLETED)
        self.assertIsNotNone(backup.file_path)
        self.assertIsNotNone(backup.file_size)
        self.assertGreater(backup.file_size, 0)
        self.assertIn("record_counts", backup.metadata)
        self.assertIn("total_records", backup.metadata)
        self.assertTrue(os.path.exists(backup.file_path))

    def test_create_backup_creates_file(self):
        backup = BackupService.create_backup(user=self.user)
        self.assertTrue(os.path.exists(backup.file_path))

        with open(backup.file_path) as f:
            data = json.load(f)

        self.assertIn("backup_id", data)
        self.assertIn("metadata", data)
        self.assertIn("data", data)

    def test_list_backups(self):
        BackupService.create_backup(user=self.user)
        BackupService.create_backup(user=self.user)
        result = BackupService.list_backups(page=1, page_size=10)
        self.assertEqual(result["count"], 2)

    def test_list_backups_pagination(self):
        for _ in range(5):
            BackupService.create_backup(user=self.user)
        result = BackupService.list_backups(page=1, page_size=2)
        self.assertEqual(len(result["results"]), 2)
        self.assertEqual(result["total_pages"], 3)

    def test_get_backup(self):
        backup = BackupService.create_backup(user=self.user)
        fetched = BackupService.get_backup(backup.id)
        self.assertEqual(fetched.id, backup.id)

    def test_get_backup_not_found(self):
        from apps.core.exceptions import NotFoundError
        with self.assertRaises(NotFoundError):
            BackupService.get_backup(99999)

    def test_validate_backup_success(self):
        backup = BackupService.create_backup(user=self.user)
        data = BackupService.validate_backup(backup)
        self.assertIn("data", data)

    def test_validate_pending_backup_raises(self):
        backup = Backup.objects.create(status=Backup.Status.PENDING)
        from apps.core.exceptions import ConflictError
        with self.assertRaises(ConflictError):
            BackupService.validate_backup(backup)

    def test_restore_backup(self):
        from apps.occupants.models import Student

        # Create some data first
        Student.objects.create(
            first_name="Original", last_name="Student",
            email="orig@test.com", phone="+256700111000",
            student_id_number="ORI001", national_id="ORI001",
        )

        backup = BackupService.create_backup(user=self.user)

        # Modify and then restore
        Student.objects.filter(student_id_number="ORI001").update(first_name="Modified")

        restored_counts = BackupService.restore_backup(backup)
        self.assertGreater(restored_counts["occupants.Student"], 0)

        student = Student.objects.get(student_id_number="ORI001")
        self.assertEqual(student.first_name, "Original")


class ExportServiceTests(TestCase):

    def setUp(self):
        from apps.occupants.models import Student
        self.student = Student.objects.create(
            first_name="Export", last_name="Test",
            email="export@test.com", phone="+256700111001",
            student_id_number="EXP001", national_id="EXP001",
        )

    def test_export_occupants_csv(self):
        content, filename, content_type = ExportService.export_occupants(file_format="csv")
        self.assertIn(".csv", filename)
        self.assertIn("Export", content)
        self.assertIn("Test", content)

    def test_export_occupants_xlsx(self):
        content, filename, content_type = ExportService.export_occupants(file_format="xlsx")
        self.assertIn(".xlsx", filename)
        self.assertGreater(len(content), 0)

    def test_export_occupancies_csv(self):
        content, filename, content_type = ExportService.export_occupancies(file_format="csv")
        self.assertIn(".csv", filename)

    def test_export_payments_csv(self):
        content, filename, content_type = ExportService.export_payments(file_format="csv")
        self.assertIn(".csv", filename)

    def test_export_receipts_csv(self):
        content, filename, content_type = ExportService.export_receipts(file_format="csv")
        self.assertIn(".csv", filename)

    def test_invalid_format(self):
        with self.assertRaises(ValueError):
            ExportService.export_occupants(file_format="pdf")


class BackupAPITests(TestCase):

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
        self.list_url = "/api/backups/"

    def test_list_requires_auth(self):
        self.client.credentials()
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_list_requires_superuser(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.normal_token.key}")
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_create_backup_via_api(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.super_token.key}")
        response = self.client.post(self.list_url, {"notes": "API test"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["status"], "completed")
        self.assertIsNotNone(response.data["file_size"])
        self.assertIn("record_counts", response.data["metadata"])

    def test_list_backups_via_api(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.super_token.key}")
        self.client.post(self.list_url, format="json")
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)

    def test_retrieve_backup_via_api(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.super_token.key}")
        create_resp = self.client.post(self.list_url, format="json")
        backup_id = create_resp.data["id"]
        response = self.client.get(f"{self.list_url}{backup_id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], backup_id)

    def test_validate_backup_via_api(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.super_token.key}")
        create_resp = self.client.post(self.list_url, format="json")
        backup_id = create_resp.data["id"]
        response = self.client.get(f"{self.list_url}{backup_id}/validate/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["valid"])

    def test_restore_backup_via_api(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.super_token.key}")
        create_resp = self.client.post(self.list_url, format="json")
        backup_id = create_resp.data["id"]
        response = self.client.post(
            f"{self.list_url}{backup_id}/restore/",
            {"backup_id": backup_id, "confirm": True},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("restored_counts", response.data)

    def test_restore_without_confirm_raises_error(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.super_token.key}")
        create_resp = self.client.post(self.list_url, format="json")
        backup_id = create_resp.data["id"]
        response = self.client.post(
            f"{self.list_url}{backup_id}/restore/",
            {"backup_id": backup_id, "confirm": False},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class ExportAPITests(TestCase):

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
        self.export_url = "/api/backups/export/"

    def test_export_requires_auth(self):
        self.client.credentials()
        response = self.client.get(f"{self.export_url}?entity=occupants&file_format=csv")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_export_requires_superuser(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.normal_token.key}")
        response = self.client.get(f"{self.export_url}?entity=occupants&file_format=csv")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_export_occupants_csv(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.super_token.key}")
        response = self.client.get(f"{self.export_url}?entity=occupants&file_format=csv")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response["Content-Type"], "text/csv")
        self.assertIn("occupants.csv", response["Content-Disposition"])

    def test_export_occupants_xlsx(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.super_token.key}")
        response = self.client.get(f"{self.export_url}?entity=occupants&file_format=xlsx")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("occupants.xlsx", response["Content-Disposition"])

    def test_export_invalid_entity(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.super_token.key}")
        response = self.client.get(f"{self.export_url}?entity=invalid&file_format=csv")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_export_invalid_format(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.super_token.key}")
        response = self.client.get(f"{self.export_url}?entity=occupants&file_format=pdf")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
