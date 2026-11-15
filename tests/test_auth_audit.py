from datetime import timedelta

from django.contrib.auth.hashers import make_password
from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import Role, User
from apps.accounts.role_constants import Roles
from apps.accounts.views.auth import REFRESH_COOKIE_NAME
from apps.audit.models import AuditLog


class AuthAuditLogTests(TestCase):
    def setUp(self):
        cache.clear()
        role = Role.objects.create(name=Roles.SYSTEM_ADMIN)
        self.user = User.objects.create(
            username="audit-user",
            email="audit-user@example.test",
            password_hash=make_password("correct-password"),
            role_id=role,
            is_active=True,
        )
        self.client = APIClient()

    def assert_user_object_metadata(self, audit_log):
        self.assertEqual(audit_log.app_label, "accounts")
        self.assertEqual(audit_log.model_name, "User")
        self.assertEqual(audit_log.object_id, str(self.user.pk))
        self.assertEqual(audit_log.user_id, str(self.user.pk))
        self.assertEqual(audit_log.user_name, self.user.username)

    def test_login_and_logout_record_user_object_metadata(self):
        login_response = self.client.post(
            "/api/auth/login/",
            {"username": self.user.username, "password": "correct-password"},
            format="json",
        )
        self.assertEqual(login_response.status_code, 200)

        login_log = AuditLog.objects.get(action="LOGIN")
        self.assert_user_object_metadata(login_log)

        self.client.cookies[REFRESH_COOKIE_NAME] = login_response.cookies[
            REFRESH_COOKIE_NAME
        ].value
        logout_response = self.client.post("/api/auth/logout/", {}, format="json")
        self.assertEqual(logout_response.status_code, 200)

        logout_log = AuditLog.objects.get(action="LOGOUT")
        self.assert_user_object_metadata(logout_log)

    def test_successful_login_updates_last_login(self):
        before_login = timezone.now()
        response = self.client.post(
            "/api/auth/login/",
            {"username": self.user.username, "password": "correct-password"},
            format="json",
        )
        after_login = timezone.now()

        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertIsNotNone(self.user.last_login)
        self.assertGreaterEqual(self.user.last_login, before_login)
        self.assertLessEqual(self.user.last_login, after_login)

    def test_repeated_successful_login_updates_last_login_to_newer_timestamp(self):
        first_response = self.client.post(
            "/api/auth/login/",
            {"username": self.user.username, "password": "correct-password"},
            format="json",
        )
        self.assertEqual(first_response.status_code, 200)
        self.user.refresh_from_db()
        first_login = self.user.last_login
        self.assertIsNotNone(first_login)

        self.user.last_login = first_login - timedelta(seconds=1)
        self.user.save(update_fields=["last_login"])
        second_response = self.client.post(
            "/api/auth/login/",
            {"username": self.user.username, "password": "correct-password"},
            format="json",
        )

        self.assertEqual(second_response.status_code, 200)
        self.user.refresh_from_db()
        self.assertGreater(self.user.last_login, first_login)

    def test_incorrect_password_does_not_update_last_login(self):
        original_last_login = timezone.now() - timedelta(days=1)
        self.user.last_login = original_last_login
        self.user.save(update_fields=["last_login"])

        response = self.client.post(
            "/api/auth/login/",
            {"username": self.user.username, "password": "incorrect-password"},
            format="json",
        )

        self.assertEqual(response.status_code, 401)
        self.user.refresh_from_db()
        self.assertEqual(self.user.last_login, original_last_login)

    def test_invalid_username_does_not_update_last_login(self):
        original_last_login = timezone.now() - timedelta(days=1)
        self.user.last_login = original_last_login
        self.user.save(update_fields=["last_login"])

        response = self.client.post(
            "/api/auth/login/",
            {"username": "missing-user", "password": "correct-password"},
            format="json",
        )

        self.assertEqual(response.status_code, 401)
        self.user.refresh_from_db()
        self.assertEqual(self.user.last_login, original_last_login)

    def test_inactive_user_login_does_not_update_last_login(self):
        original_last_login = timezone.now() - timedelta(days=1)
        self.user.is_active = False
        self.user.last_login = original_last_login
        self.user.save(update_fields=["is_active", "last_login"])

        response = self.client.post(
            "/api/auth/login/",
            {"username": self.user.username, "password": "correct-password"},
            format="json",
        )

        self.assertEqual(response.status_code, 401)
        self.user.refresh_from_db()
        self.assertEqual(self.user.last_login, original_last_login)

    def test_token_refresh_does_not_update_last_login(self):
        login_response = self.client.post(
            "/api/auth/login/",
            {"username": self.user.username, "password": "correct-password"},
            format="json",
        )
        self.assertEqual(login_response.status_code, 200)
        self.user.refresh_from_db()
        login_time = self.user.last_login

        self.client.cookies[REFRESH_COOKIE_NAME] = login_response.cookies[
            REFRESH_COOKIE_NAME
        ].value
        refresh_response = self.client.post("/api/auth/refresh/", {}, format="json")

        self.assertEqual(refresh_response.status_code, 200)
        self.user.refresh_from_db()
        self.assertEqual(self.user.last_login, login_time)

    def test_logout_all_records_user_object_metadata(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.post("/api/auth/logout-all/", {}, format="json")
        self.assertEqual(response.status_code, 200)

        logout_log = AuditLog.objects.get(action="LOGOUT")
        self.assert_user_object_metadata(logout_log)
