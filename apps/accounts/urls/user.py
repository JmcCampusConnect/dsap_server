from django.urls import include, path
from rest_framework.routers import DefaultRouter
from ..views import UserViewSet, RoleViewSet

app_name = "users"

router = DefaultRouter()
router.register(r"", UserViewSet, basename="users")
router.register(r"roles", RoleViewSet, basename="roles")

urlpatterns = [
    path("", include(router.urls)),
]