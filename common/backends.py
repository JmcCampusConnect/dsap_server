from django.contrib.auth.backends import ModelBackend
from django.contrib.auth.hashers import check_password
from common.models import User

class CommonUserBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            return None
        # Check the hash stored in password_hash
        if user and check_password(password, user.password_hash):
            return user
        return None