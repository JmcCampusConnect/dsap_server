from django.conf import settings
from django.utils import timezone
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.throttling import ScopedRateThrottle
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.token_blacklist.models import OutstandingToken, BlacklistedToken
from rest_framework_simplejwt.tokens import AccessToken
from apps.accounts.tokens import CustomRefreshToken
from ..serializers import CustomTokenObtainPairSerializer, ValidateTokenSerializer, LogoutSerializer
from ..role_constants import get_accessible_menus
from ..models import User

REFRESH_COOKIE_NAME = "refresh_token"
REFRESH_COOKIE_PATH = "/api/auth/"
REFRESH_COOKIE_MAX_AGE = int(settings.SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"].total_seconds())


def _set_refresh_cookie(response, refresh_token: str, max_age: int = None) -> None:
    response.set_cookie(
        REFRESH_COOKIE_NAME,
        refresh_token,
        max_age=max_age,
        httponly=True,
        secure=not settings.DEBUG,
        samesite="Strict",
        path=REFRESH_COOKIE_PATH,
    )


class LoginView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "login"

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.user
        refresh_token = serializer.validated_data.get('refresh')
        access_token = serializer.validated_data.get('access')
        
        # Determine max_age based on the 'remember' field from the request data
        remember = request.data.get('remember', False)
        max_age = settings.REFRESH_COOKIE_PERSISTENT_AGE if remember else None
        
        response = Response({
            'access': access_token,
        }, status=status.HTTP_200_OK)
        
        _set_refresh_cookie(response, refresh_token, max_age=max_age)
        return response
    
class ValidateTokenView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        user = request.user
        
        # ----- Reject inactive users -----
        if not user.is_active:
            return Response(
                {"detail": "User account is inactive"},
                status=status.HTTP_403_FORBIDDEN
            )
            
        # ----- Pass role_name to get_accessible_menus -----
        role_name = user.role_name or ""
        menus = get_accessible_menus(role_name)
        
        data = {
            'username': user.username,
            'role': role_name,
            'role_id': user.role_id.id if user.role_id else None,
            'service_department_id': getattr(user.service_department_id, 'id', None) if user.service_department_id else None,
            'is_active': user.is_active,
            'menus': menus,
        }
        
        # ----- Fix serializer instantiation and call is_valid() -----
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
        
        # ----- Enforce user is_active -----
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
        
        # ----- Enforce absolute session age -----
        if hasattr(settings, 'SESSION_MAX_AGE') and settings.SESSION_MAX_AGE is not None:
            # Use the claim from the original session start
            session_started_at = old_token.payload.get('session_started_at')
            if session_started_at:
                elapsed = timezone.now().timestamp() - session_started_at
                if elapsed > settings.SESSION_MAX_AGE:
                    response = Response(
                        {"detail": "Session expired. Please log in again."},
                        status=status.HTTP_401_UNAUTHORIZED
                    )
                    response.delete_cookie(REFRESH_COOKIE_NAME, path=REFRESH_COOKIE_PATH)
                    return response
        
        # ----- Create new refresh token (custom) -----
        new_refresh = CustomRefreshToken.for_user(user)
        # Copy the critical claims from the old token
        new_refresh.copy_claim_from_old(old_token, 'session_started_at')
        new_refresh.copy_claim_from_old(old_token, 'remember_me')
        
        # Blacklist the old token (SimpleJWT's blacklist app will handle this).
        # If the old token is already blacklisted, the same token was replayed
        # after rotation — treat it as a reuse/fraud attempt instead of a 500.
        try:
            old_token.blacklist()
        except TokenError:
            response = Response(
                {"detail": "Refresh token reuse detected.", "code": "token_reuse_detected"},
                status=status.HTTP_401_UNAUTHORIZED
            )
            response.delete_cookie(REFRESH_COOKIE_NAME, path=REFRESH_COOKIE_PATH)
            return response
        
        # ----- Create new access token -----
        new_access = AccessToken.for_user(user)
        
        # ----- Build response -----
        response = Response({"accessToken": str(new_access)}, status=status.HTTP_200_OK)
        
        remember_me = new_refresh.payload.get('remember_me', False)
        max_age = settings.REFRESH_COOKIE_PERSISTENT_AGE if remember_me else None
        _set_refresh_cookie(response, str(new_refresh), max_age=max_age)
        
        return response


class LogoutView(APIView):
    permission_classes = []

    def post(self, request):
        refresh_token = request.COOKIES.get(REFRESH_COOKIE_NAME)
        serializer = LogoutSerializer(data={"refresh": refresh_token})

        if not serializer.is_valid():
            response = Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            response.delete_cookie(REFRESH_COOKIE_NAME, path=REFRESH_COOKIE_PATH)
            return response

        try:
            token = RefreshToken(serializer.validated_data["refresh"])
            token.blacklist()
            response = Response({"detail": "Logged out successfully."}, status=status.HTTP_205_RESET_CONTENT)
        except Exception as e:
            response = Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        response.delete_cookie(REFRESH_COOKIE_NAME, path=REFRESH_COOKIE_PATH)
        return response
    
class LogoutAllView(APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        user = request.user
        
        # ----- Only blacklist tokens that are not already blacklisted -----
        tokens = OutstandingToken.objects.filter(user=user, blacklistedtoken__isnull=True)
        count = tokens.count()
        for token in tokens:
            BlacklistedToken.objects.get_or_create(token=token)
            
        # ----- Delete the refresh cookie -----
        response = Response(
            {'detail': f'All {count} sessions logged out successfully'},
            status=status.HTTP_200_OK
        )
        response.delete_cookie(REFRESH_COOKIE_NAME, path=REFRESH_COOKIE_PATH)
        return response