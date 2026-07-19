# apps/accounts/urls.py
from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from .views import LoginView, LogoutView

app_name = 'accounts'

urlpatterns = [
    # JWT auth endpoints
    path('auth/login/', LoginView.as_view(), name='login'),
    path('auth/refresh/', TokenRefreshView.as_view(), name='refresh'),   # built-in is fine
    path('auth/logout/', LogoutView.as_view(), name='logout'),

    # (Keep your existing User/UserRole ViewSet routes if any – but they might be in a different urlconf)
]