from django.test import RequestFactory, SimpleTestCase
from rest_framework.test import APIClient

from apps.accounts.views.auth import REFRESH_COOKIE_NAME, _get_refresh_cookie_name


class TabAuthCookieTests(SimpleTestCase):
    def test_tab_ids_select_independent_refresh_cookies(self):
        request_factory = RequestFactory()
        first_tab = _get_refresh_cookie_name(
            request_factory.get("/", HTTP_X_AUTH_TAB_ID="a" * 32)
        )
        second_tab = _get_refresh_cookie_name(
            request_factory.get("/", HTTP_X_AUTH_TAB_ID="b" * 32)
        )

        self.assertNotEqual(first_tab, second_tab)

    def test_tab_refresh_does_not_fall_back_to_legacy_shared_cookie(self):
        client = APIClient()
        client.cookies[REFRESH_COOKIE_NAME] = "legacy-shared-refresh-token"

        response = client.post(
            "/api/auth/refresh/",
            {},
            format="json",
            HTTP_X_AUTH_TAB_ID="a" * 32,
        )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.data["code"], "refresh_token_missing")
