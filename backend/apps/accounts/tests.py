from django.contrib.auth.models import Group
from django.test import TestCase
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from .models import User


class AuthFlowTests(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.login_url = "/api/auth/login/"
        self.logout_url = "/api/auth/logout/"
        self.me_url = "/api/auth/me/"
        self.password = "testpass123"
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password=self.password,
            first_name="Test",
            last_name="User",
        )

    # --- Login ---

    def test_login_success(self):
        response = self.client.post(
            self.login_url,
            {"username": "testuser", "password": self.password},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("token", response.data)
        self.assertIn("user", response.data)
        self.assertEqual(response.data["user"]["username"], "testuser")
        self.assertEqual(response.data["user"]["email"], "test@example.com")

    def test_login_invalid_credentials(self):
        response = self.client.post(
            self.login_url,
            {"username": "testuser", "password": "wrongpassword"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("non_field_errors", response.data)

    def test_login_missing_fields(self):
        response = self.client.post(
            self.login_url,
            {"username": "testuser"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("password", response.data)

    def test_login_inactive_user(self):
        self.user.is_active = False
        self.user.save()
        response = self.client.post(
            self.login_url,
            {"username": "testuser", "password": self.password},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    # --- Logout ---

    def test_logout_success(self):
        token = Token.objects.create(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
        response = self.client.post(self.logout_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(Token.objects.filter(key=token.key).exists())

    def test_logout_unauthenticated(self):
        response = self.client.post(self.logout_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    # --- Me ---

    def test_me_authenticated(self):
        token = Token.objects.create(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
        response = self.client.get(self.me_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["username"], "testuser")
        self.assertEqual(response.data["email"], "test@example.com")
        self.assertIn("groups", response.data)

    def test_me_unauthenticated(self):
        response = self.client.get(self.me_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    # --- Token reuse ---

    def test_login_returns_existing_token(self):
        token = Token.objects.create(user=self.user)
        response = self.client.post(
            self.login_url,
            {"username": "testuser", "password": self.password},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["token"], token.key)


class PermissionTests(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.me_url = "/api/auth/me/"
        self.admin = User.objects.create_superuser(
            username="admin", password="admin123"
        )
        self.regular = User.objects.create_user(
            username="regular", password="pass123"
        )
        self.manager_group = Group.objects.get(name="Property Manager")
        self.manager = User.objects.create_user(
            username="manager", password="pass123"
        )
        self.manager.groups.add(self.manager_group)

    def test_superuser_has_staff_flag(self):
        self.assertTrue(self.admin.is_staff)
        self.assertTrue(self.admin.is_superuser)

    def test_regular_user_not_staff(self):
        self.assertFalse(self.regular.is_staff)

    def test_property_manager_group_exists(self):
        self.assertIsNotNone(self.manager_group)
        self.assertIn(self.manager_group, self.manager.groups.all())

    def test_authenticated_user_can_access_me(self):
        token = Token.objects.create(user=self.regular)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
        response = self.client.get(self.me_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class PermissionClassTests(TestCase):
    """Test that the permission classes can be imported and instantiated."""

    def test_core_permissions_importable(self):
        from apps.core.permissions import (
            IsSuperAdmin,
            IsPropertyManager,
            IsStaff,
            IsStaffOrSuperAdmin,
            HasGroupPermission,
        )
        for cls in [IsSuperAdmin, IsPropertyManager, IsStaff, IsStaffOrSuperAdmin, HasGroupPermission]:
            instance = cls()
            self.assertIsNotNone(instance)
