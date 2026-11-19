from django.urls import path
from ..views import (
    LoginView,
    ValidateTokenView,
    LogoutView,
    CookieTokenRefreshView,
    LogoutAllView,
    ImpersonateView,
    ImpersonateExitView,
)

app_name = "auth"

urlpatterns = [
    path("login/", LoginView.as_view(), name="login"),
    path("validate/", ValidateTokenView.as_view(), name="validate"),
    path("refresh/", CookieTokenRefreshView.as_view(), name="refresh"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("logout-all/", LogoutAllView.as_view(), name="logout-all"),
    path("impersonate/", ImpersonateView.as_view(), name="impersonate"),
    path("impersonate/exit/", ImpersonateExitView.as_view(), name="impersonate-exit"),
]