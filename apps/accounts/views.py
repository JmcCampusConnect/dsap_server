from django.contrib.auth.models import User
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response


from .serializers import UserSerializer


class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all().order_by("id")
    serializer_class = UserSerializer

    
    def destroy(self, request, *args, **kwargs):
        user = self.get_object()

        user.is_active = False
        user.save()

        return Response(
            {"message":"User deactivated successfully."},
            status=status.HTTP_200_OK,
        )
    
    @action(detail=True, methods=["patch"])
    def reset_password(self, request, pk=None):

        user = self.get_object()

        password = request.data.get("password")

        if not password:
            return Response(
                {
                    "error": "Password is required"
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        user.set_password(password)
        user.save()

        return Response(
            {
                "message": "Password reset successfully"
            },
            status=status.HTTP_200_OK
        )
        

