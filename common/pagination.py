from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response


class StandardPagination(PageNumberPagination):
    
    page_size = 10
    page_size_query_param = "page_size"
    max_page_size = 100
    page_query_param = "page"

    def get_paginated_response(self, data):
        return Response(
            {
                "count": self.page.paginator.count,
                "next": self.get_next_link(),
                "previous": self.get_previous_link(),
                "results": data,
            }
        )

    def get_paginated_response_schema(self, schema):
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