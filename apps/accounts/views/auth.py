import time
from django.conf import settings
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
from ..serializers import CustomTokenObtainPairSerializer, ValidateTokenSerializer
from ..role_constants import get_accessible_menus, get_capabilities
from ..models import User


if settings.DEBUG:
    REFRESH_COOKIE_NAME = "refresh"
    REFRESH_COOKIE_PATH = "/"
    COOKIE_SECURE = False
else:
    REFRESH_COOKIE_NAME = "__Host-refresh"
    REFRESH_COOKIE_PATH = "/api/auth/refresh/"
    COOKIE_SECURE = True


def _set_refresh_cookie(response, refresh_token: str, max_age: int = None) -> None:
    response.set_cookie(
        REFRESH_COOKIE_NAME,
        refresh_token,
        max_age=max_age,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite="Strict",
        path=REFRESH_COOKIE_PATH,
    )


class LoginView(TokenObtainPairView):

    serializer_class = CustomTokenObtainPairSerializer
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "login"

    def post(self, request, *args, **kwargs):
        user = None
        try:
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            user = serializer.user

            refresh_token_str = serializer.validated_data.get('refresh')

            access_token = AccessToken.for_user(user)
            session_started_at = int(time.time())
            access_token['session_started_at'] = session_started_at
            access_token['role'] = user.role_name or ""

            response = Response({
                'access': str(access_token),
            }, status=status.HTTP_200_OK)

            _set_refresh_cookie(response, refresh_token_str, max_age=None)

            AuditLog.log(
                request=request,
                action='LOGIN',
                object_repr=f"User logged in" + (f" ({user.username})"),
                changes={'success': True},
                user=user
            )

            return response

        except AuthenticationFailed as e:
            raise

        except Exception as e:
            raise


class ValidateTokenView(APIView):

    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user

        if not user.is_active:
            return Response(
                {"detail": "User account is inactive"},
                status=status.HTTP_403_FORBIDDEN
            )

        access_payload = request.auth.payload
        session_started_at = access_payload.get('session_started_at')

        student = getattr(user, 'student', None)

        role_name = user.role_name or ""
        department = ""
        department_name = None
        degree = None
        branch = None
        if role_name == "STUDENT":
            academic_department = student.academic_department_id if student else user.academic_department_id
            if academic_department:
                department_name = academic_department.code
                degree = academic_department.degree
                branch = academic_department.branch
                department = ' - '.join(
                    part for part in (
                        academic_department.code,
                        academic_department.degree,
                        academic_department.branch,
                    ) if part
                )
        elif role_name in ("SYSTEM_ADMIN", "SERVICE_DEPT_ADMIN", "SERVICE_DEPT_STAFF"):
            if user.service_department_id:
                department = user.service_department_id.name

        menus = get_accessible_menus(role_name)
        capabilities = get_capabilities(role_name)

        data = {
            'username': user.username,
            'email': user.email,
            'student_name': student.name if student else None,
            'register_number': student.register_number if student else None,
            'mobile_number': student.mobile_number if student else None,
            'year_of_admission': student.year_of_admission if student else None,
            'dob': student.dob if student else None,
            'section': student.section if student else None,
            'stream': student.stream if student else None,
            'role': role_name,
            'role_id': user.role_id.id if user.role_id else None,
            'service_department_id': getattr(user.service_department_id, 'id', None) if user.service_department_id else None,
            'is_active': user.is_active,
            'department': department,
            'department_name': department_name,
            'degree': degree,
            'branch': branch,
            'menus': menus,
            'capabilities': capabilities,
            'session_started_at': session_started_at,
        }

        serializer = ValidateTokenSerializer(data=data)
        serializer.is_valid(raise_exception=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


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
            response = Response({"detail": str(e)}, status=status.HTTP_401_UNAUTHORIZED)
            response.delete_cookie(REFRESH_COOKIE_NAME, path=REFRESH_COOKIE_PATH)
            return response

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

        session_started_at = old_token.payload.get('session_started_at')

        try:
            new_refresh = CustomRefreshToken.for_user(user, session_started_at=session_started_at)
        except Exception:
            response = Response(
                {"detail": "Refresh token reuse detected.", "code": "token_reuse_detected"},
                status=status.HTTP_401_UNAUTHORIZED
            )
            response.delete_cookie(REFRESH_COOKIE_NAME, path=REFRESH_COOKIE_PATH)
            return response

        try:
            old_token.blacklist()
        except TokenError:
            response = Response(
                {"detail": "Refresh token reuse detected.", "code": "token_reuse_detected"},
                status=status.HTTP_401_UNAUTHORIZED
            )
            response.delete_cookie(REFRESH_COOKIE_NAME, path=REFRESH_COOKIE_PATH)
            return response

        new_access = AccessToken.for_user(user)
        new_access['session_started_at'] = session_started_at
        new_access['role'] = user.role_name or ""

        response = Response({"accessToken": str(new_access)}, status=status.HTTP_200_OK)
        _set_refresh_cookie(response, str(new_refresh), max_age=None)
        return response


class LogoutView(APIView):

    permission_classes = []

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
                pass

        AuditLog.log(
            request=request,
            action='LOGOUT',
            object_repr=f"User logged out" + (f" ({user.username})"),
            changes={'user_id': user.id}
        )

        response = Response({"detail": "Logged out."}, status=status.HTTP_200_OK)
        response.delete_cookie(REFRESH_COOKIE_NAME, path=REFRESH_COOKIE_PATH)
        return response


class LogoutAllView(APIView):

    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user

        tokens = OutstandingToken.objects.filter(user=user, blacklistedtoken__isnull=True)
        count = tokens.count()

        for token in tokens:
            BlacklistedToken.objects.get_or_create(token=token)

        AuditLog.log(
            request=request,
            action='LOGOUT',
            object_repr=f"User logged out from all sessions ({user.username})",
            changes={'user_id': user.id, 'sessions_logged_out': count}
        )

        response = Response(
            {'detail': f'All {count} sessions logged out successfully'},
            status=status.HTTP_200_OK
        )
        response.delete_cookie(REFRESH_COOKIE_NAME, path=REFRESH_COOKIE_PATH)
        return response