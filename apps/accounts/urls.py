from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView

from .views import UserViewSet, LoginView, LogoutView



router = DefaultRouter()
router.register(r"users", UserViewSet, basename="users")


# apps/accounts/urls.py




app_name = 'accounts'

urlpatterns = [
    # JWT auth endpoints
    path("", include(router.urls)),
    path('auth/login/', LoginView.as_view(), name='login'),
    path('auth/refresh/', TokenRefreshView.as_view(), name='refresh'),   # built-in is fine
    path('auth/logout/', LogoutView.as_view(), name='logout'),

    # (Keep your existing User/UserRole ViewSet routes if any – but they might be in a different urlconf)
]
