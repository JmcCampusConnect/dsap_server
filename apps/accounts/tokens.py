import time
from rest_framework_simplejwt.tokens import RefreshToken
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