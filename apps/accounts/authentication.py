from django.utils import timezone
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.exceptions import AuthenticationFailed


class ImpersonationAwareJWTAuthentication(JWTAuthentication):
    """
    Extends SimpleJWT's JWTAuthentication to enforce live server-side validation
    for impersonation tokens.

    For normal (non-impersonation) tokens:
        Delegates entirely to standard SimpleJWT behavior (zero performance overhead,
        no extra database queries).

    For impersonation tokens (payload['is_impersonation'] is True):
        1. Checks that an active ImpersonationSession exists in the database.
        2. Verifies the session has not expired (session.expires_at > now).
        3. Verifies target_user_id and admin_user_id match the token claims.
        4. Verifies the admin user is still active and is still a SYSTEM_ADMIN.
        5. Verifies the impersonated target user is NOT a SYSTEM_ADMIN.
        If any check fails, raises AuthenticationFailed with code 'impersonation_ended'.
    """

    def authenticate(self, request):
        result = super().authenticate(request)
        if result is None:
            return None

        user, token = result
        payload = getattr(token, 'payload', {})
        if not payload.get('is_impersonation'):
            return result

        session_id = payload.get('impersonation_session_id')
        admin_id = payload.get('impersonator_id')

        if not session_id or not admin_id:
            raise AuthenticationFailed({
                'detail': 'Impersonation session is no longer valid.',
                'code': 'impersonation_ended',
            })

        # Lazy import to avoid circular dependency
        from apps.accounts.models import ImpersonationSession

        session = (
            ImpersonationSession.objects
            .select_related('admin_user', 'target_user')
            .filter(
                id=session_id,
                is_active=True,
                expires_at__gt=timezone.now(),
                target_user_id=user.id,
                admin_user_id=admin_id,
            )
            .first()
        )

        if (
            session is None
            or not session.admin_user.is_active
            or not session.admin_user.is_system_admin()
            or user.is_system_admin()
            or not user.is_active
        ):
            raise AuthenticationFailed({
                'detail': 'Impersonation session is no longer valid.',
                'code': 'impersonation_ended',
            })

        return result
