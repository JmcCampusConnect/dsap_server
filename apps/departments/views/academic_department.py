from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from apps.departments.models import AcademicDepartment
from apps.departments.serializers.academic_department import AcademicDepartmentSerializer

class AcademicDepartmentViewSet(viewsets.ModelViewSet):
    """
    ViewSet for CRUD operations on AcademicDepartment.
    """
    queryset = AcademicDepartment.objects.exclude(status='INACTIVE')
    serializer_class = AcademicDepartmentSerializer

    def get_permissions(self):
        """
        Permissions:
        - Authenticated users can view (list, retrieve, options)
        - Admin users can create, update, delete
        """
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsAuthenticated(), IsAdminUser()]
        return [IsAuthenticated()]

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
        Returns choices for type and category.
        """
        types = [{"value": choice[0], "label": choice[1]} for choice in AcademicDepartment.TYPE_CHOICES]
        categories = [{"value": choice[0], "label": choice[1]} for choice in AcademicDepartment.CATEGORY_CHOICES]
        
        return Response({
            "types": types,
            "categories": categories
        })
