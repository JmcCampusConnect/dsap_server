from rest_framework import filters, viewsets
from rest_framework.permissions import IsAuthenticated

from common.pagination import StandardPagination
from .models import Student
from .permissions import IsStudentManagementAdmin   
from .serializers import StudentSerializer


class StudentViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Read‑only viewset for listing students with search, filters, and pagination.
    """
    serializer_class = StudentSerializer
    pagination_class = StandardPagination
    permission_classes = [IsStudentManagementAdmin]   

    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = [
        'register_number',
        'mobile_number',
        'name',
        'year_of_admission',
        'section',
        'stream',
        'academic_department_id__code',
        'academic_department_id__degree',
        'academic_department_id__branch',
    ]
    ordering_fields = ['register_number', 'year_of_admission', 'created_at']
    ordering = ['register_number']   

    def get_queryset(self):
        """
        Custom filtering:
        - status (exact match)
        - include_inactive to show inactive too
        - exact filters: register_number, year_of_admission, section, stream, academic_department_id
        """
        queryset = (
            Student.objects
            .select_related('user_id', 'academic_department_id')
            .all()
        )

        include_inactive = self.request.query_params.get('include_inactive', '').lower() in {'true', '1', 'yes'}
        status_filter = self.request.query_params.get('status', '').strip()

        if status_filter:
            queryset = queryset.filter(status__iexact=status_filter)
        elif not include_inactive:
            queryset = queryset.exclude(status__iexact='inactive')

        exact_filters = {
            'register_number__iexact': self.request.query_params.get('register_number', '').strip(),
            'year_of_admission__iexact': self.request.query_params.get('year_of_admission', '').strip(),
            'section__iexact': self.request.query_params.get('section', '').strip(),
            'stream__iexact': self.request.query_params.get('stream', '').strip(),
        }
        for lookup, value in exact_filters.items():
            if value:
                queryset = queryset.filter(**{lookup: value})

        department_id = self.request.query_params.get('academic_department_id', '').strip()
        if department_id:
            queryset = queryset.filter(academic_department_id_id=department_id)

        return queryset