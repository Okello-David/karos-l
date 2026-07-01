from django.test import TestCase
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from apps.accounts.models import User

from .models import Student


class StudentAPITests(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="admin", password="pass123", is_staff=True
        )
        self.token = Token.objects.create(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")
        self.list_url = "/api/occupants/"
        self.student_data = {
            "first_name": "Jane",
            "last_name": "Doe",
            "email": "jane@example.com",
            "phone": "+256700111222",
            "student_id_number": "STU001",
            "national_id": "NAT001",
        }

    def _create_student(self, **overrides):
        data = {**self.student_data, **overrides}
        return self.client.post(self.list_url, data, format="json")

    # --- Create ---

    def test_create_student_success(self):
        response = self._create_student()
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["first_name"], "Jane")
        self.assertEqual(response.data["last_name"], "Doe")
        self.assertEqual(response.data["email"], "jane@example.com")
        self.assertEqual(response.data["phone"], "+256700111222")
        self.assertEqual(response.data["student_id_number"], "STU001")
        self.assertEqual(response.data["national_id"], "NAT001")
        self.assertTrue(response.data["is_active"])
        self.assertIn("full_name", response.data)
        self.assertEqual(response.data["full_name"], "Jane Doe")

    def test_create_student_requires_first_name(self):
        response = self._create_student(first_name="")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("first_name", response.data)

    def test_create_student_requires_last_name(self):
        response = self._create_student(last_name="")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("last_name", response.data)

    def test_create_student_duplicate_email(self):
        self._create_student()
        response = self._create_student(
            first_name="John",
            last_name="Smith",
            student_id_number="STU002",
            national_id="NAT002",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_student_optional_fields_blank(self):
        response = self._create_student(
            email="",
            phone="",
            student_id_number="",
            national_id="",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIsNone(response.data["email"])
        self.assertEqual(response.data["phone"], "")
        self.assertIsNone(response.data["student_id_number"])
        self.assertIsNone(response.data["national_id"])

    def test_create_second_student_with_blank_optional_fields_does_not_crash(self):
        first = self._create_student(
            first_name="Jane",
            last_name="Doe",
            email="",
            student_id_number="",
            national_id="",
        )
        self.assertEqual(first.status_code, status.HTTP_201_CREATED)
        second = self._create_student(
            first_name="John",
            last_name="Smith",
            email="",
            student_id_number="",
            national_id="",
        )
        self.assertEqual(second.status_code, status.HTTP_201_CREATED)
        self.assertIsNone(second.data["email"])
        self.assertIsNone(second.data["student_id_number"])
        self.assertIsNone(second.data["national_id"])

    def test_create_student_unauthenticated(self):
        self.client.credentials()
        response = self._create_student()
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    # --- List ---

    def test_list_students_empty(self):
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 0)
        self.assertEqual(response.data["results"], [])

    def test_list_students_pagination(self):
        for i in range(25):
            self._create_student(
                first_name=f"Student{i}",
                last_name="Test",
                email=f"student{i}@example.com",
                student_id_number=f"STU{i:03d}",
                national_id=f"NAT{i:03d}",
            )
        response = self.client.get(self.list_url, {"page_size": 10})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 25)
        self.assertEqual(len(response.data["results"]), 10)
        self.assertEqual(response.data["total_pages"], 3)

    # --- Search ---

    def test_search_by_first_name(self):
        self._create_student(first_name="Alice", last_name="Smith", email="alice@example.com", student_id_number="STU010", national_id="NAT010")
        self._create_student(first_name="Bob", last_name="Jones", email="bob@example.com", student_id_number="STU011", national_id="NAT011")
        response = self.client.get(self.list_url, {"search": "Alice"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["first_name"], "Alice")

    def test_search_by_last_name(self):
        self._create_student(first_name="Alice", last_name="Smith", email="alice@example.com", student_id_number="STU010", national_id="NAT010")
        self._create_student(first_name="Bob", last_name="Jones", email="bob@example.com", student_id_number="STU011", national_id="NAT011")
        response = self.client.get(self.list_url, {"search": "Jones"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["last_name"], "Jones")

    def test_search_by_phone(self):
        self._create_student(first_name="Alice", last_name="Smith", email="alice@example.com", phone="+256700000001", student_id_number="STU010", national_id="NAT010")
        response = self.client.get(self.list_url, {"search": "700000001"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)

    def test_search_by_student_id(self):
        self._create_student(first_name="Alice", last_name="Smith", email="alice@example.com", student_id_number="STU010", national_id="NAT010")
        response = self.client.get(self.list_url, {"search": "STU010"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)

    def test_search_by_national_id(self):
        self._create_student(first_name="Alice", last_name="Smith", email="alice@example.com", student_id_number="STU010", national_id="NAT010")
        response = self.client.get(self.list_url, {"search": "NAT010"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)

    def test_search_no_results(self):
        response = self.client.get(self.list_url, {"search": "NonexistentPerson"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 0)

    # --- Filter by status ---

    def test_filter_active(self):
        self._create_student(first_name="Alice", last_name="Smith", email="alice@example.com", student_id_number="STU010", national_id="NAT010")
        student = Student.objects.get(student_id_number="STU010")
        student.is_active = False
        student.save()
        response = self.client.get(self.list_url, {"status": "active"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 0)

    def test_filter_archived(self):
        self._create_student(first_name="Alice", last_name="Smith", email="alice@example.com", student_id_number="STU010", national_id="NAT010")
        student = Student.objects.get(student_id_number="STU010")
        student.is_active = False
        student.save()
        response = self.client.get(self.list_url, {"status": "archived"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)

    # --- Retrieve ---

    def test_retrieve_student(self):
        create_resp = self._create_student()
        student_id = create_resp.data["id"]
        response = self.client.get(f"{self.list_url}{student_id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["first_name"], "Jane")

    def test_retrieve_nonexistent_student(self):
        response = self.client.get(f"{self.list_url}99999/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    # --- Update ---

    def test_update_student(self):
        create_resp = self._create_student()
        student_id = create_resp.data["id"]
        response = self.client.put(
            f"{self.list_url}{student_id}/",
            {"first_name": "Jane", "last_name": "Smith", "email": "jane.smith@example.com", "phone": "", "student_id_number": "STU001", "national_id": "NAT001"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["last_name"], "Smith")
        self.assertEqual(response.data["email"], "jane.smith@example.com")

    def test_partial_update_student(self):
        create_resp = self._create_student()
        student_id = create_resp.data["id"]
        response = self.client.patch(
            f"{self.list_url}{student_id}/",
            {"phone": "+256700333444"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["phone"], "+256700333444")

    # --- Archive ---

    def test_archive_student(self):
        create_resp = self._create_student()
        student_id = create_resp.data["id"]
        self.assertTrue(create_resp.data["is_active"])
        response = self.client.post(f"{self.list_url}{student_id}/archive/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["detail"], "Occupant archived successfully.")
        student = Student.objects.get(id=student_id)
        self.assertFalse(student.is_active)

    def test_archive_already_archived_student(self):
        create_resp = self._create_student()
        student_id = create_resp.data["id"]
        self.client.post(f"{self.list_url}{student_id}/archive/")
        response = self.client.post(f"{self.list_url}{student_id}/archive/")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["detail"], "This occupant is already archived.")

    def test_archive_preserves_record(self):
        create_resp = self._create_student()
        student_id = create_resp.data["id"]
        self.client.post(f"{self.list_url}{student_id}/archive/")
        student = Student.objects.get(id=student_id)
        self.assertEqual(student.first_name, "Jane")
        self.assertEqual(student.last_name, "Doe")
        self.assertIsNotNone(student.created_at)
        self.assertIsNotNone(student.updated_at)
