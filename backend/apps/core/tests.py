from django.test import TestCase
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from apps.accounts.models import User


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
