from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.documents.models import Document
from apps.notifications.models import Notification
from apps.requests.models import Request
from apps.services.models import Service, ServiceDocument
from apps.workflow.models import WorkflowHistory, WorkflowStep


class DepartmentQueueTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        from seeders.runner import SEEDERS, run_seeder
        for s in SEEDERS:
            run_seeder(s)

    def setUp(self):
        self.client = APIClient()
        self.sysadmin = User.objects.get(username="SYSTEM_ADMIN")
        self.coe_admin = User.objects.get(username="COE_ADMIN")
        self.coe_staff = User.objects.get(username="COE_STAFF")
        self.lib_admin = User.objects.get(username="LIB_ADMIN")
        self.lib_staff = User.objects.get(username="LIB_STAFF")
        self.student_user = User.objects.get(username="24MCA066")

    # ----------------------------------------------------------------------
    # 1. Department staff can retrieve authorized queue requests
    # ----------------------------------------------------------------------
    def test_01_staff_can_retrieve_authorized_queue_requests(self):
        self.client.force_authenticate(user=self.coe_staff)
        res = self.client.get("/api/department-queue/", HTTP_HOST="localhost")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        results = res.data.get("results", res.data)
        # All requests returned must belong to COE and have current step for SERVICE_DEPT_STAFF
        self.assertTrue(len(results) > 0)
        for item in results:
            self.assertEqual(item["responsible_role"], "SERVICE_DEPT_STAFF")
            self.assertIn("request_number", item)
            self.assertIn("service_name", item)
            self.assertIn("current_status", item)

    # ----------------------------------------------------------------------
    # 2. Users cannot retrieve requests outside their department
    # ----------------------------------------------------------------------
    def test_02_users_cannot_retrieve_requests_outside_their_department(self):
        # COE request REQ-2026-0001
        coe_req = Request.objects.get(request_number="REQ-2026-0001")
        # LIB staff and LIB admin attempt to access COE request
        self.client.force_authenticate(user=self.lib_staff)
        res_staff = self.client.get(f"/api/department-queue/{coe_req.id}/", HTTP_HOST="localhost")
        self.assertEqual(res_staff.status_code, status.HTTP_403_FORBIDDEN)

        self.client.force_authenticate(user=self.lib_admin)
        res_admin = self.client.get(f"/api/department-queue/{coe_req.id}/", HTTP_HOST="localhost")
        self.assertEqual(res_admin.status_code, status.HTTP_403_FORBIDDEN)

    # ----------------------------------------------------------------------
    # 3. SYSTEM_ADMIN can access requests across departments
    # ----------------------------------------------------------------------
    def test_03_system_admin_can_access_requests_across_departments(self):
        self.client.force_authenticate(user=self.sysadmin)
        res = self.client.get("/api/department-queue/", HTTP_HOST="localhost")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        results = res.data.get("results", res.data)
        self.assertTrue(len(results) >= 5)

        # Can access detail of COE request
        coe_req = Request.objects.get(request_number="REQ-2026-0001")
        detail_res = self.client.get(f"/api/department-queue/{coe_req.id}/", HTTP_HOST="localhost")
        self.assertEqual(detail_res.status_code, status.HTTP_200_OK)
        self.assertEqual(detail_res.data["request_number"], "REQ-2026-0001")

    # ----------------------------------------------------------------------
    # 4. Users cannot act on workflow steps they are not authorized to handle
    # ----------------------------------------------------------------------
    def test_04_users_cannot_act_on_unauthorized_workflow_steps(self):
        # REQ-2026-0002 is at Step 3 (responsible role: SERVICE_DEPT_ADMIN)
        req_admin_step = Request.objects.get(request_number="REQ-2026-0002")
        self.client.force_authenticate(user=self.coe_staff)
        # Staff attempting forward on admin step
        res = self.client.post(
            f"/api/department-queue/{req_admin_step.id}/forward/",
            data={"remarks": "Staff trying to forward admin step"},
            format="json",
            HTTP_HOST="localhost",
        )
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

        # COE Admin attempting forward on staff step (REQ-2026-0001, Step 1 is staff)
        req_staff_step = Request.objects.get(request_number="REQ-2026-0001")
        self.client.force_authenticate(user=self.coe_admin)
        res_admin = self.client.post(
            f"/api/department-queue/{req_staff_step.id}/forward/",
            data={"remarks": "Admin trying to forward staff step"},
            format="json",
            HTTP_HOST="localhost",
        )
        self.assertEqual(res_admin.status_code, status.HTTP_403_FORBIDDEN)

    # ----------------------------------------------------------------------
    # 5. Staff cannot final approve, reject requests, or mark requests completed
    # ----------------------------------------------------------------------
    def test_05_staff_cannot_final_approve_reject_or_complete(self):
        req = Request.objects.get(request_number="REQ-2026-0001")
        self.client.force_authenticate(user=self.coe_staff)

        # Staff trying to approve
        res_app = self.client.post(
            f"/api/department-queue/{req.id}/approve/",
            data={"remarks": "Staff approve"},
            format="json",
            HTTP_HOST="localhost",
        )
        self.assertEqual(res_app.status_code, status.HTTP_403_FORBIDDEN)

        # Staff trying to reject
        res_rej = self.client.post(
            f"/api/department-queue/{req.id}/reject/",
            data={"remarks": "Staff reject"},
            format="json",
            HTTP_HOST="localhost",
        )
        self.assertEqual(res_rej.status_code, status.HTTP_403_FORBIDDEN)

        # Staff trying to complete
        res_comp = self.client.post(
            f"/api/department-queue/{req.id}/complete/",
            data={"remarks": "Staff complete"},
            format="json",
            HTTP_HOST="localhost",
        )
        self.assertEqual(res_comp.status_code, status.HTTP_403_FORBIDDEN)

    # ----------------------------------------------------------------------
    # 6. Authorized department admins can perform their permitted actions
    # ----------------------------------------------------------------------
    def test_06_authorized_dept_admin_can_perform_permitted_actions(self):
        # REQ-2026-0002 is APPROVED at step 3 (responsible role: SERVICE_DEPT_ADMIN)
        req = Request.objects.get(request_number="REQ-2026-0002")
        self.client.force_authenticate(user=self.coe_admin)

        # Complete action
        res_complete = self.client.post(
            f"/api/department-queue/{req.id}/complete/",
            data={"remarks": "Certificate collected and issued."},
            format="json",
            HTTP_HOST="localhost",
        )
        self.assertEqual(res_complete.status_code, status.HTTP_200_OK)
        req.refresh_from_db()
        self.assertEqual(req.current_status, "COMPLETED")
        self.assertIsNotNone(req.completed_at)

    # ----------------------------------------------------------------------
    # 7. Required documents must be verified before forwarding
    # ----------------------------------------------------------------------
    def test_07_required_documents_must_be_verified_before_forwarding(self):
        # REQ-2026-0001 has 1 VERIFIED and 1 PENDING document
        req = Request.objects.get(request_number="REQ-2026-0001")
        self.client.force_authenticate(user=self.coe_staff)

        # Forward should fail because passport photo is PENDING
        res = self.client.post(
            f"/api/department-queue/{req.id}/forward/",
            data={"remarks": "Forwarding with pending docs"},
            format="json",
            HTTP_HOST="localhost",
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("unverified_documents", res.data)

        # Now verify all pending documents
        pending_docs = Document.objects.filter(request_id=req, verification_status="PENDING")
        for doc in pending_docs:
            v_res = self.client.patch(
                f"/api/department-queue/{req.id}/documents/{doc.id}/",
                data={"verification_status": "VERIFIED"},
                format="json",
                HTTP_HOST="localhost",
            )
            self.assertEqual(v_res.status_code, status.HTTP_200_OK)

        # Now forward should succeed
        res_ok = self.client.post(
            f"/api/department-queue/{req.id}/forward/",
            data={"remarks": "All documents verified. Forwarding to preparation step."},
            format="json",
            HTTP_HOST="localhost",
        )
        self.assertEqual(res_ok.status_code, status.HTTP_200_OK)
        req.refresh_from_db()
        self.assertEqual(req.current_step_id.step_order, 2)

    # ----------------------------------------------------------------------
    # 8. Invalid workflow transitions are rejected
    # ----------------------------------------------------------------------
    def test_08_invalid_workflow_transitions_rejected(self):
        # REQ-2026-0005 is COMPLETED — no actions allowed from COMPLETED
        req = Request.objects.get(request_number="REQ-2026-0005")
        self.client.force_authenticate(user=self.coe_admin)

        res = self.client.post(
            f"/api/department-queue/{req.id}/approve/",
            data={"remarks": "Trying to approve completed request"},
            format="json",
            HTTP_HOST="localhost",
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

        # Cannot complete a request that is not APPROVED
        req_sub = Request.objects.get(request_number="REQ-2026-0003")
        res_comp = self.client.post(
            f"/api/department-queue/{req_sub.id}/complete/",
            data={"remarks": "Trying to complete submitted request"},
            format="json",
            HTTP_HOST="localhost",
        )
        self.assertEqual(res_comp.status_code, status.HTTP_400_BAD_REQUEST)

    # ----------------------------------------------------------------------
    # 9. Return fails without remarks
    # ----------------------------------------------------------------------
    def test_09_return_fails_without_remarks(self):
        req = Request.objects.get(request_number="REQ-2026-0001")
        self.client.force_authenticate(user=self.coe_staff)

        # Empty string
        res_empty = self.client.post(
            f"/api/department-queue/{req.id}/return/",
            data={"remarks": ""},
            format="json",
            HTTP_HOST="localhost",
        )
        self.assertEqual(res_empty.status_code, status.HTTP_400_BAD_REQUEST)

        # Whitespace-only
        res_whitespace = self.client.post(
            f"/api/department-queue/{req.id}/return/",
            data={"remarks": "   \n\t  "},
            format="json",
            HTTP_HOST="localhost",
        )
        self.assertEqual(res_whitespace.status_code, status.HTTP_400_BAD_REQUEST)

    # ----------------------------------------------------------------------
    # 10. Reject fails without remarks
    # ----------------------------------------------------------------------
    def test_10_reject_fails_without_remarks(self):
        # REQ-2026-0001 (UNDER_VERIFICATION)
        req = Request.objects.get(request_number="REQ-2026-0001")
        self.client.force_authenticate(user=self.sysadmin)

        # Empty string
        res_empty = self.client.post(
            f"/api/department-queue/{req.id}/reject/",
            data={"remarks": ""},
            format="json",
            HTTP_HOST="localhost",
        )
        self.assertEqual(res_empty.status_code, status.HTTP_400_BAD_REQUEST)

        # Whitespace-only
        res_whitespace = self.client.post(
            f"/api/department-queue/{req.id}/reject/",
            data={"remarks": "   "},
            format="json",
            HTTP_HOST="localhost",
        )
        self.assertEqual(res_whitespace.status_code, status.HTTP_400_BAD_REQUEST)

    # ----------------------------------------------------------------------
    # 11. Valid transitions update the request's current step and status
    # ----------------------------------------------------------------------
    def test_11_valid_transitions_update_step_and_status(self):
        req = Request.objects.get(request_number="REQ-2026-0001")
        self.client.force_authenticate(user=self.coe_staff)

        res_return = self.client.post(
            f"/api/department-queue/{req.id}/return/",
            data={"remarks": "Please provide clearer certificate scans."},
            format="json",
            HTTP_HOST="localhost",
        )
        self.assertEqual(res_return.status_code, status.HTTP_200_OK)
        req.refresh_from_db()
        self.assertEqual(req.current_status, "RETURNED")

    # ----------------------------------------------------------------------
    # 12. Every successful transition creates exactly one workflow history entry
    # ----------------------------------------------------------------------
    def test_12_transition_creates_exactly_one_history_entry(self):
        req = Request.objects.get(request_number="REQ-2026-0001")
        initial_history_count = WorkflowHistory.objects.filter(request_id=req).count()
        self.client.force_authenticate(user=self.coe_staff)

        res = self.client.post(
            f"/api/department-queue/{req.id}/return/",
            data={"remarks": "Return note for audit"},
            format="json",
            HTTP_HOST="localhost",
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        new_history_count = WorkflowHistory.objects.filter(request_id=req).count()
        self.assertEqual(new_history_count, initial_history_count + 1)

        latest_entry = WorkflowHistory.objects.filter(request_id=req).order_by("-action_at").first()
        self.assertEqual(latest_entry.action, "RETURN")
        self.assertEqual(latest_entry.remarks, "Return note for audit")
        self.assertEqual(latest_entry.action_by_user_id, self.coe_staff)

    # ----------------------------------------------------------------------
    # 13. Every successful transition generates the appropriate student notification
    # ----------------------------------------------------------------------
    def test_13_transition_generates_student_notification(self):
        req = Request.objects.get(request_number="REQ-2026-0001")
        initial_notifs = Notification.objects.filter(request_id=req).count()
        self.client.force_authenticate(user=self.coe_staff)

        res = self.client.post(
            f"/api/department-queue/{req.id}/return/",
            data={"remarks": "Resubmit with correction"},
            format="json",
            HTTP_HOST="localhost",
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        new_notifs = Notification.objects.filter(request_id=req).count()
        self.assertGreater(new_notifs, initial_notifs)

        latest_notif = Notification.objects.filter(request_id=req).order_by("-created_at").first()
        self.assertEqual(latest_notif.template_id.event_code, "REQ_RETURNED")
        self.assertEqual(latest_notif.user_id, req.student_id.user_id)

    # ----------------------------------------------------------------------
    # 14. Document verification updates the correct document
    # ----------------------------------------------------------------------
    def test_14_document_verification_updates_correct_document(self):
        req = Request.objects.get(request_number="REQ-2026-0001")
        doc = Document.objects.filter(request_id=req, verification_status="PENDING").first()
        self.assertIsNotNone(doc)
        self.client.force_authenticate(user=self.coe_staff)

        # Reject document with remarks
        res = self.client.patch(
            f"/api/department-queue/{req.id}/documents/{doc.id}/",
            data={
                "verification_status": "REJECTED",
                "rejection_remarks": "Photo is blurry and not within specifications.",
            },
            format="json",
            HTTP_HOST="localhost",
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        doc.refresh_from_db()
        self.assertEqual(doc.verification_status, "REJECTED")
        self.assertEqual(doc.rejection_remarks, "Photo is blurry and not within specifications.")

    # ----------------------------------------------------------------------
    # 15. A document belonging to another request cannot be modified
    # ----------------------------------------------------------------------
    def test_15_document_belonging_to_another_request_cannot_be_modified(self):
        req_1 = Request.objects.get(request_number="REQ-2026-0001")
        req_4 = Request.objects.get(request_number="REQ-2026-0004")
        doc_4 = Document.objects.filter(request_id=req_4).first()
        self.assertIsNotNone(doc_4)

        self.client.force_authenticate(user=self.coe_staff)
        # Attempt to modify doc_4 through req_1 URL
        res = self.client.patch(
            f"/api/department-queue/{req_1.id}/documents/{doc_4.id}/",
            data={"verification_status": "VERIFIED"},
            format="json",
            HTTP_HOST="localhost",
        )
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

    # ----------------------------------------------------------------------
    # 16. History is returned in chronological order
    # ----------------------------------------------------------------------
    def test_16_history_returned_in_chronological_order(self):
        req = Request.objects.get(request_number="REQ-2026-0001")
        self.client.force_authenticate(user=self.coe_staff)

        res = self.client.get(f"/api/department-queue/{req.id}/history/", HTTP_HOST="localhost")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        history = res.data.get("history", [])
        self.assertTrue(len(history) >= 2)

        timestamps = [h["action_at"] for h in history]
        self.assertEqual(timestamps, sorted(timestamps))
