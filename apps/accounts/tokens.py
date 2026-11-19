import time
from datetime import timedelta
from rest_framework_simplejwt.tokens import RefreshToken, AccessToken
from typing import Optional

class CustomRefreshToken(RefreshToken):
    @classmethod
    def for_user(cls, user, session_started_at: Optional[int] = None):
        token = super().for_user(user)
        if session_started_at is None:
            # Only set to "now" during initial login (no old token exists)
            session_started_at = int(time.time())
        token.payload['session_started_at'] = session_started_at
        return token

    def copy_claim_from_old(self, old_token, claim_name):
        # Keep this helper; we'll call it explicitly in the view
        if claim_name in old_token.payload:
            self.payload[claim_name] = old_token.payload[claim_name]


def build_impersonation_access_token(target_user, admin_user, session, lifetime_minutes: int) -> AccessToken:
    """
    Mint a short-lived access token that authenticates as *target_user* but
    carries impersonation metadata so the backend can:
      - Validate the session on every request (ImpersonationAwareJWTAuthentication)
      - Populate AuditLog with the real actor (admin_user)
      - Block sensitive actions (IsNotImpersonating)

    Does NOT create OutstandingToken rows (AccessToken.for_user does not).
    Does NOT set any refresh cookie.
    """
    token = AccessToken.for_user(target_user)
    token['session_started_at'] = int(time.time())
    token['role'] = target_user.role_name or ''
    token['is_impersonation'] = True
    token['impersonator_id'] = admin_user.id
    token['impersonator_name'] = admin_user.username
    token['impersonation_session_id'] = session.id
    token.set_exp(lifetime=timedelta(minutes=lifetime_minutes))
    return token