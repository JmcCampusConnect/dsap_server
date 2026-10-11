from datetime import timedelta
from decimal import Decimal

from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient
from django.test import TestCase

from apps.accounts.models import Role, User
from apps.accounts.role_constants import Roles, has_menu_access
from apps.departments.models import ServiceDepartment
from apps.payments.models import Payment
from apps.requests.models import Request
from apps.services.models import Service
from apps.students.models import Student
from apps.workflow.constants import RequestStatuses
from apps.workflow.models import WorkflowHistory, WorkflowStep


class DashboardAPITestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        from seeders.runner import SEEDERS, run_seeder

        for seeder in SEEDERS:
            run_seeder(seeder)

    def setUp(self):
        self.client = APIClient()
        self.student = Student.objects.first()
        self.staff_role = Role.objects.get(name=Roles.SERVICE_DEPT_STAFF)
        self.admin_role = Role.objects.get(name=Roles.SERVICE_DEPT_ADMIN)
        self.system_admin = User.objects.get(username="SYSTEM_ADMIN")
        self.department, self.other_department = self.create_departments()
        self.staff_user = self.create_user(
            "dashboard-staff", self.staff_role, self.department
        )
        self.admin_user = self.create_user(
            "dashboard-admin", self.admin_role, self.department
        )
        self.staff_service = self.create_service(
            "DASH-STAFF", self.department, self.staff_role
        )
        self.admin_service = self.create_service(
            "DASH-ADMIN", self.department, self.admin_role
        )
        self.other_service = self.create_service(
            "DASH-OTHER", self.other_department, self.staff_role
        )

    @staticmethod
    def create_departments():
        return (
            ServiceDepartment.objects.create(code="DASH-A", name="Dashboard Department A"),
            ServiceDepartment.objects.create(code="DASH-B", name="Dashboard Department B"),
        )

    @staticmethod
    def create_user(username, role, department):
        return User.objects.create(
            username=username,
            email=f"{username}@example.test",
            password_hash="not-a-real-password",
            role_id=role,
            service_department_id=department,
            is_active=True,
        )

    @staticmethod
    def create_service(code, department, role, sla_days=1):
        service = Service.objects.create(
            code=code,
            name=f"{code} Service",
            service_department_id=department,
            sla_days=sla_days,
        )
        WorkflowStep.objects.create(
            service_id=service,
            step_order=1,
            step_name="Review",
            responsible_role_id=role,
            action_type="REVIEW",
            allowed_actions=[],
        )
        return service

    def create_request(self, number, service, status_name, submitted_at=None):
        step = WorkflowStep.objects.get(service_id=service)
        return Request.objects.create(
            request_number=number,
            student_id=self.student,
            service_id=service,
            current_status=status_name,
            current_step_id=step,
            submitted_at=submitted_at or timezone.now(),
            completed_at=(
                timezone.now() if status_name == RequestStatuses.COMPLETED else None
            ),
        )

    def test_anonymous_and_unapproved_roles_are_denied(self):
        for role_name in (
            Roles.SYSTEM_ADMIN,
            Roles.SERVICE_DEPT_ADMIN,
            Roles.SERVICE_DEPT_STAFF,
        ):
            self.assertTrue(has_menu_access(role_name, "dashboard"))
        self.assertFalse(has_menu_access(Roles.STUDENT, "dashboard"))
        self.assertFalse(has_menu_access(Roles.SUBJECT_TEACHING_STAFF, "dashboard"))

        response = self.client.get("/api/dashboard/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

        student_user = self.student.user_id
        self.client.force_authenticate(user=student_user)
        response = self.client.get("/api/dashboard/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        teaching_role, _ = Role.objects.get_or_create(
            name=Roles.SUBJECT_TEACHING_STAFF
        )
        teaching_user = self.create_user(
            "dashboard-teaching", teaching_role, self.department
        )
        self.client.force_authenticate(user=teaching_user)
        response = self.client.get("/api/dashboard/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_dashboard_roles_are_allowed_and_use_only_authorized_scope(self):
        own_staff_request = self.create_request(
            "DASH-OWN-STAFF",
            self.staff_service,
            RequestStatuses.SUBMITTED,
            timezone.now() - timedelta(days=4),
        )
        self.create_request(
            "DASH-OWN-ADMIN",
            self.admin_service,
            RequestStatuses.UNDER_VERIFICATION,
        )
        self.create_request(
            "DASH-OTHER-STAFF",
            self.other_service,
            RequestStatuses.SUBMITTED,
        )
        WorkflowHistory.objects.create(
            request_id=own_staff_request,
            step_id=own_staff_request.current_step_id,
            action_by_user_id=self.staff_user,
            action="FORWARD",
            remarks="Moved to next review.",
        )

        self.client.force_authenticate(user=self.staff_user)
        staff_response = self.client.get("/api/dashboard/")
        self.assertEqual(staff_response.status_code, status.HTTP_200_OK)
        staff_data = staff_response.data
        self.assertEqual(staff_data["role"], Roles.SERVICE_DEPT_STAFF)
        self.assertEqual(staff_data["scope"]["department"], self.department.name)
        self.assertEqual(staff_data["metrics"]["total_requests"], 1)
        self.assertEqual(
            sum(item["count"] for item in staff_data["status_counts"]),
            staff_data["metrics"]["total_requests"],
        )
        self.assertEqual(staff_data["metrics"]["sla_breaches"], 1)
        self.assertEqual(staff_data["metrics"]["actions_today"], 1)
        self.assertEqual(staff_data["metrics"]["forwarded_this_week"], 1)
        self.assertEqual(staff_data["services"][0]["request_count"], 1)
        self.assertEqual(
            [row["request_number"] for row in staff_data["recent_requests"]],
            ["DASH-OWN-STAFF"],
        )
        self.assertEqual(staff_data["recent_activity"][0]["request_number"], "DASH-OWN-STAFF")
        self.assertNotIn("assigned_to_me", staff_data["metrics"])
        self.assertIsNone(staff_data["metrics"]["paid_revenue_this_month"])

        self.client.force_authenticate(user=self.admin_user)
        admin_response = self.client.get("/api/dashboard/")
        self.assertEqual(admin_response.status_code, status.HTTP_200_OK)
        self.assertEqual(admin_response.data["metrics"]["total_requests"], 2)
        self.assertEqual(admin_response.data["scope"]["type"], "service_department")
        self.assertIsNone(admin_response.data["metrics"]["service_departments"])
        self.assertEqual(len(admin_response.data["revenue_history"]), 6)

        self.client.force_authenticate(user=self.system_admin)
        system_response = self.client.get("/api/dashboard/")
        self.assertEqual(system_response.status_code, status.HTTP_200_OK)
        self.assertEqual(system_response.data["scope"]["type"], "global")
        self.assertGreater(system_response.data["metrics"]["total_requests"], 2)
        self.assertIsNotNone(system_response.data["metrics"]["active_users"])
        self.assertIsNotNone(system_response.data["metrics"]["service_departments"])
        self.assertGreaterEqual(len(system_response.data["department_overview"]), 2)
        own_department = next(
            item
            for item in system_response.data["department_overview"]
            if item["id"] == self.department.id
        )
        self.assertEqual(own_department["requests"], 2)
        self.assertEqual(own_department["staff"], 2)
        self.assertEqual(system_response.data["staff_activity"][0]["username"], self.staff_user.username)

    def test_system_admin_revenue_uses_successful_payments_in_calendar_month(self):
        request = self.create_request(
            "DASH-PAID",
            self.staff_service,
            RequestStatuses.DRAFT,
        )
        paid_at = timezone.now()
        Payment.objects.create(
            request_id=request,
            amount=Decimal("37.50"),
            payment_status="SUCCESS",
            paid_at=paid_at,
        )
        unpaid_request = self.create_request(
            "DASH-UNPAID",
            self.staff_service,
            RequestStatuses.DRAFT,
        )
        Payment.objects.create(
            request_id=unpaid_request,
            amount=Decimal("88.00"),
            payment_status="PENDING",
            paid_at=paid_at,
        )

        self.client.force_authenticate(user=self.system_admin)
        response = self.client.get("/api/dashboard/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["metrics"]["paid_revenue_this_month"], "37.50")
        self.assertEqual(response.data["revenue_history"][-1]["amount"], "37.50")

    def test_department_admin_revenue_is_limited_to_their_department(self):
        own_request = self.create_request(
            "DASH-DEPT-PAID",
            self.staff_service,
            RequestStatuses.DRAFT,
        )
        other_request = self.create_request(
            "DASH-DEPT-OTHER-PAID",
            self.other_service,
            RequestStatuses.DRAFT,
        )
        paid_at = timezone.now()
        Payment.objects.create(
            request_id=own_request,
            amount=Decimal("19.25"),
            payment_status="SUCCESS",
            paid_at=paid_at,
        )
        Payment.objects.create(
            request_id=other_request,
            amount=Decimal("80.00"),
            payment_status="SUCCESS",
            paid_at=paid_at,
        )

        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get("/api/dashboard/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["metrics"]["paid_revenue_this_month"], "19.25")
        self.assertEqual(response.data["revenue_history"][-1]["amount"], "19.25")

    def test_empty_department_has_zero_metrics_and_empty_collections(self):
        empty_department = ServiceDepartment.objects.create(
            code="DASH-EMPTY", name="Empty Dashboard Department"
        )
        empty_admin = self.create_user(
            "dashboard-empty-admin", self.admin_role, empty_department
        )

        self.client.force_authenticate(user=empty_admin)
        response = self.client.get("/api/dashboard/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["metrics"]["total_requests"], 0)
        self.assertEqual(response.data["metrics"]["open_requests"], 0)
        self.assertEqual(response.data["metrics"]["sla_breaches"], 0)
        self.assertEqual(response.data["status_counts"], [])
        self.assertEqual(response.data["services"], [])
        self.assertEqual(response.data["recent_requests"], [])
        self.assertEqual(response.data["recent_activity"], [])
