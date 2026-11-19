from datetime import timedelta
import time

from django.contrib.auth.hashers import make_password
from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import ImpersonationSession, Role, User
from apps.accounts.role_constants import Roles
from apps.audit.models import AuditLog


class ImpersonationBackendTests(TestCase):
    def setUp(self):
        cache.clear()

        # Roles
        self.role_sys_admin = Role.objects.create(name=Roles.SYSTEM_ADMIN)
        self.role_dept_admin = Role.objects.create(name=Roles.SERVICE_DEPT_ADMIN)
        self.role_dept_staff = Role.objects.create(name=Roles.SERVICE_DEPT_STAFF)
        self.role_student = Role.objects.create(name=Roles.STUDENT)

        # Users
        self.admin = User.objects.create(
            username="sysadmin",
            email="sysadmin@example.test",
            password_hash=make_password("password123"),
            role_id=self.role_sys_admin,
            is_active=True,
        )
        self.other_admin = User.objects.create(
            username="otheradmin",
            email="otheradmin@example.test",
            password_hash=make_password("password123"),
            role_id=self.role_sys_admin,
            is_active=True,
        )
        self.student = User.objects.create(
            username="student1",
            email="student1@example.test",
            password_hash=make_password("password123"),
            role_id=self.role_student,
            is_active=True,
        )
        self.dept_admin = User.objects.create(
            username="deptadmin",
            email="deptadmin@example.test",
            password_hash=make_password("password123"),
            role_id=self.role_dept_admin,
            is_active=True,
        )
        self.dept_staff = User.objects.create(
            username="deptstaff",
            email="deptstaff@example.test",
            password_hash=make_password("password123"),
            role_id=self.role_dept_staff,
            is_active=True,
        )
        self.inactive_user = User.objects.create(
            username="inactiveuser",
            email="inactive@example.test",
            password_hash=make_password("password123"),
            role_id=self.role_student,
            is_active=False,
        )

        self.client = APIClient()

    def _login_and_get_token(self, user):
        res = self.client.post(
            "/api/auth/login/",
            {"username": user.username, "password": "password123"},
            format="json",
        )
        self.assertEqual(res.status_code, 200)
        return res.data["access"]

    def _auth_header(self, token):
        return {"HTTP_AUTHORIZATION": f"Bearer {token}"}

    def test_system_admin_can_start_impersonation_for_student(self):
        admin_token = self._login_and_get_token(self.admin)
        res = self.client.post(
            "/api/auth/impersonate/",
            {"target_user_id": self.student.id, "reason": "Investigating student issue"},
            format="json",
            **self._auth_header(admin_token),
        )
        self.assertEqual(res.status_code, 200)
        self.assertIn("access", res.data)
        self.assertIn("session_id", res.data)
        self.assertEqual(res.data["target"]["id"], self.student.id)
        self.assertEqual(res.data["target"]["role_name"], Roles.STUDENT)

        # Check DB session
        session = ImpersonationSession.objects.get(id=res.data["session_id"])
        self.assertTrue(session.is_active)
        self.assertEqual(session.admin_user_id, self.admin.id)
        self.assertEqual(session.target_user_id, self.student.id)

        # Check Audit log
        log = AuditLog.objects.filter(action="IMPERSONATE_START").first()
        self.assertIsNotNone(log)
        self.assertEqual(log.user_id, str(self.admin.id))
        self.assertEqual(log.changes["target_user_id"], self.student.id)

    def test_system_admin_can_start_impersonation_for_dept_roles(self):
        admin_token = self._login_and_get_token(self.admin)

        # Dept Admin
        res_admin = self.client.post(
            "/api/auth/impersonate/",
            {"target_user_id": self.dept_admin.id, "reason": "Support dept admin"},
            format="json",
            **self._auth_header(admin_token),
        )
        self.assertEqual(res_admin.status_code, 200)

        # Dept Staff
        res_staff = self.client.post(
            "/api/auth/impersonate/",
            {"target_user_id": self.dept_staff.id, "reason": "Support dept staff"},
            format="json",
            **self._auth_header(admin_token),
        )
        self.assertEqual(res_staff.status_code, 200)

    def test_system_admin_cannot_impersonate_another_system_admin(self):
        admin_token = self._login_and_get_token(self.admin)
        res = self.client.post(
            "/api/auth/impersonate/",
            {"target_user_id": self.other_admin.id, "reason": "Invalid attempt"},
            format="json",
            **self._auth_header(admin_token),
        )
        self.assertEqual(res.status_code, 403)
        self.assertIn("Cannot impersonate", res.data["detail"])

    def test_system_admin_cannot_impersonate_self(self):
        admin_token = self._login_and_get_token(self.admin)
        res = self.client.post(
            "/api/auth/impersonate/",
            {"target_user_id": self.admin.id, "reason": "Invalid self attempt"},
            format="json",
            **self._auth_header(admin_token),
        )
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.data["detail"], "You cannot impersonate yourself.")

    def test_cannot_impersonate_inactive_user(self):
        admin_token = self._login_and_get_token(self.admin)
        res = self.client.post(
            "/api/auth/impersonate/",
            {"target_user_id": self.inactive_user.id, "reason": "Attempt on inactive"},
            format="json",
            **self._auth_header(admin_token),
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn("inactive", res.data["detail"])

    def test_non_system_admin_cannot_start_impersonation(self):
        student_token = self._login_and_get_token(self.student)
        res = self.client.post(
            "/api/auth/impersonate/",
            {"target_user_id": self.dept_staff.id, "reason": "Unauthorized attempt"},
            format="json",
            **self._auth_header(student_token),
        )
        self.assertEqual(res.status_code, 403)

    def test_reason_is_mandatory(self):
        admin_token = self._login_and_get_token(self.admin)
        res = self.client.post(
            "/api/auth/impersonate/",
            {"target_user_id": self.student.id, "reason": "   "},
            format="json",
            **self._auth_header(admin_token),
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn("reason", res.data)

    def test_new_impersonation_supersedes_previous_session(self):
        admin_token = self._login_and_get_token(self.admin)
        # First session
        res1 = self.client.post(
            "/api/auth/impersonate/",
            {"target_user_id": self.student.id, "reason": "First session"},
            format="json",
            **self._auth_header(admin_token),
        )
        self.assertEqual(res1.status_code, 200)
        sess1_id = res1.data["session_id"]

        # Second session
        res2 = self.client.post(
            "/api/auth/impersonate/",
            {"target_user_id": self.dept_staff.id, "reason": "Second session"},
            format="json",
            **self._auth_header(admin_token),
        )
        self.assertEqual(res2.status_code, 200)
        sess2_id = res2.data["session_id"]

        # Check DB
        sess1 = ImpersonationSession.objects.get(id=sess1_id)
        sess2 = ImpersonationSession.objects.get(id=sess2_id)
        self.assertFalse(sess1.is_active)
        self.assertIsNotNone(sess1.ended_at)
        self.assertTrue(sess2.is_active)

    def test_impersonation_exit_closes_session_and_audits(self):
        admin_token = self._login_and_get_token(self.admin)
        start_res = self.client.post(
            "/api/auth/impersonate/",
            {"target_user_id": self.student.id, "reason": "Testing exit"},
            format="json",
            **self._auth_header(admin_token),
        )
        impersonation_token = start_res.data["access"]
        session_id = start_res.data["session_id"]

        # Exit
        exit_res = self.client.post(
            "/api/auth/impersonate/exit/",
            {},
            format="json",
            **self._auth_header(impersonation_token),
        )
        self.assertEqual(exit_res.status_code, 200)

        # Verify DB session is closed
        sess = ImpersonationSession.objects.get(id=session_id)
        self.assertFalse(sess.is_active)
        self.assertIsNotNone(sess.ended_at)

        # Verify audit log
        end_log = AuditLog.objects.filter(action="IMPERSONATE_END").first()
        self.assertIsNotNone(end_log)
        self.assertEqual(end_log.changes["session_id"], session_id)

    def test_impersonation_token_validates_and_exposes_impersonation_info(self):
        admin_token = self._login_and_get_token(self.admin)
        start_res = self.client.post(
            "/api/auth/impersonate/",
            {"target_user_id": self.student.id, "reason": "Testing validate"},
            format="json",
            **self._auth_header(admin_token),
        )
        impersonation_token = start_res.data["access"]

        # Call /api/auth/validate/
        val_res = self.client.get(
            "/api/auth/validate/",
            **self._auth_header(impersonation_token),
        )
        self.assertEqual(val_res.status_code, 200)
        self.assertEqual(val_res.data["username"], self.student.username)
        self.assertEqual(val_res.data["role"], Roles.STUDENT)
        self.assertIsNotNone(val_res.data["impersonation"])
        self.assertTrue(val_res.data["impersonation"]["active"])
        self.assertEqual(val_res.data["impersonation"]["impersonator"]["username"], self.admin.username)

    def test_blocked_endpoints_return_403_blocked_during_impersonation(self):
        admin_token = self._login_and_get_token(self.admin)
        start_res = self.client.post(
            "/api/auth/impersonate/",
            {"target_user_id": self.student.id, "reason": "Testing blocked endpoints"},
            format="json",
            **self._auth_header(admin_token),
        )
        impersonation_token = start_res.data["access"]
        auth_hdr = self._auth_header(impersonation_token)

        # 1. Chain impersonation
        res1 = self.client.post(
            "/api/auth/impersonate/",
            {"target_user_id": self.dept_staff.id, "reason": "Chain attempt"},
            format="json",
            **auth_hdr,
        )
        self.assertEqual(res1.status_code, 403)
        self.assertEqual(res1.data.get("code"), "blocked_during_impersonation")

        # 2. Logout all
        res2 = self.client.post("/api/auth/logout-all/", {}, format="json", **auth_hdr)
        self.assertEqual(res2.status_code, 403)
        self.assertEqual(res2.data.get("code"), "blocked_during_impersonation")

        # 3. Profile patch
        res3 = self.client.patch("/api/profile/", {"email": "hack@example.test"}, format="json", **auth_hdr)
        self.assertEqual(res3.status_code, 403)
        self.assertEqual(res3.data.get("code"), "blocked_during_impersonation")

    def test_impersonation_session_ended_when_expired(self):
        admin_token = self._login_and_get_token(self.admin)
        start_res = self.client.post(
            "/api/auth/impersonate/",
            {"target_user_id": self.student.id, "reason": "Testing expiry"},
            format="json",
            **self._auth_header(admin_token),
        )
        impersonation_token = start_res.data["access"]
        session_id = start_res.data["session_id"]

        # Manually expire the session in DB
        ImpersonationSession.objects.filter(id=session_id).update(
            expires_at=timezone.now() - timedelta(minutes=1)
        )

        res = self.client.get(
            "/api/auth/validate/",
            **self._auth_header(impersonation_token),
        )
        self.assertEqual(res.status_code, 401)
        self.assertEqual(res.data.get("code"), "impersonation_ended")

    def test_impersonation_session_ended_when_admin_deactivated(self):
        admin_token = self._login_and_get_token(self.admin)
        start_res = self.client.post(
            "/api/auth/impersonate/",
            {"target_user_id": self.student.id, "reason": "Testing admin deactivation"},
            format="json",
            **self._auth_header(admin_token),
        )
        impersonation_token = start_res.data["access"]

        # Deactivate admin
        self.admin.is_active = False
        self.admin.save(update_fields=["is_active"])

        res = self.client.get(
            "/api/auth/validate/",
            **self._auth_header(impersonation_token),
        )
        self.assertEqual(res.status_code, 401)
        self.assertEqual(res.data.get("code"), "impersonation_ended")
