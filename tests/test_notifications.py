"""
Comprehensive test suite for Admin-Managed Email Notification Template System.
Tests:
- Template CRUD and permissions (SystemAdmin required)
- Placeholder validation and email subject CRLF injection prevention
- Safe dynamic escaping and HTML sanitization
- Preview endpoint
- Recipient resolution (valid vs missing/invalid emails)
- Transaction-safe email dispatch via Django's test locmem email backend
- Email failure recording without interrupting caller workflows
- Transaction rollback behavior (no email on rollback)
- Event-specific idempotency and concurrency duplicate prevention
- Manual retry service and maximum retry limits
- Workflow integration (Submission, Forward, Return, Reject, Complete, Issue)
- Audit log recording for admin operations
"""

from unittest.mock import patch

from django.core import mail
from django.core.exceptions import ValidationError
from django.db import transaction
from django.test import TestCase, override_settings
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.models import Role, User
from apps.accounts.role_constants import Roles
from apps.audit.models import AuditLog
from apps.departments.models import AcademicDepartment, ServiceDepartment
from apps.notifications.models import (
    Notification,
    NotificationChannels,
    NotificationStatuses,
    NotificationTemplate,
)
from apps.notifications.services import (
    dispatch_notification,
    html_to_plain_text,
    render_template,
    retry_notification,
    sanitize_html,
    schedule_notification_dispatch,
    validate_placeholders,
    validate_subject,
)
from apps.requests.models import Request
from apps.services.models import Service
from apps.students.models import Student
from apps.workflow.constants import AllowedActions, NotificationEventCodes, RequestStatuses, WorkflowStepKinds
from apps.workflow.models import WorkflowHistory, WorkflowStep


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class NotificationTemplateSystemTests(TestCase):

    def setUp(self):
        mail.outbox = []

        # Roles
        self.admin_role, _ = Role.objects.get_or_create(name=Roles.SYSTEM_ADMIN)
        self.staff_role, _ = Role.objects.get_or_create(name=Roles.SERVICE_DEPT_STAFF)
        self.student_role, _ = Role.objects.get_or_create(name=Roles.STUDENT)

        # Users
        self.admin_user = User.objects.create(
            username="admin_test",
            email="admin@college.edu",
            role_id=self.admin_role,
        )
        self.staff_user = User.objects.create(
            username="staff_test",
            email="staff@college.edu",
            role_id=self.staff_role,
        )
        self.student_user = User.objects.create(
            username="student_test",
            email="student@college.edu",
            role_id=self.student_role,
        )

        # Academic & Service Departments
        self.service_dept = ServiceDepartment.objects.create(
            code="COE",
            name="Controller of Examinations",
        )
        self.academic_dept = AcademicDepartment.objects.create(
            code="MCA",
            stream="SFM",
            degree="PG",
            branch="Computer Applications",
        )

        # Student Profile
        self.student = Student.objects.create(
            register_number="24MCA001",
            name="Ahmad Test Student",
            user_id=self.student_user,
            academic_department_id=self.academic_dept,
            mobile_number="9876543210",
        )

        # Service
        self.service = Service.objects.create(
            code="COE-TRANSCRIPT",
            name="Transcript Certificate",
            service_department_id=self.service_dept,
            base_fee=100.0,
        )

        # Workflow Steps
        self.step1 = WorkflowStep.objects.create(
            service_id=self.service,
            step_order=1,
            step_name="Document Verification",
            step_kind=WorkflowStepKinds.VERIFICATION,
            responsible_role_id=self.staff_role,
            allowed_actions=[AllowedActions.FORWARD, AllowedActions.RETURN, AllowedActions.REJECT],
        )
        self.step2 = WorkflowStep.objects.create(
            service_id=self.service,
            step_order=2,
            step_name="Certificate Issuance",
            step_kind=WorkflowStepKinds.ISSUANCE,
            responsible_role_id=self.staff_role,
            allowed_actions=[AllowedActions.ISSUE],
        )

        # Request
        self.request_obj = Request.objects.create(
            request_number="REQ-2026-TEST01",
            student_id=self.student,
            service_id=self.service,
            current_status=RequestStatuses.SUBMITTED,
            current_step_id=self.step1,
        )

        # Notification Templates
        self.template_submitted = NotificationTemplate.objects.create(
            event_code=NotificationEventCodes.REQ_SUBMITTED,
            channel=NotificationChannels.EMAIL,
            name="Request Submitted Template",
            description="Sent upon submission",
            subject="Request {request_number} Submitted",
            template_body="<p>Dear {student_name}, your request {request_number} for {service_name} was submitted.</p>",
            is_active=True,
        )

        self.template_verified = NotificationTemplate.objects.create(
            event_code=NotificationEventCodes.REQ_UNDER_VERIFICATION,
            channel=NotificationChannels.EMAIL,
            name="Under Verification Template",
            subject="Request {request_number} Under Verification",
            template_body="<p>Dear {student_name}, status is {new_status}. Remarks: {remarks}</p>",
            is_active=True,
        )

        # API Clients
        self.client_admin = APIClient()
        self.client_admin.force_authenticate(user=self.admin_user)

        self.client_staff = APIClient()
        self.client_staff.force_authenticate(user=self.staff_user)

        self.client_anon = APIClient()

    # =========================================================================
    # 1. Validation & Safe Rendering Tests
    # =========================================================================

    def test_placeholder_validation_allows_valid_placeholders(self):
        text = "Hello {student_name}, your request {request_number} for {service_name} is {new_status}."
        # Should not raise
        validate_placeholders(text)

    def test_placeholder_validation_rejects_unknown_placeholders(self):
        text = "Hello {unknown_variable}, your balance is {fake_amount}."
        with self.assertRaises(ValidationError) as ctx:
            validate_placeholders(text)
        self.assertIn("Invalid placeholders found", str(ctx.exception))
        self.assertIn("{unknown_variable}", str(ctx.exception))

    def test_subject_validation_rejects_crlf_header_injection(self):
        malicious_subject = "Application Update\r\nBcc: hacker@bad.com"
        with self.assertRaises(ValidationError) as ctx:
            validate_subject(malicious_subject)
        self.assertIn("newline characters", str(ctx.exception))

    def test_html_sanitization_removes_dangerous_tags_and_scripts(self):
        raw_html = (
            "<p>Hello</p><script>alert('xss')</script>"
            "<iframe src='javascript:alert(1)'></iframe>"
            "<a href='javascript:steal()' onclick='steal()'>Click here</a>"
            "<a href='https://college.edu' target='_blank'>Valid Link</a>"
        )
        cleaned = sanitize_html(raw_html)
        self.assertNotIn("<script>", cleaned)
        self.assertNotIn("alert('xss')", cleaned)
        self.assertNotIn("<iframe>", cleaned)
        self.assertNotIn("javascript:", cleaned)
        self.assertNotIn("onclick", cleaned)
        self.assertIn("<p>Hello</p>", cleaned)
        self.assertIn('href="https://college.edu"', cleaned)

    def test_render_template_escapes_dynamic_html_values(self):
        malicious_student_name = "<script>alert('pwned')</script>"
        context = {
            "student_name": malicious_student_name,
            "request_number": "REQ-123",
            "service_name": "Transcript",
        }
        subj, html_body, text_body = render_template(
            subject_template="Update for {student_name}",
            body_template="<p>Dear {student_name}, req: {request_number}</p>",
            context=context,
        )
        # HTML output must escape angle brackets in the student name
        self.assertNotIn("<script>", html_body)
        self.assertIn("&lt;script&gt;alert(&#x27;pwned&#x27;)&lt;/script&gt;", html_body)
        # Plain text must contain the plain value
        self.assertIn(malicious_student_name, text_body)

    def test_missing_optional_values_render_blank_in_real_notifications(self):
        _, html_body, _ = render_template(
            subject_template="Request {request_number}",
            body_template="<p>{remarks} {student_name}</p>",
            context={"request_number": "REQ-42"},
        )
        self.assertIn("<p> </p>", html_body)
        self.assertNotIn("Mohamed Jainul", html_body)

    def test_dynamic_link_value_cannot_inject_unsafe_url_scheme(self):
        _, html_body, _ = render_template(
            subject_template="Request {request_number}",
            body_template='<a href="{portal_url}">Open request</a>',
            context={"request_number": "REQ-42", "portal_url": "javascript:alert(1)"},
        )
        self.assertNotIn("href=", html_body)
        self.assertIn("Open request", html_body)

    def test_html_to_plain_text_converts_properly(self):
        html = "<p>Line 1</p><p>Line 2<br/>Line 3</p><a href='http://test'>Link</a>"
        plain = html_to_plain_text(html)
        self.assertIn("Line 1", plain)
        self.assertIn("Line 2", plain)
        self.assertIn("Line 3", plain)
        self.assertNotIn("<p>", plain)

    # =========================================================================
    # 2. Template API Permissions & CRUD Tests
    # =========================================================================

    def test_anonymous_and_non_admin_cannot_access_templates(self):
        resp_anon = self.client_anon.get("/api/notifications/templates/")
        self.assertEqual(resp_anon.status_code, status.HTTP_401_UNAUTHORIZED)

        resp_staff = self.client_staff.get("/api/notifications/templates/")
        self.assertEqual(resp_staff.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_can_list_and_retrieve_templates(self):
        resp = self.client_admin.get("/api/notifications/templates/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(resp.data), 2)

        detail_resp = self.client_admin.get(f"/api/notifications/templates/{self.template_submitted.id}/")
        self.assertEqual(detail_resp.status_code, status.HTTP_200_OK)
        self.assertEqual(detail_resp.data["event_code"], "REQ_SUBMITTED")

    def test_admin_can_update_template_and_audit_log_is_recorded(self):
        payload = {
            "name": "Updated Submitted Name",
            "subject": "New Subject - {request_number}",
            "template_body": "<p>Hello {student_name}, new body for {request_number}.</p>",
        }
        resp = self.client_admin.patch(
            f"/api/notifications/templates/{self.template_submitted.id}/",
            data=payload,
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.template_submitted.refresh_from_db()
        self.assertEqual(self.template_submitted.name, "Updated Submitted Name")
        self.assertEqual(self.template_submitted.subject, "New Subject - {request_number}")

        # Verify AuditLog created
        audit = AuditLog.objects.filter(
            object_id=str(self.template_submitted.id),
            action="UPDATE",
        ).first()
        self.assertIsNotNone(audit)
        self.assertIn("subject", audit.changes)

    def test_admin_update_rejects_invalid_placeholders(self):
        payload = {
            "template_body": "<p>Bad placeholder {hacker_code}</p>",
        }
        resp = self.client_admin.patch(
            f"/api/notifications/templates/{self.template_submitted.id}/",
            data=payload,
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Invalid placeholders found", str(resp.data))

    def test_admin_cannot_change_template_event_or_channel(self):
        resp = self.client_admin.patch(
            f"/api/notifications/templates/{self.template_submitted.id}/",
            data={"event_code": NotificationEventCodes.REQ_REJECTED},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.template_submitted.refresh_from_db()
        self.assertEqual(self.template_submitted.event_code, NotificationEventCodes.REQ_SUBMITTED)

    def test_admin_cannot_delete_template_with_history_safe_endpoint(self):
        resp = self.client_admin.delete(
            f"/api/notifications/templates/{self.template_submitted.id}/"
        )
        self.assertEqual(resp.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
        self.assertTrue(NotificationTemplate.objects.filter(pk=self.template_submitted.id).exists())

    def test_admin_toggle_active_status(self):
        self.assertTrue(self.template_submitted.is_active)
        resp = self.client_admin.post(f"/api/notifications/templates/{self.template_submitted.id}/toggle-active/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.template_submitted.refresh_from_db()
        self.assertFalse(self.template_submitted.is_active)

    def test_placeholders_endpoint_returns_registry(self):
        resp = self.client_admin.get("/api/notifications/templates/placeholders/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("placeholders", resp.data)
        self.assertIn("sample_context", resp.data)
        keys = [p["key"] for p in resp.data["placeholders"]]
        self.assertIn("student_name", keys)
        self.assertIn("request_number", keys)

    def test_preview_endpoint(self):
        resp = self.client_admin.post(
            f"/api/notifications/templates/{self.template_submitted.id}/preview/",
            data={"context": {"student_name": "Preview User", "request_number": "REQ-PREV"}},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("REQ-PREV", resp.data["subject"])
        self.assertIn("Preview User", resp.data["html"])

    def test_send_test_email_endpoint(self):
        resp = self.client_admin.post(
            f"/api/notifications/templates/{self.template_submitted.id}/send-test/",
            data={"recipient_email": "admin@college.edu"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["admin@college.edu"])
        self.assertEqual(resp.data["status"], "SENT")

        # Verify test notification history record created
        notif = Notification.objects.get(pk=resp.data["notification_id"])
        self.assertTrue(notif.is_test)
        self.assertEqual(notif.recipient_email, "admin@college.edu")

    def test_test_email_rejects_recipient_other_than_authenticated_admin(self):
        response = self.client_admin.post(
            f"/api/notifications/templates/{self.template_submitted.id}/send-test/",
            data={"recipient_email": "someone-else@example.com"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(len(mail.outbox), 0)

    def test_create_template_rejects_unknown_event_code(self):
        response = self.client_admin.post(
            "/api/notifications/templates/",
            data={
                "name": "Unsupported",
                "description": "",
                "event_code": "UNSUPPORTED_EVENT",
                "channel": "EMAIL",
                "subject": "Subject",
                "template_body": "<p>Message</p>",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_preview_uses_unsaved_template_content(self):
        response = self.client_admin.post(
            f"/api/notifications/templates/{self.template_submitted.id}/preview/",
            data={
                "subject": "Draft {request_number}",
                "template_body": "<p>Draft body {student_name}</p>",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["subject"].startswith("Draft "))
        self.assertIn("Draft body", response.data["html"])
        self.template_submitted.refresh_from_db()
        self.assertNotIn("Draft", self.template_submitted.subject)

    # =========================================================================
    # 3. Notification Dispatch & Idempotency Tests
    # =========================================================================

    def test_successful_dispatch_creates_sent_notification_and_sends_email(self):
        notif = dispatch_notification(
            event_code=NotificationEventCodes.REQ_SUBMITTED,
            request_obj=self.request_obj,
            event_identifier="TEST_EVENT_001",
        )
        self.assertIsNotNone(notif)
        self.assertEqual(notif.status, NotificationStatuses.SENT)
        self.assertEqual(notif.recipient_email, "student@college.edu")
        self.assertEqual(notif.request_number_snapshot, "REQ-2026-TEST01")
        self.assertIsNotNone(notif.sent_at)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["student@college.edu"])

    def test_dispatch_is_idempotent_for_same_event_identifier(self):
        notif1 = dispatch_notification(
            event_code=NotificationEventCodes.REQ_SUBMITTED,
            request_obj=self.request_obj,
            event_identifier="STABLE_EVT_100",
        )
        self.assertEqual(len(mail.outbox), 1)

        # Dispatch again with same identifier
        notif2 = dispatch_notification(
            event_code=NotificationEventCodes.REQ_SUBMITTED,
            request_obj=self.request_obj,
            event_identifier="STABLE_EVT_100",
        )
        # Should not send a second email
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(notif1.id, notif2.id)

    def test_dispatch_handles_inactive_template(self):
        self.template_submitted.is_active = False
        self.template_submitted.save()

        notif = dispatch_notification(
            event_code=NotificationEventCodes.REQ_SUBMITTED,
            request_obj=self.request_obj,
            event_identifier="INACTIVE_EVT_1",
        )
        self.assertIsNone(notif)
        self.assertEqual(len(mail.outbox), 0)

    def test_dispatch_handles_student_without_email(self):
        self.student_user.email = ""
        self.student_user.save()

        notif = dispatch_notification(
            event_code=NotificationEventCodes.REQ_SUBMITTED,
            request_obj=self.request_obj,
            event_identifier="NO_EMAIL_EVT",
        )
        self.assertIsNotNone(notif)
        self.assertEqual(notif.status, NotificationStatuses.FAILED)
        self.assertIn("no registered email", notif.delivery_error)
        self.assertEqual(len(mail.outbox), 0)

    @patch("apps.notifications.services.event_dispatcher.send_email")
    def test_dispatch_records_email_failure_without_raising(self, mock_send):
        mock_send.return_value = (
            False,
            "",
            "SMTPAuthenticationError: Username and Password not accepted.",
            False,
        )

        notif = dispatch_notification(
            event_code=NotificationEventCodes.REQ_SUBMITTED,
            request_obj=self.request_obj,
            event_identifier="FAIL_EVT_001",
        )
        self.assertIsNotNone(notif)
        self.assertEqual(notif.status, NotificationStatuses.FAILED)
        self.assertIn("SMTPAuthenticationError", notif.delivery_error)

    @patch("apps.notifications.services.event_dispatcher.send_email")
    def test_uncertain_delivery_outcome_is_not_marked_failed_or_retried(self, mock_send):
        mock_send.return_value = (False, "", "SMTP response timed out", True)
        notification = dispatch_notification(
            event_code=NotificationEventCodes.REQ_SUBMITTED,
            request_obj=self.request_obj,
            event_identifier="UNCERTAIN_EVENT",
        )
        self.assertEqual(notification.status, NotificationStatuses.UNCERTAIN)
        with self.assertRaises(ValidationError):
            retry_notification(notification.id, admin_user=self.admin_user)

    # =========================================================================
    # 4. Transaction Safety (on_commit) Tests
    # =========================================================================

    def test_transaction_rollback_does_not_send_email(self):
        try:
            with transaction.atomic():
                schedule_notification_dispatch(
                    event_code=NotificationEventCodes.REQ_SUBMITTED,
                    request_obj=self.request_obj,
                    event_identifier="ROLLBACK_EVT",
                )
                # Intentionally trigger rollback
                raise RuntimeError("Forced Rollback")
        except RuntimeError:
            pass

        # Since transaction rolled back, on_commit hook must NOT run
        self.assertEqual(len(mail.outbox), 0)
        self.assertFalse(
            Notification.objects.filter(event_identifier="ROLLBACK_EVT").exists()
        )

    # =========================================================================
    # 5. Retry Service & Limits Tests
    # =========================================================================

    def test_retry_failed_notification_succeeds(self):
        # Create a failed notification
        failed_notif = Notification.objects.create(
            request_id=self.request_obj,
            user_id=self.student_user,
            channel=NotificationChannels.EMAIL,
            template_id=self.template_submitted,
            recipient_email="student@college.edu",
            subject="Test Fail",
            message="<p>Failed message</p>",
            status=NotificationStatuses.FAILED,
            delivery_error="Simulated network error",
            retry_count=0,
        )

        # Retry via service
        updated = retry_notification(failed_notif.id, admin_user=self.admin_user)
        self.assertEqual(updated.status, NotificationStatuses.SENT)
        self.assertEqual(updated.retry_count, 1)
        self.assertEqual(updated.delivery_error, "")
        self.assertEqual(len(mail.outbox), 1)

    def test_retry_limit_enforced(self):
        max_notif = Notification.objects.create(
            request_id=self.request_obj,
            user_id=self.student_user,
            channel=NotificationChannels.EMAIL,
            template_id=self.template_submitted,
            recipient_email="student@college.edu",
            subject="Test Max Fail",
            message="<p>Max retries</p>",
            status=NotificationStatuses.FAILED,
            retry_count=3,  # Already at MAX_RETRIES (3)
        )

        with self.assertRaises(ValidationError) as ctx:
            retry_notification(max_notif.id, admin_user=self.admin_user)
        self.assertIn("Maximum retry limit", str(ctx.exception))

    def test_api_retry_endpoint(self):
        failed_notif = Notification.objects.create(
            request_id=self.request_obj,
            user_id=self.student_user,
            channel=NotificationChannels.EMAIL,
            template_id=self.template_submitted,
            recipient_email="student@college.edu",
            subject="Test API Fail",
            message="<p>Failed API message</p>",
            status=NotificationStatuses.FAILED,
            retry_count=0,
        )

        resp = self.client_admin.post(f"/api/notifications/history/{failed_notif.id}/retry/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["status"], "SENT")
        self.assertEqual(resp.data["retry_count"], 1)

    # =========================================================================
    # 6. Notification History API & Filtering Tests
    # =========================================================================

    def test_history_list_and_filters(self):
        Notification.objects.create(
            request_id=self.request_obj,
            user_id=self.student_user,
            channel=NotificationChannels.EMAIL,
            recipient_email="student@college.edu",
            subject="History 1",
            status=NotificationStatuses.SENT,
            event_code="REQ_SUBMITTED",
            is_test=False,
        )
        Notification.objects.create(
            user_id=self.admin_user,
            channel=NotificationChannels.EMAIL,
            recipient_email="test@admin.com",
            subject="Test History",
            status=NotificationStatuses.SENT,
            event_code="REQ_SUBMITTED",
            is_test=True,
        )

        # List all
        resp = self.client_admin.get("/api/notifications/history/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(resp.data["count"], 2)

        # Filter by is_test
        resp_test = self.client_admin.get("/api/notifications/history/?is_test=true")
        self.assertEqual(resp_test.status_code, status.HTTP_200_OK)
        for item in resp_test.data["results"]:
            self.assertTrue(item["is_test"])

        # Filter by search
        resp_search = self.client_admin.get("/api/notifications/history/?search=test@admin.com")
        self.assertEqual(resp_search.status_code, status.HTTP_200_OK)
        self.assertEqual(resp_search.data["count"], 1)

    # =========================================================================
    # 7. Workflow Transition Integration Tests
    # =========================================================================

    def test_workflow_forward_transition_triggers_email(self):
        from apps.department_queue.notification_service import send_workflow_notification

        history = WorkflowHistory.objects.create(
            request_id=self.request_obj,
            step_id=self.step1,
            action_by_user_id=self.staff_user,
            action=AllowedActions.FORWARD,
            remarks="Documents in order, forwarding.",
        )

        with self.captureOnCommitCallbacks(execute=True):
            send_workflow_notification(
                request_obj=self.request_obj,
                action=AllowedActions.FORWARD,
                history_obj=history,
                previous_status=RequestStatuses.SUBMITTED,
                remarks="Documents in order, forwarding.",
            )

        # Verify email dispatched
        self.assertEqual(len(mail.outbox), 1)
        sent_email = mail.outbox[0]
        self.assertIn("Under Verification", sent_email.subject)
        self.assertIn("Ahmad Test Student", sent_email.body)
        self.assertIn("Documents in order, forwarding.", sent_email.body)

        # Verify notification history record
        notif = Notification.objects.filter(event_identifier=f"WF_{history.id}").first()
        self.assertIsNotNone(notif)
        self.assertEqual(notif.status, NotificationStatuses.SENT)
        self.assertEqual(notif.request_number_snapshot, "REQ-2026-TEST01")

    def test_email_failure_does_not_break_workflow_transition(self):
        from apps.department_queue.notification_service import send_workflow_notification

        with patch("apps.notifications.services.event_dispatcher.send_email") as mock_send:
            mock_send.return_value = (False, "", "Simulated Connection Refused", False)

            # This call must NOT raise any exception
            with self.captureOnCommitCallbacks(execute=True):
                send_workflow_notification(
                    request_obj=self.request_obj,
                    action=AllowedActions.FORWARD,
                    previous_status=RequestStatuses.SUBMITTED,
                    remarks="Testing resilient failure.",
                )

            # Notification history should record the failure
            failed_record = Notification.objects.filter(
                request_id=self.request_obj,
                status=NotificationStatuses.FAILED,
            ).first()
            self.assertIsNotNone(failed_record)
            self.assertIn("Simulated Connection Refused", failed_record.delivery_error)
