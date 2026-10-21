from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.audit.models import AuditLog
from apps.payments.models import Payment
from apps.requests.models import Request
from apps.services.models import Service


class ReportsModuleTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        from seeders.runner import SEEDERS, run_seeder
        for s in SEEDERS:
            run_seeder(s)

        # Ensure at least one request has a successful payment for testing revenue
        req = Request.objects.filter(current_status='COMPLETED').first()
        if req:
            Payment.objects.update_or_create(
                request_id=req,
                defaults={
                    'amount': 500.00,
                    'payment_status': 'SUCCESS',
                    'payment_method': 'UPI',
                    'gateway_txn_id': 'TXN_TEST_1001',
                    'paid_at': req.submitted_at,
                }
            )

    def setUp(self):
        self.client = APIClient()
        self.sysadmin = User.objects.get(username="SYSTEM_ADMIN")
        self.coe_admin = User.objects.get(username="COE_ADMIN")
        self.coe_staff = User.objects.get(username="COE_STAFF")
        self.lib_admin = User.objects.get(username="LIB_ADMIN")
        self.lib_staff = User.objects.get(username="LIB_STAFF")
        self.student_user = User.objects.get(username="24MCA066")
        self.teacher_user = User.objects.get(username="JMCMTS0006")

    # ----------------------------------------------------------------------
    # 1. Summary API
    # ----------------------------------------------------------------------
    def test_01_sysadmin_can_access_summary(self):
        self.client.force_authenticate(user=self.sysadmin)
        res = self.client.get("/api/reports/summary/", HTTP_HOST="localhost")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        data = res.data
        self.assertIn("total_requests", data)
        self.assertIn("status_counts", data)
        self.assertIn("revenue_summary", data)
        self.assertIn("filters_applied", data)
        # Verify all 6 statuses are present
        for st in ['SUBMITTED', 'UNDER_VERIFICATION', 'APPROVED', 'COMPLETED', 'REJECTED', 'RETURNED']:
            self.assertIn(st, data['status_counts'])

    def test_02_department_staff_summary_is_scoped(self):
        self.client.force_authenticate(user=self.coe_staff)
        res = self.client.get("/api/reports/summary/", HTTP_HOST="localhost")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        # LIB staff should have 0 requests because seeded requests belong to COE
        self.client.force_authenticate(user=self.lib_staff)
        res_lib = self.client.get("/api/reports/summary/", HTTP_HOST="localhost")
        self.assertEqual(res_lib.status_code, status.HTTP_200_OK)
        self.assertEqual(res_lib.data["total_requests"], 0)

    def test_03_unauthorized_roles_denied_summary(self):
        # Student denied
        self.client.force_authenticate(user=self.student_user)
        res_student = self.client.get("/api/reports/summary/", HTTP_HOST="localhost")
        self.assertEqual(res_student.status_code, status.HTTP_403_FORBIDDEN)

        # Subject Teacher denied
        self.client.force_authenticate(user=self.teacher_user)
        res_teacher = self.client.get("/api/reports/summary/", HTTP_HOST="localhost")
        self.assertEqual(res_teacher.status_code, status.HTTP_403_FORBIDDEN)

        # Anonymous denied
        self.client.logout()
        res_anon = self.client.get("/api/reports/summary/", HTTP_HOST="localhost")
        self.assertEqual(res_anon.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_04_summary_date_validation_error(self):
        self.client.force_authenticate(user=self.sysadmin)
        res = self.client.get("/api/reports/summary/?from_date=invalid-date", HTTP_HOST="localhost")
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", res.data)
        self.assertEqual(res.data["error"]["code"], "VALIDATION_ERROR")

    # ----------------------------------------------------------------------
    # 2. Requests Listing API
    # ----------------------------------------------------------------------
    def test_05_requests_listing_pagination_and_fields(self):
        self.client.force_authenticate(user=self.sysadmin)
        res = self.client.get("/api/reports/requests/?page=1&page_size=2", HTTP_HOST="localhost")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        data = res.data
        self.assertIn("count", data)
        self.assertIn("results", data)
        self.assertTrue(len(data["results"]) <= 2)

        if data["results"]:
            first_item = data["results"][0]
            self.assertIn("request_number", first_item)
            self.assertIn("student", first_item)
            self.assertIn("service", first_item)
            self.assertIn("current_status", first_item)
            self.assertIn("submitted_at", first_item)
            self.assertIn("completed_at", first_item)
            self.assertIn("payment", first_item)
            # Verify student fields
            self.assertIn("register_number", first_item["student"])
            self.assertIn("name", first_item["student"])
            self.assertIn("stream", first_item["student"])
            self.assertIn("academic_department", first_item["student"])

    def test_06_requests_listing_filters(self):
        self.client.force_authenticate(user=self.sysadmin)
        # Filter by status
        res = self.client.get("/api/reports/requests/?status=UNDER_VERIFICATION", HTTP_HOST="localhost")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        for item in res.data["results"]:
            self.assertEqual(item["current_status"], "UNDER_VERIFICATION")

        # Filter by stream
        res_stream = self.client.get("/api/reports/requests/?stream=SFM", HTTP_HOST="localhost")
        self.assertEqual(res_stream.status_code, status.HTTP_200_OK)
        for item in res_stream.data["results"]:
            self.assertEqual(item["student"]["stream"], "SFM")

    # ----------------------------------------------------------------------
    # 3. Revenue API
    # ----------------------------------------------------------------------
    def test_07_revenue_report_structure_and_payment_date_filter(self):
        self.client.force_authenticate(user=self.sysadmin)
        res = self.client.get("/api/reports/revenue/?from_date=2026-01-01&to_date=2026-12-31", HTTP_HOST="localhost")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        data = res.data
        self.assertIn("summary", data)
        self.assertIn("by_service", data)
        self.assertIn("by_payment_method", data)
        self.assertIn("total_revenue_collected", data["summary"])
        self.assertIn("total_successful_transactions", data["summary"])

        if data["by_service"]:
            svc = data["by_service"][0]
            self.assertIn("service_id", svc)
            self.assertIn("service_code", svc)
            self.assertIn("service_name", svc)
            self.assertIn("service_department_name", svc)
            self.assertIn("successful_count", svc)
            self.assertIn("total_amount", svc)

    # ----------------------------------------------------------------------
    # 4. Export API (Excel & CSV) + AuditLog
    # ----------------------------------------------------------------------
    def test_08_export_excel_requests(self):
        self.client.force_authenticate(user=self.sysadmin)
        res = self.client.get("/api/reports/export/?report_type=requests&format=xlsx", HTTP_HOST="localhost")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(
            res["Content-Type"],
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        self.assertIn("attachment; filename=", res["Content-Disposition"])
        self.assertTrue(len(res.content) > 0)

        # Verify AuditLog created
        audit_entry = AuditLog.objects.filter(action='EXPORT').first()
        self.assertIsNotNone(audit_entry)
        self.assertIn("requests", audit_entry.object_repr.lower())

    def test_09_export_csv_requests(self):
        self.client.force_authenticate(user=self.sysadmin)
        res = self.client.get("/api/reports/export/?report_type=requests&format=csv", HTTP_HOST="localhost")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res["Content-Type"], "text/csv; charset=utf-8")
        self.assertIn("attachment; filename=", res["Content-Disposition"])
        csv_text = res.content.decode("utf-8")
        self.assertIn("Request Number", csv_text)
        self.assertIn("Student Name", csv_text)

    def test_10_export_validation_errors(self):
        self.client.force_authenticate(user=self.sysadmin)
        # Invalid format
        res_bad_format = self.client.get("/api/reports/export/?format=pdf", HTTP_HOST="localhost")
        self.assertEqual(res_bad_format.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", res_bad_format.data)

        # Invalid report_type
        res_bad_type = self.client.get("/api/reports/export/?report_type=unknown", HTTP_HOST="localhost")
        self.assertEqual(res_bad_type.status_code, status.HTTP_400_BAD_REQUEST)

    # ----------------------------------------------------------------------
    # 5. Options API
    # ----------------------------------------------------------------------
    def test_11_options_api_structure_and_scoping(self):
        # System Admin sees all departments
        self.client.force_authenticate(user=self.sysadmin)
        res_sys = self.client.get("/api/reports/options/", HTTP_HOST="localhost")
        self.assertEqual(res_sys.status_code, status.HTTP_200_OK)
        data = res_sys.data
        self.assertIn("service_departments", data)
        self.assertIn("services", data)
        self.assertIn("academic_departments", data)
        self.assertIn("request_statuses", data)
        self.assertIn("streams", data)
        self.assertIn("payment_statuses", data)
        # Verify stream choices
        self.assertEqual(data["streams"], ["SFM", "SFW", "AIDED"])

        # COE Admin sees only COE department and services
        self.client.force_authenticate(user=self.coe_admin)
        res_coe = self.client.get("/api/reports/options/", HTTP_HOST="localhost")
        self.assertEqual(res_coe.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res_coe.data["service_departments"]), 1)
        self.assertEqual(res_coe.data["service_departments"][0]["code"], "COE")
        for svc in res_coe.data["services"]:
            self.assertEqual(svc["service_department_id"], self.coe_admin.service_department_id.id)
