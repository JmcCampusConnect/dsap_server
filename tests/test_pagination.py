from django.test import SimpleTestCase
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory

from common.pagination import StandardPagination


class StandardPaginationTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()

    def test_default_page_size_and_metadata(self):
        paginator = StandardPagination()
        request = Request(self.factory.get("/items/?page=2"))

        page = paginator.paginate_queryset(list(range(250)), request)
        response = paginator.get_paginated_response(page)

        self.assertEqual(len(response.data["results"]), 100)
        self.assertEqual(response.data["count"], 250)
        self.assertEqual(response.data["page"], 2)
        self.assertEqual(response.data["page_size"], 100)
        self.assertEqual(response.data["total_pages"], 3)
        self.assertIsNotNone(response.data["previous"])
        self.assertIsNotNone(response.data["next"])

    def test_requested_page_size_is_capped_at_one_thousand(self):
        paginator = StandardPagination()
        request = Request(self.factory.get("/items/?page_size=1500"))

        page = paginator.paginate_queryset(list(range(1205)), request)
        response = paginator.get_paginated_response(page)

        self.assertEqual(len(response.data["results"]), 1000)
        self.assertEqual(response.data["count"], 1205)
        self.assertEqual(response.data["page_size"], 1000)
        self.assertEqual(response.data["total_pages"], 2)
