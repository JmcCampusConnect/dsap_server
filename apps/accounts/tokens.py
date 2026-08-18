import time
from rest_framework_simplejwt.tokens import RefreshToken
from django.conf import settings

class CustomRefreshToken(RefreshToken):
    @classmethod
    def for_user(cls, user):
        token = super().for_user(user)
        # Set the session start time when the token is first issued
        # (this will be overwritten by the view during rotation)
        token.payload['session_started_at'] = int(time.time())
        return token

    def copy_claim_from_old(self, old_token, claim_name):
        """Helper to copy a claim from an old token payload."""
        if claim_name in old_token.payload:
            self.payload[claim_name] = old_token.payload[claim_name]