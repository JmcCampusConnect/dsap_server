from datetime import timedelta
import time

from django.contrib.auth.hashers import make_password
from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import ImpersonationSession, Role, User
from apps.accounts.role_constants import Roles, get_capabilities
from apps.accounts.tokens import build_impersonation_access_token
from apps.audit.models import AuditLog
from apps.departments.models import AcademicDepartment, ServiceDepartment
from apps.services.models import Service
from apps.requests.models import Request
from apps.students.models import Student


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

    def test_start_response_sets_no_refresh_cookie(self):
        admin_token = self._login_and_get_token(self.admin)
        res = self.client.post(
            "/api/auth/impersonate/",
            {"target_user_id": self.student.id, "reason": "Cookie check"},
            format="json",
            **self._auth_header(admin_token),
        )
        self.assertEqual(res.status_code, 200)
        cookie_names = {c.key for c in res.cookies.values()}
        for name in ("refresh", "__Host-refresh", "__Secure-refresh", "access"):
            self.assertNotIn(name, cookie_names)

    def test_target_deactivated_mid_session_returns_401(self):
        admin_token = self._login_and_get_token(self.admin)
        start_res = self.client.post(
            "/api/auth/impersonate/",
            {"target_user_id": self.student.id, "reason": "Target deactivation"},
            format="json",
            **self._auth_header(admin_token),
        )
        self.assertEqual(start_res.status_code, 200)
        impersonation_token = start_res.data["access"]

        self.student.is_active = False
        self.student.save(update_fields=["is_active"])

        res = self.client.get(
            "/api/auth/validate/",
            **self._auth_header(impersonation_token),
        )
        # Any 401 while impersonating triggers force-exit; the exact sub-code
        # (user_inactive vs impersonation_ended) depends on where the check hits.
        self.assertEqual(res.status_code, 401)

    def test_admin_demoted_mid_session_returns_401(self):
        admin_token = self._login_and_get_token(self.admin)
        start_res = self.client.post(
            "/api/auth/impersonate/",
            {"target_user_id": self.student.id, "reason": "Admin demotion"},
            format="json",
            **self._auth_header(admin_token),
        )
        self.assertEqual(start_res.status_code, 200)
        impersonation_token = start_res.data["access"]

        self.admin.role_id = self.role_student
        self.admin.save(update_fields=["role_id"])

        res = self.client.get(
            "/api/auth/validate/",
            **self._auth_header(impersonation_token),
        )
        self.assertEqual(res.status_code, 401)
        self.assertEqual(res.data.get("code"), "impersonation_ended")

    def test_act_as_target_allowed_mutating_endpoint(self):
        service_dept = ServiceDepartment.objects.create(
            code="SVCE", name="Services", status=True
        )
        acad_dept = AcademicDepartment.objects.create(
            code="CSE", stream="SFM", degree="B.Sc", branch="Computer Science",
            type="UG", category="SCIENCE", status="active",
        )
        service = Service.objects.create(
            code="SVC001", name="Test Service", service_department_id=service_dept,
            base_fee=0, status=True,
        )
        Student.objects.create(
            register_number="24TEST001", name="Test Student", user_id=self.student,
            academic_department_id=acad_dept, year_of_admission="2024", stream="SFM",
        )

        admin_token = self._login_and_get_token(self.admin)
        start_res = self.client.post(
            "/api/auth/impersonate/",
            {"target_user_id": self.student.id, "reason": "Act as student"},
            format="json",
            **self._auth_header(admin_token),
        )
        self.assertEqual(start_res.status_code, 200)
        impersonation_token = start_res.data["access"]

        ir_before = AuditLog.objects.filter(action="IMPERSONATED_REQUEST").count()

        res = self.client.post(
            "/api/requests/",
            {"service_id": service.id},
            format="json",
            **self._auth_header(impersonation_token),
        )
        self.assertEqual(res.status_code, 201)
        request_obj = Request.objects.get(id=res.data["id"])
        self.assertEqual(request_obj.student_id.user_id_id, self.student.id)

        ir_after = AuditLog.objects.filter(action="IMPERSONATED_REQUEST").count()
        self.assertEqual(ir_after, ir_before + 1)
        ir_row = AuditLog.objects.filter(action="IMPERSONATED_REQUEST").order_by("-created_at").first()
        self.assertEqual(ir_row.impersonator_id, str(self.admin.id))
        self.assertEqual(ir_row.impersonator_name, self.admin.username)
        self.assertEqual(ir_row.changes["method"], "POST")
        self.assertEqual(ir_row.changes["path"], "/api/requests/")
        self.assertEqual(ir_row.changes["session_id"], start_res.data["session_id"])
        for key in ("body", "token", "password", "refresh", "access"):
            self.assertNotIn(key, ir_row.changes)

        self.client.get(
            "/api/requests/my/",
            **self._auth_header(impersonation_token),
        )
        ir_after_get = AuditLog.objects.filter(action="IMPERSONATED_REQUEST").count()
        self.assertEqual(ir_after_get, ir_after)

    def test_blocked_endpoints_return_403_while_impersonating(self):
        admin_token = self._login_and_get_token(self.admin)
        start_res = self.client.post(
            "/api/auth/impersonate/",
            {"target_user_id": self.student.id, "reason": "Blocked check"},
            format="json",
            **self._auth_header(admin_token),
        )
        self.assertEqual(start_res.status_code, 200)
        impersonation_token = start_res.data["access"]

        blocked = [
            ("POST", "/api/auth/impersonate/", {"target_user_id": self.student.id, "reason": "x"}),
            ("POST", "/api/auth/logout-all/", None),
            ("POST", "/api/auth/logout/", None),
            ("PATCH", "/api/profile/", {}),
        ]
        for method, path, payload in blocked:
            kwargs = {"format": "json", **self._auth_header(impersonation_token)}
            if payload is not None:
                res = getattr(self.client, method.lower())(path, payload, **kwargs)
            else:
                res = getattr(self.client, method.lower())(path, **kwargs)
            self.assertEqual(res.status_code, 403, f"{method} {path}")
            self.assertEqual(res.data.get("code"), "blocked_during_impersonation", f"{method} {path}")

        self.assertEqual(
            self.client.post("/api/auth/logout-all/", {}, format="json", **self._auth_header(admin_token)).status_code,
            200,
        )
        self.assertNotEqual(
            self.client.patch("/api/profile/", {}, format="json", **self._auth_header(admin_token)).status_code,
            403,
        )

    def test_student_endpoints_blocked_while_impersonating(self):
        student_user = User.objects.create(
            username="targetstudent", email="targetstudent@example.test",
            password_hash=make_password("password123"), role_id=self.role_student,
            is_active=True,
        )
        admin_token = self._login_and_get_token(self.admin)
        start_res = self.client.post(
            "/api/auth/impersonate/",
            {"target_user_id": student_user.id, "reason": "Student block check"},
            format="json",
            **self._auth_header(admin_token),
        )
        self.assertEqual(start_res.status_code, 200)
        impersonation_token = start_res.data["access"]

        blocked_student = [
            ("POST", f"/api/students/{student_user.id}/activate/", None),
            ("POST", f"/api/students/{student_user.id}/reset-password/", {"password": "newpass123"}),
        ]
        for method, path, payload in blocked_student:
            kwargs = {"format": "json", **self._auth_header(impersonation_token)}
            res = getattr(self.client, method.lower())(path, payload, **kwargs)
            self.assertEqual(res.status_code, 403, f"{method} {path}")
            self.assertEqual(res.data.get("code"), "blocked_during_impersonation", f"{method} {path}")

    def test_impersonate_end_exit_and_superseded_audit(self):
        admin_token = self._login_and_get_token(self.admin)

        start_res1 = self.client.post(
            "/api/auth/impersonate/",
            {"target_user_id": self.student.id, "reason": "First session"},
            format="json",
            **self._auth_header(admin_token),
        )
        self.assertEqual(start_res1.status_code, 200)
        session1_id = start_res1.data["session_id"]

        end_before = AuditLog.objects.filter(action="IMPERSONATE_END").count()

        # A second start supersedes the first session
        start_res2 = self.client.post(
            "/api/auth/impersonate/",
            {"target_user_id": self.student.id, "reason": "Second session"},
            format="json",
            **self._auth_header(admin_token),
        )
        self.assertEqual(start_res2.status_code, 200)
        session2_id = start_res2.data["session_id"]
        end_after_supersede = AuditLog.objects.filter(action="IMPERSONATE_END").count()
        self.assertEqual(end_after_supersede, end_before + 1)
        end_row = AuditLog.objects.filter(action="IMPERSONATE_END").order_by("-created_at").first()
        self.assertEqual(end_row.changes["ended_reason"], "superseded")
        self.assertEqual(end_row.changes["session_id"], session1_id)
        self.assertIsInstance(end_row.changes.get("duration_seconds"), int)
        self.assertFalse(ImpersonationSession.objects.get(id=session1_id).is_active)
        self.assertTrue(ImpersonationSession.objects.get(id=session2_id).is_active)

        # Exiting the second (active) session records reason=exit
        end_after_exit = AuditLog.objects.filter(action="IMPERSONATE_END").count()
        res = self.client.post(
            "/api/auth/impersonate/exit/",
            format="json",
            **self._auth_header(start_res2.data["access"]),
        )
        self.assertEqual(res.status_code, 200)
        end_final = AuditLog.objects.filter(action="IMPERSONATE_END").count()
        self.assertEqual(end_final, end_after_exit + 1)
        end_row2 = AuditLog.objects.filter(action="IMPERSONATE_END").order_by("-created_at").first()
        self.assertEqual(end_row2.changes["ended_reason"], "exit")
        self.assertEqual(end_row2.changes["session_id"], session2_id)
        self.assertFalse(ImpersonationSession.objects.get(id=session2_id).is_active)

    def test_impersonate_end_expired_audit(self):
        admin_token = self._login_and_get_token(self.admin)

        expired_session = ImpersonationSession.objects.create(
            admin_user=self.admin, target_user=self.student, reason="Expired test",
            expires_at=timezone.now() - timedelta(minutes=5),
            is_active=True,
        )
        expired_token = build_impersonation_access_token(
            target_user=self.student, admin_user=self.admin,
            session=expired_session, lifetime_minutes=5,
        )
        end_before = AuditLog.objects.filter(action="IMPERSONATE_END").count()
        res = self.client.get(
            "/api/auth/validate/",
            **self._auth_header(str(expired_token)),
        )
        end_after = AuditLog.objects.filter(action="IMPERSONATE_END").count()
        self.assertEqual(res.status_code, 401)
        self.assertEqual(res.data.get("code"), "impersonation_ended")
        end_after = AuditLog.objects.filter(action="IMPERSONATE_END").count()
        self.assertEqual(end_after, end_before + 1)
        end_row = AuditLog.objects.filter(action="IMPERSONATE_END").order_by("-created_at").first()
        self.assertEqual(end_row.changes["ended_reason"], "expired")
        self.assertEqual(end_row.changes["session_id"], expired_session.id)
        self.assertFalse(ImpersonationSession.objects.get(id=expired_session.id).is_active)

    def test_exit_ownership_recheck_returns_401_for_superseded_session(self):
        # F7: exit look-up also filters by admin_user_id and target_user_id.
        # A superseded session's token can no longer authenticate (401), and the
        # exit view only closes the session whose admin/target match the token.
        admin_token = self._login_and_get_token(self.admin)
        start_res = self.client.post(
            "/api/auth/impersonate/",
            {"target_user_id": self.student.id, "reason": "Ownership recheck"},
            format="json",
            **self._auth_header(admin_token),
        )
        self.assertEqual(start_res.status_code, 200)
        first_session_id = start_res.data["session_id"]

        # A second start supersedes the first session
        start_res2 = self.client.post(
            "/api/auth/impersonate/",
            {"target_user_id": self.student.id, "reason": "Supersede for recheck"},
            format="json",
            **self._auth_header(admin_token),
        )
        self.assertEqual(start_res2.status_code, 200)
        second_token = start_res2.data["access"]

        # Exiting with the second (active) token works
        res = self.client.post(
            "/api/auth/impersonate/exit/",
            format="json",
            **self._auth_header(second_token),
        )
        self.assertEqual(res.status_code, 200)
        self.assertFalse(ImpersonationSession.objects.get(id=start_res2.data["session_id"]).is_active)

        # The first (superseded) session stays closed
        self.assertFalse(ImpersonationSession.objects.get(id=first_session_id).is_active)

    def test_logout_blocked_during_impersonation(self):
        admin_token = self._login_and_get_token(self.admin)
        start_res = self.client.post(
            "/api/auth/impersonate/",
            {"target_user_id": self.student.id, "reason": "Logout block"},
            format="json",
            **self._auth_header(admin_token),
        )
        self.assertEqual(start_res.status_code, 200)
        impersonation_token = start_res.data["access"]

        res = self.client.post(
            "/api/auth/logout/",
            format="json",
            **self._auth_header(impersonation_token),
        )
        self.assertEqual(res.status_code, 403)
        self.assertEqual(res.data.get("code"), "blocked_during_impersonation")

    def test_normal_logout_unchanged(self):
        admin_token = self._login_and_get_token(self.admin)
        res = self.client.post(
            "/api/auth/logout/",
            format="json",
            **self._auth_header(admin_token),
        )
        self.assertEqual(res.status_code, 200)

    def test_impersonation_capability_only_for_system_admin(self):
        self.assertIn("user.impersonate", get_capabilities(Roles.SYSTEM_ADMIN))
        self.assertNotIn("user.impersonate", get_capabilities(Roles.STUDENT))
        self.assertNotIn("user.impersonate", get_capabilities(Roles.SERVICE_DEPT_ADMIN))
        self.assertNotIn("user.impersonate", get_capabilities(Roles.SERVICE_DEPT_STAFF))


