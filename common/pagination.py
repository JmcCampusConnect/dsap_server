"""
Common Pagination — Reusable pagination classes for all DSAP API modules.

Usage in any ViewSet:
    from common.pagination import StandardPagination

    class MyViewSet(viewsets.ModelViewSet):
        pagination_class = StandardPagination
        ...

The paginated response will have the shape:
    {
        "count":    <int>,      # Total number of matching records
        "next":     <url|null>, # URL of next page, or null
        "previous": <url|null>, # URL of previous page, or null
        "results":  [...]       # Items for the current page
    }

Query params accepted by the client:
    ?page=2          — request a specific page number
    ?page_size=25    — override items per page (max: MAX_PAGE_SIZE)
"""

from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response


class StandardPagination(PageNumberPagination):
    """
    Default pagination used across all listing endpoints.
    Returns 10 items per page; clients may request up to 100.
    """

    page_size = 10
    page_size_query_param = "page_size"
    max_page_size = 100
    page_query_param = "page"

    def get_paginated_response(self, data):
        """Return a consistent envelope with count, navigation links, and results."""
        return Response(
            {
                "count": self.page.paginator.count,
                "next": self.get_next_link(),
                "previous": self.get_previous_link(),
                "results": data,
            }
        )

    def get_paginated_response_schema(self, schema):
        """Extend the OpenAPI schema with pagination fields."""
        return {
            "type": "object",
            "required": ["count", "results"],
            "properties": {
                "count": {
                    "type": "integer",
                    "description": "Total number of items across all pages.",
                },
                "next": {
                    "type": "string",
                    "nullable": True,
                    "description": "URL of the next page, or null if on the last page.",
                },
                "previous": {
                    "type": "string",
                    "nullable": True,
                    "description": "URL of the previous page, or null if on the first page.",
                },
                "results": schema,
            },
        }
