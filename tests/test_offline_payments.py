from decimal import Decimal

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import Role, User
from apps.departments.models import AcademicDepartment, ServiceDepartment
from apps.payments.models import Payment, PaymentVerificationLog
from apps.payments.services import (
    PaymentFlowError,
    confirm_payment,
    reject_payment,
    submit_request,
)
from apps.requests.models import Request
from apps.services.models import Service
from apps.students.models import Student
from apps.workflow.models import WorkflowHistory, WorkflowStep


class OfflinePaymentFlowTestCase(TestCase):
    def setUp(self):
        self.staff_role = Role.objects.create(name="SERVICE_DEPT_STAFF")
        self.student_role = Role.objects.create(name="STUDENT")
        self.department = ServiceDepartment.objects.create(
            code="PAY-TEST",
            name="Payment Test Department",
        )
        self.staff = User.objects.create(
            username="payment-test-staff",
            email="payment-test-staff@example.test",
            password_hash="not-a-real-password",
            role_id=self.staff_role,
            service_department_id=self.department,
        )
        student_user = User.objects.create(
            username="payment-test-student",
            email="payment-test-student@example.test",
            password_hash="not-a-real-password",
            role_id=self.student_role,
        )
        academic_department = AcademicDepartment.objects.create(
            code="PAY-TEST",
            stream="Aided",
            degree="B.Sc.",
            branch="Computer Science",
            type="UG",
            category="SCIENCE",
        )
        student = Student.objects.create(
            register_number="PAY-TEST-001",
            name="Payment Test Student",
            user_id=student_user,
            academic_department_id=academic_department,
            year_of_admission="2024",
            mobile_number="0000000000",
        )
        self.service = Service.objects.create(
            code="PAY-TEST",
            name="Paid Test Service",
            service_department_id=self.department,
            base_fee=Decimal("125.00"),
        )
        self.payment_step = WorkflowStep.objects.create(
            service_id=self.service,
            step_order=1,
            step_name="Payment Verification",
            step_kind="PAYMENT_VERIFY",
            responsible_role_id=self.staff_role,
            allowed_actions=["PAYMENT_CONFIRM", "PAYMENT_REJECT"],
        )
        self.verification_step = WorkflowStep.objects.create(
            service_id=self.service,
            step_order=2,
            step_name="Document Verification",
            step_kind="VERIFICATION",
            responsible_role_id=self.staff_role,
            allowed_actions=["FORWARD"],
        )
        self.processing_step = WorkflowStep.objects.create(
            service_id=self.service,
            step_order=3,
            step_name="Processing",
            step_kind="PROCESSING",
            responsible_role_id=self.staff_role,
            allowed_actions=["COMPLETE"],
        )
        self.student = student
        self.client = APIClient()

    def create_draft(self, number="PAY-TEST-REQUEST", *, service=None):
        service = service or self.service
        request = Request.objects.create(
            request_number=number,
            student_id=self.student,
            service_id=service,
            current_status="DRAFT",
        )
        payment = Payment.objects.create(
            request_id=request,
            amount=service.base_fee,
            payment_status="PENDING",
        )
        return request, payment

    def confirm_data(self, **overrides):
        data = {
            "amount_received": Decimal("125.00"),
            "payment_date": timezone.localdate(),
            "payment_mode": "BANK_COUNTER",
            "bank_name": "Test Bank",
            "bank_branch": "Main Branch",
            "receipt_number": "CHALLAN-001",
            "remarks": "Original stamped receipt checked.",
        }
        data.update(overrides)
        return data

    def test_paid_submission_requires_acknowledgement_and_enters_payment_stage(self):
        request, payment = self.create_draft()

        with self.assertRaises(PaymentFlowError) as error:
            submit_request(request, submitted_by=self.staff)
        self.assertEqual(error.exception.detail["code"], "OFFLINE_PAYMENT_ACK_REQUIRED")

        request.refresh_from_db()
        self.assertEqual(request.current_status, "DRAFT")

        submit_request(
            request,
            submitted_by=self.staff,
            offline_payment_acknowledged=True,
        )
        request.refresh_from_db()
        payment.refresh_from_db()
        self.assertEqual(request.current_status, "PAYMENT_PENDING")
        self.assertEqual(request.current_step_id, self.payment_step)
        self.assertEqual(payment.payment_status, "PENDING")
        self.assertIsNone(payment.payment_due_at)

    def test_submit_api_requires_ack_and_returns_offline_payment_instructions(self):
        request, _ = self.create_draft()
        self.client.force_authenticate(user=self.student.user_id)

        rejected = self.client.post(
            f"/api/requests/{request.pk}/submit/",
            {},
            format="json",
            HTTP_HOST="localhost",
        )
        self.assertEqual(rejected.status_code, 400)
        self.assertEqual(rejected.data["code"], "OFFLINE_PAYMENT_ACK_REQUIRED")

        accepted = self.client.post(
            f"/api/requests/{request.pk}/submit/",
            {"offline_payment_acknowledged": True},
            format="json",
            HTTP_HOST="localhost",
        )
        self.assertEqual(accepted.status_code, 200)
        self.assertEqual(accepted.data["current_status"], "PAYMENT_PENDING")
        self.assertEqual(accepted.data["submission"]["fee_amount"], "125.00")
        self.assertEqual(len(accepted.data["submission"]["instructions"]), 3)
        self.assertNotIn("office_address", accepted.data["submission"])
        self.assertNotIn(
            "office_address", accepted.data["service"]["department"]
        )

    def test_free_service_skips_payment_verification(self):
        free_service = Service.objects.create(
            code="PAY-FREE",
            name="Free Test Service",
            service_department_id=self.department,
            base_fee=Decimal("0.00"),
        )
        verification_step = WorkflowStep.objects.create(
            service_id=free_service,
            step_order=1,
            step_name="Document Verification",
            step_kind="VERIFICATION",
            responsible_role_id=self.staff_role,
            allowed_actions=["FORWARD"],
        )
        request, payment = self.create_draft("PAY-FREE-REQUEST", service=free_service)

        submit_request(request, submitted_by=self.staff)
        request.refresh_from_db()
        payment.refresh_from_db()
        self.assertEqual(request.current_status, "SUBMITTED")
        self.assertEqual(request.current_step_id, verification_step)
        self.assertEqual(payment.payment_status, "SUCCESS")

    def test_staff_confirmation_advances_request_and_records_history(self):
        request, payment = self.create_draft()
        submit_request(
            request,
            submitted_by=self.staff,
            offline_payment_acknowledged=True,
        )

        confirmed = confirm_payment(payment, self.staff, self.confirm_data())
        request.refresh_from_db()
        self.assertEqual(confirmed.payment_status, "SUCCESS")
        self.assertEqual(request.current_status, "SUBMITTED")
        self.assertEqual(request.current_step_id, self.verification_step)
        self.assertEqual(
            PaymentVerificationLog.objects.filter(
                payment=payment,
                action=PaymentVerificationLog.CONFIRM,
            ).count(),
            1,
        )
        self.assertTrue(
            WorkflowHistory.objects.filter(
                request_id=request,
                action="PAYMENT_CONFIRM",
                step_id=self.payment_step,
            ).exists()
        )

    def test_amount_mismatch_does_not_confirm_or_advance(self):
        request, payment = self.create_draft()
        submit_request(
            request,
            submitted_by=self.staff,
            offline_payment_acknowledged=True,
        )

        with self.assertRaises(PaymentFlowError) as error:
            confirm_payment(
                payment,
                self.staff,
                self.confirm_data(amount_received=Decimal("100.00")),
            )
        self.assertEqual(error.exception.detail["code"], "AMOUNT_MISMATCH")
        payment.refresh_from_db()
        request.refresh_from_db()
        self.assertEqual(payment.payment_status, "PENDING")
        self.assertEqual(request.current_status, "PAYMENT_PENDING")

    def test_rejection_is_append_only_and_a_retry_can_be_confirmed(self):
        request, payment = self.create_draft()
        submit_request(
            request,
            submitted_by=self.staff,
            offline_payment_acknowledged=True,
        )
        reject_payment(payment, self.staff, "Bank stamp is missing.")
        request.refresh_from_db()
        payment.refresh_from_db()
        self.assertEqual(request.current_status, "PAYMENT_ISSUE")
        self.assertEqual(payment.payment_status, "ISSUE")

        confirm_payment(
            payment,
            self.staff,
            self.confirm_data(receipt_number="CHALLAN-RETRY"),
        )
        self.assertEqual(
            PaymentVerificationLog.objects.filter(payment=payment).count(),
            2,
        )
        self.assertEqual(
            list(
                PaymentVerificationLog.objects.filter(payment=payment)
                .order_by("id")
                .values_list("action", flat=True)
            ),
            ["REJECT", "CONFIRM"],
        )

    def test_receipt_number_is_unique_case_insensitively(self):
        first_request, first_payment = self.create_draft()
        submit_request(
            first_request,
            submitted_by=self.staff,
            offline_payment_acknowledged=True,
        )
        confirm_payment(
            first_payment,
            self.staff,
            self.confirm_data(receipt_number="SAME-RECEIPT"),
        )

        second_request, second_payment = self.create_draft("PAY-TEST-REQUEST-2")
        submit_request(
            second_request,
            submitted_by=self.staff,
            offline_payment_acknowledged=True,
        )
        with self.assertRaises(PaymentFlowError) as error:
            confirm_payment(
                second_payment,
                self.staff,
                self.confirm_data(receipt_number="same-receipt"),
            )
        self.assertEqual(error.exception.detail["code"], "DUPLICATE_RECEIPT")

    def test_pending_endpoint_is_scoped_to_staff_department(self):
        other_department = ServiceDepartment.objects.create(
            code="PAY-OTHER",
            name="Other Payment Department",
        )
        other_service = Service.objects.create(
            code="PAY-OTHER",
            name="Other Paid Service",
            service_department_id=other_department,
            base_fee=Decimal("20.00"),
        )
        WorkflowStep.objects.create(
            service_id=other_service,
            step_order=1,
            step_name="Payment Verification",
            step_kind="PAYMENT_VERIFY",
            responsible_role_id=self.staff_role,
            allowed_actions=["PAYMENT_CONFIRM"],
        )
        WorkflowStep.objects.create(
            service_id=other_service,
            step_order=2,
            step_name="Document Verification",
            step_kind="VERIFICATION",
            responsible_role_id=self.staff_role,
            allowed_actions=["FORWARD"],
        )
        own_request, _ = self.create_draft()
        other_request, _ = self.create_draft(
            "PAY-OTHER-REQUEST",
            service=other_service,
        )
        submit_request(
            own_request,
            submitted_by=self.staff,
            offline_payment_acknowledged=True,
        )
        submit_request(
            other_request,
            submitted_by=self.staff,
            offline_payment_acknowledged=True,
        )

        self.client.force_authenticate(user=self.staff)
        response = self.client.get("/api/payments/pending/", HTTP_HOST="localhost")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [item["request_number"] for item in response.data["results"]],
            [own_request.request_number],
        )

    def test_new_offline_payment_does_not_assign_a_due_date(self):
        request, payment = self.create_draft()
        submit_request(
            request,
            submitted_by=self.staff,
            offline_payment_acknowledged=True,
        )
        payment.refresh_from_db()
        self.assertIsNone(payment.payment_due_at)

    def test_department_admin_can_update_only_own_department_profile(self):
        admin_role = Role.objects.create(name="SERVICE_DEPT_ADMIN")
        department_admin = User.objects.create(
            username="payment-test-admin",
            email="payment-test-admin@example.test",
            password_hash="not-a-real-password",
            role_id=admin_role,
            service_department_id=self.department,
        )
        other_department = ServiceDepartment.objects.create(
            code="PAY-OTHER",
            name="Other Payment Department",
        )
        self.client.force_authenticate(user=department_admin)

        updated = self.client.patch(
            f"/api/service-departments/{self.department.pk}/",
            {"name": "Updated Payment Department", "status": False},
            format="json",
            HTTP_HOST="localhost",
        )
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated.data["name"], "Updated Payment Department")
        self.assertIs(updated.data["status"], True)
        self.assertNotIn("office_address", updated.data)

        forbidden = self.client.patch(
            f"/api/service-departments/{other_department.pk}/",
            {"name": "Not allowed"},
            HTTP_HOST="localhost",
        )
        self.assertEqual(forbidden.status_code, 404)

    def test_system_admin_can_create_and_filter_departments_by_boolean_status(self):
        system_admin_role = Role.objects.create(name="SYSTEM_ADMIN")
        system_admin = User.objects.create(
            username="payment-test-system-admin",
            email="payment-test-system-admin@example.test",
            password_hash="not-a-real-password",
            role_id=system_admin_role,
        )
        self.client.force_authenticate(user=system_admin)

        created = self.client.post(
            "/api/service-departments/",
            {"code": "BOOL-TEST", "name": "Boolean Status Department", "status": False},
            format="json",
            HTTP_HOST="localhost",
        )
        self.assertEqual(created.status_code, 201)
        self.assertIs(created.data["status"], False)
        self.assertNotIn("office_address", created.data)

        filtered = self.client.get(
            "/api/service-departments/?status=false",
            HTTP_HOST="localhost",
        )
        self.assertEqual(filtered.status_code, 200)
        self.assertIn(
            created.data["id"],
            [department["id"] for department in filtered.data["results"]],
        )
        invalid = self.client.post(
            "/api/service-departments/",
            {"code": "BOOL-INVALID", "name": "Invalid Status", "status": "active"},
            format="json",
            HTTP_HOST="localhost",
        )
        self.assertEqual(invalid.status_code, 400)

    def test_student_cannot_confirm_or_reject_payment(self):
        request, payment = self.create_draft()
        submit_request(request, submitted_by=self.staff, offline_payment_acknowledged=True)
        self.client.force_authenticate(user=self.student.user_id)

        confirm_res = self.client.post(
            f"/api/payments/{payment.pk}/confirm/",
            self.confirm_data(),
            format="json",
            HTTP_HOST="localhost",
        )
        self.assertEqual(confirm_res.status_code, 403)

        reject_res = self.client.post(
            f"/api/payments/{payment.pk}/reject/",
            {"reason": "Invalid payment"},
            format="json",
            HTTP_HOST="localhost",
        )
        self.assertEqual(reject_res.status_code, 403)

    def test_other_department_staff_cannot_confirm_or_reject_payment(self):
        other_dept = ServiceDepartment.objects.create(code="OTHER", name="Other Dept")
        other_staff = User.objects.create(
            username="other-staff",
            email="other-staff@example.test",
            password_hash="not-a-real-password",
            role_id=self.staff_role,
            service_department_id=other_dept,
        )
        request, payment = self.create_draft()
        submit_request(request, submitted_by=self.staff, offline_payment_acknowledged=True)
        self.client.force_authenticate(user=other_staff)

        confirm_res = self.client.post(
            f"/api/payments/{payment.pk}/confirm/",
            self.confirm_data(),
            format="json",
            HTTP_HOST="localhost",
        )
        self.assertEqual(confirm_res.status_code, 403)

        reject_res = self.client.post(
            f"/api/payments/{payment.pk}/reject/",
            {"reason": "Invalid payment"},
            format="json",
            HTTP_HOST="localhost",
        )
        self.assertEqual(reject_res.status_code, 403)

    def test_rejection_requires_reason(self):
        request, payment = self.create_draft()
        submit_request(request, submitted_by=self.staff, offline_payment_acknowledged=True)

        with self.assertRaises(PaymentFlowError) as error:
            reject_payment(payment, self.staff, "   ")
        self.assertEqual(error.exception.detail["code"], "REJECTION_REASON_REQUIRED")

        self.client.force_authenticate(user=self.staff)
        res = self.client.post(
            f"/api/payments/{payment.pk}/reject/",
            {"reason": ""},
            format="json",
            HTTP_HOST="localhost",
        )
        self.assertEqual(res.status_code, 400)

    def test_generic_workflow_endpoints_cannot_bypass_payment_verification(self):
        request, payment = self.create_draft()
        submit_request(request, submitted_by=self.staff, offline_payment_acknowledged=True)
        self.client.force_authenticate(user=self.staff)

        forward_res = self.client.post(
            f"/api/department-queue/{request.pk}/forward/",
            {"remarks": "Trying to bypass payment"},
            format="json",
            HTTP_HOST="localhost",
        )
        self.assertEqual(forward_res.status_code, 409)
        self.assertEqual(forward_res.data["code"], "PAYMENT_NOT_VERIFIED")

        return_res = self.client.post(
            f"/api/department-queue/{request.pk}/return/",
            {"remarks": "Returning before payment"},
            format="json",
            HTTP_HOST="localhost",
        )
        self.assertEqual(return_res.status_code, 409)
        self.assertEqual(return_res.data["code"], "PAYMENT_NOT_VERIFIED")

    def test_cannot_confirm_already_confirmed_payment(self):
        request, payment = self.create_draft()
        submit_request(request, submitted_by=self.staff, offline_payment_acknowledged=True)
        confirm_payment(payment, self.staff, self.confirm_data())

        with self.assertRaises(PaymentFlowError) as error:
            confirm_payment(payment, self.staff, self.confirm_data())
        self.assertEqual(error.exception.detail["code"], "PAYMENT_ALREADY_VERIFIED")
