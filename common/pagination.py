from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response


class StandardPagination(PageNumberPagination):
    page_size = 100
    page_size_query_param = "page_size"
    max_page_size = 1000
    page_query_param = "page"

    def get_paginated_response(self, data):
        return Response(
            {
                "count": self.page.paginator.count,
                "next": self.get_next_link(),
                "previous": self.get_previous_link(),
                "page": self.page.number,
                "page_size": self.get_page_size(self.request),
                "total_pages": self.page.paginator.num_pages,
                "results": data,
            }
        )

    def get_paginated_response_schema(self, schema):
        return {
            "type": "object",
            "required": ["count", "page", "page_size", "total_pages", "results"],
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
                "page": {
                    "type": "integer",
                    "description": "The current page number.",
                },
                "page_size": {
                    "type": "integer",
                    "description": "The number of records returned per page.",
                },
                "total_pages": {
                    "type": "integer",
                    "description": "The total number of pages in the filtered result.",
                },
                "results": schema,
            },
        }