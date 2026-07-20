from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from .views import UserViewSet, LoginView, LogoutView

router = DefaultRouter()
router.register(r"users", UserViewSet, basename="users")

app_name = 'accounts'

urlpatterns = [
    path('auth/login/', LoginView.as_view(), name='login'),
    path('auth/refresh/', TokenRefreshView.as_view(), name='refresh'), 
    path('auth/logout/', LogoutView.as_view(), name='logout'),
]
