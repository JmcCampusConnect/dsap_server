from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from apps.audit.models import AuditLog


class LogoutViewTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_logout_without_refresh_cookie_succeeds(self):
        response = self.client.post('/api/auth/logout/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        log = AuditLog.objects.get(action='LOGOUT')
        self.assertEqual(log.object_repr, 'User logged out')
        self.assertEqual(log.changes, {})

    def test_logout_with_invalid_refresh_cookie_succeeds(self):
        self.client.cookies['refresh'] = 'not-a-valid-token'
        self.client.cookies['__Host-refresh'] = 'not-a-valid-token'

        response = self.client.post('/api/auth/logout/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
