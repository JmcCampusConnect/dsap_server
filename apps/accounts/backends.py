from django.contrib.auth.backends import ModelBackend
from django.contrib.auth.hashers import check_password, make_password
from apps.accounts.models import User

class CommonUserBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        if username is None or password is None:
            return None

        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            make_password(password)
            return None

        if check_password(password, user.password_hash) and self.user_can_authenticate(user):
            return user
        return None