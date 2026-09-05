import time
from django.conf import settings
from django.utils import timezone
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.tokens import RefreshToken, AccessToken
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.token_blacklist.models import OutstandingToken, BlacklistedToken

from apps.accounts.tokens import CustomRefreshToken
from apps.audit.models import AuditLog
from ..serializers import CustomTokenObtainPairSerializer, ValidateTokenSerializer, LogoutSerializer
from ..role_constants import get_accessible_menus
from ..models import User


# ----------------------------------------------------------------------
# Conditional cookie configuration based on environment
# ----------------------------------------------------------------------
if settings.DEBUG:
    REFRESH_COOKIE_NAME = "refresh"
    REFRESH_COOKIE_PATH = "/"
    COOKIE_SECURE = False
else:
    REFRESH_COOKIE_NAME = "__Host-refresh"
    REFRESH_COOKIE_PATH = "/api/auth/refresh/"
    COOKIE_SECURE = True


# ----------------------------------------------------------------------
# Helper: set refresh cookie
# ----------------------------------------------------------------------
def _set_refresh_cookie(response, refresh_token: str, max_age: int = None) -> None:
    """Set the HTTP‑only refresh cookie with __Host- prefix."""
    response.set_cookie(
        REFRESH_COOKIE_NAME,
        refresh_token,
        max_age=max_age,                # None → session cookie
        httponly=True,
        secure=COOKIE_SECURE,
        samesite="Strict",
        path=REFRESH_COOKIE_PATH,
    )


# ----------------------------------------------------------------------
# Helper: role‑based absolute maximum lifetime
# ----------------------------------------------------------------------
def get_max_absolute_lifetime(user, remember_me: bool) -> int | None:
    """
    Returns the maximum allowed absolute session lifetime in seconds,
    or None if no limit should be enforced.
    Matches the specification (§5.6) and role_seeder.py roles.
    """
    role = user.role_name  # e.g. 'SYSTEM_ADMIN', 'STUDENT', etc.

    # Admins (both system and service department)
    if role in ('SYSTEM_ADMIN', 'SERVICE_DEPT_ADMIN'):
        return 24 * 3600  # 24 hours

    # Faculty / Staff / Teaching Staff / Service Dept Staff
    if role in ('SUBJECT_TEACHING_STAFF', 'SERVICE_DEPT_STAFF'):
        return 7 * 24 * 3600  # 7 days

    # Students
    if role == 'STUDENT':
        if remember_me:
            return 7 * 24 * 3600  # 7 days when "Remember Me" is checked
        else:
            # Spec says "session only" but we add a safety cap (30 days)
            # to prevent indefinite sessions if browser never closes.
            return 30 * 24 * 3600  # 30 days (optional but recommended)

    # Fallback: no restriction for unknown roles (should not happen)
    return None


# ----------------------------------------------------------------------
# VIEW: Login
# ----------------------------------------------------------------------
class LoginView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "login"

    def post(self, request, *args, **kwargs):
        try:
            # 1) Validate credentials via the custom serializer
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            user = serializer.user
            refresh_token_str = serializer.validated_data.get('refresh')
            remember = request.data.get('remember', False)

            # 2) Create access token with required claims
            access_token = AccessToken.for_user(user)
            session_started_at = int(time.time())
            access_token['session_started_at'] = session_started_at
            access_token['role'] = user.role_name or ""

            # 3) Prepare response with the access token
            response = Response({
                'access': str(access_token),
            }, status=status.HTTP_200_OK)

            # 4) Set refresh cookie (session or persistent)
            max_age = settings.REFRESH_COOKIE_PERSISTENT_AGE if remember else None
            _set_refresh_cookie(response, refresh_token_str, max_age=max_age)

            # 5) Audit: login success
            AuditLog.log(
                request=request,
                action='LOGIN_SUCCESS',
                object_repr=f"User {user.username} logged in",
                changes={'remember': remember}
            )

            return response

        except AuthenticationFailed as e:
            # Audit: login failure
            username = request.data.get('username', 'unknown')
            AuditLog.log(
                request=request,
                action='LOGIN_FAILURE',
                object_repr=f"Failed login for {username}",
                changes={'username': username, 'error': str(e)}
            )
            raise  # re-raise to let DRF return 401

        except Exception as e:
            # Catch‑all for unexpected errors
            AuditLog.log(
                request=request,
                action='LOGIN_FAILURE',
                object_repr="Unexpected login error",
                changes={'error': str(e)}
            )
            raise


