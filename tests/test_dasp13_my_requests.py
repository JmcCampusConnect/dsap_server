from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient
from apps.accounts.models import User
from apps.requests.models import Request


class MyRequestsEndpointTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        # Run all prerequisite seeders in order
        from seeders.runner import SEEDERS, run_seeder
        for s in SEEDERS:
            run_seeder(s)

    def setUp(self):
        self.client = APIClient()
        self.student_user_66 = User.objects.get(username="24MCA066")
        self.student_user_57 = User.objects.get(username="24MCA057")
        self.staff_user = User.objects.get(username="COE_STAFF")

    def test_list_requests_authenticated_student(self):
        self.client.force_authenticate(user=self.student_user_66)
        response = self.client.get("/api/requests/my/", HTTP_HOST="localhost")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data.get("results", response.data)
        self.assertEqual(len(results), 7)
        # Ensure requests belong only to student 66
        req_numbers = [r["request_number"] for r in results]
        self.assertIn("REQ-2026-0001", req_numbers)
        self.assertNotIn("REQ-2026-0099", req_numbers)

    def test_stats_counts(self):
        self.client.force_authenticate(user=self.student_user_66)
        response = self.client.get("/api/requests/my/stats/", HTTP_HOST="localhost")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["total"], 7)
        self.assertEqual(response.data["DRAFT"], 1)
        self.assertEqual(response.data["SUBMITTED"], 1)
        self.assertEqual(response.data["UNDER_VERIFICATION"], 1)
        self.assertEqual(response.data["APPROVED"], 1)
        self.assertEqual(response.data["COMPLETED"], 1)
        self.assertEqual(response.data["REJECTED"], 1)
        self.assertEqual(response.data["RETURNED"], 1)

    def test_status_filtering(self):
        self.client.force_authenticate(user=self.student_user_66)
        response = self.client.get("/api/requests/my/?status=UNDER_VERIFICATION", HTTP_HOST="localhost")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data.get("results", response.data)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["request_number"], "REQ-2026-0001")

    def test_search_by_request_number(self):
        self.client.force_authenticate(user=self.student_user_66)
        response = self.client.get("/api/requests/my/?search=0004", HTTP_HOST="localhost")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data.get("results", response.data)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["request_number"], "REQ-2026-0004")

    def test_request_detail(self):
        self.client.force_authenticate(user=self.student_user_66)
        req = Request.objects.get(request_number="REQ-2026-0001")
        response = self.client.get(f"/api/requests/my/{req.id}/", HTTP_HOST="localhost")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.data
        self.assertEqual(data["request_number"], "REQ-2026-0001")
        self.assertEqual(data["current_status"], "UNDER_VERIFICATION")
        self.assertEqual(data["service"]["name"], "Transcript Certificate")
        self.assertIsNotNone(data["current_step"])
        self.assertEqual(data["assigned_role"], "SERVICE_DEPT_STAFF")
        self.assertGreater(len(data["form_data"]), 0)
        self.assertGreater(len(data["documents"]), 0)
        self.assertGreater(len(data["timeline"]), 0)

    def test_request_timeline(self):
        self.client.force_authenticate(user=self.student_user_66)
        req = Request.objects.get(request_number="REQ-2026-0001")
        response = self.client.get(f"/api/requests/my/{req.id}/timeline/", HTTP_HOST="localhost")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("timeline", response.data)
        self.assertIn("history", response.data)
        self.assertIn("notifications", response.data)
        # Verify chronological ordering of action_at in history
        history = response.data["history"]
        timestamps = [h["action_at"] for h in history]
        self.assertEqual(timestamps, sorted(timestamps))

    def test_request_documents(self):
        self.client.force_authenticate(user=self.student_user_66)
        req = Request.objects.get(request_number="REQ-2026-0001")
        response = self.client.get(f"/api/requests/my/{req.id}/documents/", HTTP_HOST="localhost")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)
        doc_names = [d["document_name"] for d in response.data]
        self.assertIn("Copy of Consolidated Mark Statement", doc_names)

    def test_student_data_isolation(self):
        """Ensure student A cannot access student B's requests by ID."""
        self.client.force_authenticate(user=self.student_user_66)
        req_57 = Request.objects.get(request_number="REQ-2026-0099")

        # Detail endpoint isolation
        res_detail = self.client.get(f"/api/requests/my/{req_57.id}/", HTTP_HOST="localhost")
        self.assertEqual(res_detail.status_code, status.HTTP_404_NOT_FOUND)

        # Timeline endpoint isolation
        res_tl = self.client.get(f"/api/requests/my/{req_57.id}/timeline/", HTTP_HOST="localhost")
        self.assertEqual(res_tl.status_code, status.HTTP_404_NOT_FOUND)

        # Documents endpoint isolation
        res_docs = self.client.get(f"/api/requests/my/{req_57.id}/documents/", HTTP_HOST="localhost")
        self.assertEqual(res_docs.status_code, status.HTTP_404_NOT_FOUND)

    def test_non_student_forbidden(self):
        self.client.force_authenticate(user=self.staff_user)
        response = self.client.get("/api/requests/my/", HTTP_HOST="localhost")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_unauthenticated_unauthorized(self):
        self.client.force_authenticate(user=None)
        response = self.client.get("/api/requests/my/", HTTP_HOST="localhost")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
