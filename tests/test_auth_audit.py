from django.contrib.auth.hashers import make_password
from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.models import Role, User
from apps.accounts.role_constants import Roles
from apps.accounts.views.auth import REFRESH_COOKIE_NAME
from apps.audit.models import AuditLog


class AuthAuditLogTests(TestCase):
    def setUp(self):
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

    def test_logout_all_records_user_object_metadata(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.post("/api/auth/logout-all/", {}, format="json")
        self.assertEqual(response.status_code, 200)

        logout_log = AuditLog.objects.get(action="LOGOUT")
        self.assert_user_object_metadata(logout_log)
