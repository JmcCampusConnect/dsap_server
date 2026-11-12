"""
Tests for GET /api/profile/ and PATCH /api/profile/.

Covers permissions, role-shaped responses, editable-field allow-list,
validation, duplicate-email 409, and AuditLog writes.
"""

from datetime import date

from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.accounts.models import Role, User
from apps.audit.models import AuditLog
from apps.departments.models import AcademicDepartment, ServiceDepartment
from apps.students.models import Student


class ProfileAPITestBase(TestCase):
    url = "/api/profile/"

    def setUp(self):
        self.client = APIClient()

        self.student_role = Role.objects.create(name="STUDENT")
        self.staff_role = Role.objects.create(name="SERVICE_DEPT_STAFF")

        self.academic_dept = AcademicDepartment.objects.create(
            code="MCA", stream="Aided", degree="M.C.A.",
            branch="Computer Applications", type="PG", category="SCIENCE",
        )
        self.service_dept = ServiceDepartment.objects.create(
            code="COE", name="Controller of Examinations",
        )

        self.student_user = User.objects.create(
            username="24MCA057",
            email="student057@example.com",
            password_hash="x",
            role_id=self.student_role,
            is_active=True,
        )
        self.student = Student.objects.create(
            register_number="24MCA057",
            name="Abdul Rasak H",
            dob=date(2000, 1, 1),
            user_id=self.student_user,
            academic_department_id=self.academic_dept,
            year_of_admission="2024-2026",
            section="A",
            stream="SFM",
            mobile_number="9876543210",
            status=True,
        )

        self.staff_user = User.objects.create(
            username="COE_STAFF",
            email="coe.staff@example.com",
            password_hash="x",
            role_id=self.staff_role,
            service_department_id=self.service_dept,
            is_active=True,
        )

    def auth(self, user):
        token = AccessToken.for_user(user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")


# ---------------------------------------------------------------------
# Permissions
# ---------------------------------------------------------------------
class ProfilePermissionsTests(ProfileAPITestBase):
    def test_get_without_token_returns_401(self):
        self.assertEqual(self.client.get(self.url).status_code, 401)

    def test_patch_without_token_returns_401(self):
        response = self.client.patch(
            self.url, {"email": "x@y.com"}, format="json"
        )
        self.assertEqual(response.status_code, 401)

    def test_get_with_invalid_token_returns_401(self):
        self.client.credentials(HTTP_AUTHORIZATION="Bearer not-a-token")
        self.assertEqual(self.client.get(self.url).status_code, 401)


# ---------------------------------------------------------------------
# GET — STUDENT
# ---------------------------------------------------------------------
class StudentProfileReadTests(ProfileAPITestBase):
    def setUp(self):
        super().setUp()
        self.auth(self.student_user)

    def test_response_shape(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["role"], "STUDENT")
        self.assertEqual(response.data["username"], "24MCA057")
        self.assertIn("profile", response.data)
        self.assertIn("academic", response.data)
        self.assertIn("contact", response.data)

    def test_academic_block_exposes_department_fields(self):
        data = self.client.get(self.url).data["academic"]
        self.assertEqual(data["department_id"], self.academic_dept.id)
        self.assertEqual(data["type"], "PG")
        self.assertEqual(data["category"], "SCIENCE")
        self.assertEqual(data["stream"], "SFM")

    def test_contact_block_returns_raw_mobile_and_email(self):
        data = self.client.get(self.url).data["contact"]
        self.assertEqual(data["mobile_number"], "9876543210")
        self.assertEqual(data["email"], "student057@example.com")


# ---------------------------------------------------------------------
# GET — STAFF / ADMIN
# ---------------------------------------------------------------------
class StaffProfileReadTests(ProfileAPITestBase):
    def setUp(self):
        super().setUp()
        self.auth(self.staff_user)

    def test_response_shape(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["role"], "SERVICE_DEPT_STAFF")
        self.assertNotIn("profile", response.data)
        self.assertNotIn("academic", response.data)
        self.assertNotIn("contact", response.data)

    def test_service_department_block(self):
        data = self.client.get(self.url).data
        self.assertEqual(
            data["service_department"],
            {"id": self.service_dept.id, "code": "COE", "name": "Controller of Examinations"},
        )

    def test_academic_department_null_when_unset(self):
        self.assertIsNone(self.client.get(self.url).data["academic_department"])


# ---------------------------------------------------------------------
# PATCH — Student happy path + audit
# ---------------------------------------------------------------------
class StudentProfilePatchTests(ProfileAPITestBase):
    def setUp(self):
        super().setUp()
        self.auth(self.student_user)

    def test_update_mobile_persists_and_audits(self):
        response = self.client.patch(
            self.url, {"mobile_number": "9123456789"}, format="json"
        )
        self.assertEqual(response.status_code, 200)

        self.student.refresh_from_db()
        self.assertEqual(self.student.mobile_number, "9123456789")

        audit = AuditLog.objects.filter(
            action="UPDATE", model_name="Student"
        ).order_by("-id").first()
        self.assertIsNotNone(audit)
        self.assertEqual(
            audit.changes["mobile_number"],
            {"old": "9876543210", "new": "9123456789"},
        )

    def test_update_email_persists_and_audits(self):
        response = self.client.patch(
            self.url, {"email": "new.student@example.com"}, format="json"
        )
        self.assertEqual(response.status_code, 200)

        self.student_user.refresh_from_db()
        self.assertEqual(self.student_user.email, "new.student@example.com")

        audit = AuditLog.objects.filter(
            action="UPDATE", model_name="User"
        ).order_by("-id").first()
        self.assertIsNotNone(audit)
        self.assertEqual(
            audit.changes["email"]["new"], "new.student@example.com",
        )

    def test_mobile_is_normalized_before_storage(self):
        response = self.client.patch(
            self.url, {"mobile_number": "+91 91234-56789"}, format="json"
        )
        self.assertEqual(response.status_code, 200)
        self.student.refresh_from_db()
        self.assertEqual(self.student.mobile_number, "9123456789")

    def test_same_email_submission_is_noop(self):
        response = self.client.patch(
            self.url, {"email": "student057@example.com"}, format="json"
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(
            AuditLog.objects.filter(action="UPDATE", model_name="User").exists()
        )


# ---------------------------------------------------------------------
# PATCH — Validation errors
# ---------------------------------------------------------------------
class StudentProfilePatchValidationTests(ProfileAPITestBase):
    def setUp(self):
        super().setUp()
        self.auth(self.student_user)

    def _assert_no_writes(self):
        self.assertFalse(AuditLog.objects.filter(action="UPDATE").exists())

    def test_invalid_mobile_returns_400(self):
        response = self.client.patch(
            self.url, {"mobile_number": "12345"}, format="json"
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["error"], "VALIDATION_ERROR")
        self._assert_no_writes()

    def test_mobile_must_start_with_6_to_9(self):
        response = self.client.patch(
            self.url, {"mobile_number": "1234567890"}, format="json"
        )
        self.assertEqual(response.status_code, 400)

    def test_invalid_email_returns_400(self):
        response = self.client.patch(
            self.url, {"email": "not-an-email"}, format="json"
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["error"], "VALIDATION_ERROR")
        self._assert_no_writes()

    def test_duplicate_email_returns_409(self):
        response = self.client.patch(
            self.url, {"email": "coe.staff@example.com"}, format="json"
        )
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data["error"], "EMAIL_EXISTS")
        self._assert_no_writes()

    def test_non_editable_field_returns_400(self):
        response = self.client.patch(
            self.url, {"name": "Hacked"}, format="json"
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["error"], "FIELD_NOT_EDITABLE")
        self.assertIn("name", response.data["fields"])

        self.student.refresh_from_db()
        self.assertEqual(self.student.name, "Abdul Rasak H")
        self._assert_no_writes()

    def test_mixed_editable_and_non_editable_rejects_all(self):
        response = self.client.patch(
            self.url,
            {"mobile_number": "9123456789", "name": "Hacked"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["error"], "FIELD_NOT_EDITABLE")

        self.student.refresh_from_db()
        self.assertEqual(self.student.mobile_number, "9876543210")  # unchanged
        self._assert_no_writes()

    def test_empty_body_returns_400(self):
        response = self.client.patch(self.url, {}, format="json")
        self.assertEqual(response.status_code, 400)
        self._assert_no_writes()


# ---------------------------------------------------------------------
# PATCH — Staff
# ---------------------------------------------------------------------
class StaffProfilePatchTests(ProfileAPITestBase):
    def setUp(self):
        super().setUp()
        self.auth(self.staff_user)

    def test_update_email_persists_and_audits(self):
        response = self.client.patch(
            self.url, {"email": "updated.staff@example.com"}, format="json"
        )
        self.assertEqual(response.status_code, 200)

        self.staff_user.refresh_from_db()
        self.assertEqual(self.staff_user.email, "updated.staff@example.com")
        self.assertTrue(
            AuditLog.objects.filter(action="UPDATE", model_name="User").exists()
        )

    def test_mobile_field_not_editable_for_staff(self):
        response = self.client.patch(
            self.url, {"mobile_number": "9123456789"}, format="json"
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["error"], "FIELD_NOT_EDITABLE")
        self.assertIn("mobile_number", response.data["fields"])