# ----------------------------------------------------------------------
# VIEW: Validate Token (source of truth for frontend)
# ----------------------------------------------------------------------
class ValidateTokenView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user

        # Reject inactive users
        if not user.is_active:
            return Response(
                {"detail": "User account is inactive"},
                status=status.HTTP_403_FORBIDDEN
            )

        # Extract claims from the access token
        access_payload = request.auth.payload
        session_started_at = access_payload.get('session_started_at')
        token_role = access_payload.get('role')

        # (Optional) audit: role mismatch detection
        db_role = user.role_name or ""
        if token_role and token_role != db_role:
            AuditLog.log(
                request=request,
                action='VALIDATE_MISMATCH',
                object_repr=f"Role mismatch for {user.username}",
                changes={'token_role': token_role, 'db_role': db_role}
            )

        # Build department string based on the user's role
        role_name = user.role_name or ""
        department = ""
        if role_name == "STUDENT":
            if user.academic_department_id:
                department = user.academic_department_id.name
        elif role_name in ("SYSTEM_ADMIN", "SERVICE_DEPT_ADMIN", "SERVICE_DEPT_STAFF"):
            if user.service_department_id:
                department = user.service_department_id.name
        # For other roles, department remains empty

        menus = get_accessible_menus(role_name)

        data = {
            'username': user.username,
            'role': role_name,
            'role_id': user.role_id.id if user.role_id else None,
            'service_department_id': getattr(user.service_department_id, 'id', None) if user.service_department_id else None,
            'is_active': user.is_active,
            'department': department,
            'menus': menus,
            'session_started_at': session_started_at,
        }

        serializer = ValidateTokenSerializer(data=data)
        serializer.is_valid(raise_exception=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


# ----------------------------------------------------------------------
# VIEW: Refresh Token (with rotation, reuse detection, absolute cap)
# ----------------------------------------------------------------------
class CookieTokenRefreshView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        refresh_token = request.COOKIES.get(REFRESH_COOKIE_NAME)
        if not refresh_token:
            return Response(
                {"detail": "Refresh token is missing.", "code": "refresh_token_missing"},
                status=status.HTTP_401_UNAUTHORIZED
            )

        try:
            old_token = RefreshToken(refresh_token)
        except TokenError as e:
            # Invalid token – delete cookie and audit
            response = Response({"detail": str(e)}, status=status.HTTP_401_UNAUTHORIZED)
            response.delete_cookie(REFRESH_COOKIE_NAME, path=REFRESH_COOKIE_PATH)

            AuditLog.log(
                request=request,
                action='REUSE_DETECTED',
                object_repr="Invalid refresh token used",
                changes={'error': str(e)}
            )
            return response

        # Retrieve user and ensure active
        try:
            user = User.objects.get(id=old_token['user_id'])
        except User.DoesNotExist:
            response = Response({"detail": "User not found."}, status=status.HTTP_401_UNAUTHORIZED)
            response.delete_cookie(REFRESH_COOKIE_NAME, path=REFRESH_COOKIE_PATH)
            return response

        if not user.is_active:
            response = Response({"detail": "User account is inactive."}, status=status.HTTP_403_FORBIDDEN)
            response.delete_cookie(REFRESH_COOKIE_NAME, path=REFRESH_COOKIE_PATH)
            return response

        # ----- Enforce absolute session age (role‑based) -----
        session_started_at = old_token.payload.get('session_started_at')
        remember_me = old_token.payload.get('remember_me', False)

        if session_started_at:
            max_lifetime = get_max_absolute_lifetime(user, remember_me)
            if max_lifetime is not None:
                elapsed = timezone.now().timestamp() - session_started_at
                if elapsed > max_lifetime:
                    # Blacklist the old token to clean up
                    try:
                        old_token.blacklist()
                    except TokenError:
                        pass  # already blacklisted

                    response = Response(
                        {"detail": "Session exceeded maximum allowed lifetime. Please log in again."},
                        status=status.HTTP_401_UNAUTHORIZED
                    )
                    response.delete_cookie(REFRESH_COOKIE_NAME, path=REFRESH_COOKIE_PATH)
                    return response

        # ----- Create new refresh token (custom) preserving claims -----
        try:
            new_refresh = CustomRefreshToken.for_user(user, session_started_at=session_started_at)
            new_refresh.payload['remember_me'] = remember_me
        except Exception:
            # If token reuse is detected, CustomRefreshToken may raise
            response = Response(
                {"detail": "Refresh token reuse detected.", "code": "token_reuse_detected"},
                status=status.HTTP_401_UNAUTHORIZED
            )
            response.delete_cookie(REFRESH_COOKIE_NAME, path=REFRESH_COOKIE_PATH)

            AuditLog.log(
                request=request,
                action='REUSE_DETECTED',
                object_repr=f"Reuse detected for user {user.username}",
                changes={'user_id': user.id}
            )
            return response

        # Blacklist the old token (rotation)
        try:
            old_token.blacklist()
        except TokenError:
            # Already blacklisted – treat as reuse
            response = Response(
                {"detail": "Refresh token reuse detected.", "code": "token_reuse_detected"},
                status=status.HTTP_401_UNAUTHORIZED
            )
            response.delete_cookie(REFRESH_COOKIE_NAME, path=REFRESH_COOKIE_PATH)

            AuditLog.log(
                request=request,
                action='REUSE_DETECTED',
                object_repr=f"Reuse detected (already blacklisted) for {user.username}",
                changes={'user_id': user.id}
            )
            return response

        # ----- Create new access token with claims -----
        new_access = AccessToken.for_user(user)
        new_access['session_started_at'] = session_started_at
        new_access['role'] = user.role_name or ""

        # ----- Build response with new cookie -----
        response = Response({"accessToken": str(new_access)}, status=status.HTTP_200_OK)
        max_age = settings.REFRESH_COOKIE_PERSISTENT_AGE if remember_me else None
        _set_refresh_cookie(response, str(new_refresh), max_age=max_age)

        # Audit: successful refresh
        AuditLog.log(
            request=request,
            action='REFRESH',
            object_repr=f"Token refreshed for {user.username}",
            changes={'user_id': user.id}
        )

        return response


# ----------------------------------------------------------------------
# VIEW: Logout (always returns 200 to avoid oracle)
# ----------------------------------------------------------------------
class LogoutView(APIView):
    permission_classes = []   # AllowAny (no auth required)

    def post(self, request):
        refresh_token = request.COOKIES.get(REFRESH_COOKIE_NAME)
        user = None

        if refresh_token:
            try:
                token = RefreshToken(refresh_token)
                user_id = token.payload.get('user_id')
                if user_id:
                    user = User.objects.filter(id=user_id).first()
                token.blacklist()
            except Exception:
                pass  # ignore errors – just delete the cookie

        # Audit: always log the attempt
        AuditLog.log(
            request=request,
            action='LOGOUT',
            object_repr=f"User logged out" + (f" ({user.username})" if user else ""),
            changes={'user_id': user.id if user else None}
        )

        response = Response({"detail": "Logged out."}, status=status.HTTP_200_OK)
        response.delete_cookie(REFRESH_COOKIE_NAME, path=REFRESH_COOKIE_PATH)
        return response

# ----------------------------------------------------------------------
# VIEW: Logout All Devices
# ----------------------------------------------------------------------
class LogoutAllView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user

        # Only blacklist tokens that are not already blacklisted
        tokens = OutstandingToken.objects.filter(user=user, blacklistedtoken__isnull=True)
        count = tokens.count()

        for token in tokens:
            BlacklistedToken.objects.get_or_create(token=token)

        # Audit
        AuditLog.log(
            request=request,
            action='LOGOUT_ALL',
            object_repr=f"User {user.username} logged out from all devices",
            changes={'revoked_count': count}
        )

        response = Response(
            {'detail': f'All {count} sessions logged out successfully'},
            status=status.HTTP_200_OK
        )
        response.delete_cookie(REFRESH_COOKIE_NAME, path=REFRESH_COOKIE_PATH)
        return response