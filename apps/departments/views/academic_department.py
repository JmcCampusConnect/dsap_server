from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from apps.departments.models import AcademicDepartment
from apps.departments.serializers.academic_department import AcademicDepartmentSerializer

from rest_framework.permissions import AllowAny, IsAuthenticated, IsAdminUser

class AcademicDepartmentViewSet(viewsets.ModelViewSet):
    """
    ViewSet for CRUD operations on AcademicDepartment.
    """
    queryset = AcademicDepartment.objects.exclude(status='INACTIVE')
    serializer_class = AcademicDepartmentSerializer

    def get_permissions(self):
        """
        Permissions:
        - Temporarily AllowAny for testing frontend without auth.
        """
        return [AllowAny()]

    def destroy(self, request, *args, **kwargs):
        """
        Perform a soft delete by setting status to 'INACTIVE'.
        """
        instance = self.get_object()
        instance.status = 'INACTIVE'
        instance.save()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=['get'], url_path='options')
    def get_options(self, request):
        """
        Returns choices for type and category, plus distinct values for filters.
        """
        base_qs = AcademicDepartment.objects.exclude(status='INACTIVE')
        
        # Get distinct values for all dynamic dropdown filters (exclude empty/null)
        types = list(base_qs.exclude(type='').values_list('type', flat=True).distinct())
        categories = list(base_qs.exclude(category='').values_list('category', flat=True).distinct())
        codes = list(base_qs.exclude(code='').values_list('code', flat=True).distinct())
        names = list(base_qs.exclude(name='').values_list('name', flat=True).distinct())
        degrees = list(base_qs.exclude(degree='').values_list('degree', flat=True).distinct())
        branches = list(base_qs.exclude(branch='').values_list('branch', flat=True).distinct())
        
        return Response({
            "types": [{"value": x, "label": x} for x in types],
            "categories": [{"value": x, "label": x} for x in categories],
            "codes": [{"value": x, "label": x} for x in codes],
            "names": [{"value": x, "label": x} for x in names],
            "degrees": [{"value": x, "label": x} for x in degrees],
            "branches": [{"value": x, "label": x} for x in branches]
        })