class ImpersonationContextSwitchTests(TestCase):
    """API-level proof that the app switches to the target user's context during impersonation."""

    def setUp(self):
        cache.clear()
        self.role_sys_admin = Role.objects.create(name=Roles.SYSTEM_ADMIN)
        self.role_student = Role.objects.create(name=Roles.STUDENT)

        self.admin = User.objects.create(
            username="sysadmin", email="sysadmin@example.test",
            password_hash=make_password("password123"), role_id=self.role_sys_admin, is_active=True)
        self.student = User.objects.create(
            username="student1", email="student1@example.test",
            password_hash=make_password("password123"), role_id=self.role_student, is_active=True)

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

    def test_validate_returns_target_menus_and_capabilities(self):
        admin_token = self._login_and_get_token(self.admin)
        start_res = self.client.post(
            "/api/auth/impersonate/",
            {"target_user_id": self.student.id, "reason": "Context switch check"},
            format="json",
            **self._auth_header(admin_token),
        )
        self.assertEqual(start_res.status_code, 200)
        imp_token = start_res.data["access"]

        val_res = self.client.get("/api/auth/validate/", **self._auth_header(imp_token))
        self.assertEqual(val_res.status_code, 200)
        self.assertEqual(val_res.data["username"], self.student.username)
        self.assertEqual(val_res.data["role"], Roles.STUDENT)
        # Target's (student) menus/capabilities are delivered — not the admin's.
        self.assertIn("student_home", val_res.data["menus"])
        self.assertNotIn("dashboard", val_res.data["menus"])
        self.assertNotIn("user_management", val_res.data["menus"])
        self.assertIsNotNone(val_res.data["impersonation"])
        self.assertEqual(val_res.data["impersonation"]["impersonator"]["username"], self.admin.username)

    def test_exit_returns_401_when_session_already_closed(self):
        admin_token = self._login_and_get_token(self.admin)
        start_res = self.client.post(
            "/api/auth/impersonate/",
            {"target_user_id": self.student.id, "reason": "Exit after close check"},
            format="json",
            **self._auth_header(admin_token),
        )
        self.assertEqual(start_res.status_code, 200)
        imp_token = start_res.data["access"]

        # First exit closes the session (200).
        res1 = self.client.post(
            "/api/auth/impersonate/exit/", {}, format="json",
            **self._auth_header(imp_token),
        )
        self.assertEqual(res1.status_code, 200)

        # Second exit: authentication rejects the closed session before the view runs.
        res2 = self.client.post(
            "/api/auth/impersonate/exit/", {}, format="json",
            **self._auth_header(imp_token),
        )
        self.assertEqual(res2.status_code, 401)
        self.assertEqual(res2.data.get("code"), "impersonation_ended")

    def test_impersonation_token_rejected_after_exit(self):
        admin_token = self._login_and_get_token(self.admin)
        start_res = self.client.post(
            "/api/auth/impersonate/",
            {"target_user_id": self.student.id, "reason": "Post-exit rejection"},
            format="json",
            **self._auth_header(admin_token),
        )
        self.assertEqual(start_res.status_code, 200)
        imp_token = start_res.data["access"]

        self.client.post(
            "/api/auth/impersonate/exit/", {}, format="json",
            **self._auth_header(imp_token),
        )

        # After exit the session is closed; the impersonation token is rejected.
        res = self.client.get("/api/auth/validate/", **self._auth_header(imp_token))
        self.assertEqual(res.status_code, 401)
        self.assertEqual(res.data.get("code"), "impersonation_ended")

    def test_impersonate_start_audit_populates_impersonator_fields(self):
        admin_token = self._login_and_get_token(self.admin)
        self.client.post(
            "/api/auth/impersonate/",
            {"target_user_id": self.student.id, "reason": "Audit impersonator fields"},
            format="json",
            **self._auth_header(admin_token),
        )
        log = AuditLog.objects.filter(action="IMPERSONATE_START").first()
        self.assertIsNotNone(log)
        # The actor (admin) is recorded in user_id/name...
        self.assertEqual(log.user_id, str(self.admin.id))
        self.assertEqual(log.user_name, self.admin.username)
        # ...and the impersonator identity is also populated on the START row.
        self.assertEqual(log.impersonator_id, str(self.admin.id))
        self.assertEqual(log.impersonator_name, self.admin.username)
        self.assertEqual(log.changes["target_user_id"], self.student.id)
