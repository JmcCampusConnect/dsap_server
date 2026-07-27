from rest_framework import viewsets, status
from rest_framework.response import Response

from apps.departments.models import ServiceDepartment
from apps.departments.serializers.service_department import ServiceDepartmentSerializer


class ServiceDepartmentViewSet(viewsets.ModelViewSet):
    queryset = ServiceDepartment.objects.all()
    serializer_class = ServiceDepartmentSerializer

    def destroy(self, request, *args, **kwargs):
        """
        Soft delete (Deactivate) the department.
        """

        department = self.get_object()
        department.status = "INACTIVE"
        department.save()

        return Response(
            {"message": "Service Department deactivated successfully."},
            status=status.HTTP_200_OK
        )