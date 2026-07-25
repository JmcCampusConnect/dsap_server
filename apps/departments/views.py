from rest_framework import viewsets, status
from rest_framework.response import Response

from .models import ServiceDepartment
from .serializers import ServiceDepartmentSerializer


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