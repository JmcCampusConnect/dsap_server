import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.db import models


def _get_fernet() -> Fernet:
    secret = getattr(settings, 'SECRET_KEY', '')
    key = hashlib.sha256(secret.encode('utf-8')).digest()
    return Fernet(base64.urlsafe_b64encode(key))


class EncryptedTextField(models.TextField):
    """
    Store text encrypted at rest using Fernet.

    The database only sees ciphertext; Django transparently decrypts values
    when the model is loaded.
    """

    description = 'Encrypted text'

    @staticmethod
    def _coerce_to_text(value):
        if value is None:
            return value
        if isinstance(value, memoryview):
            value = value.tobytes()
        if isinstance(value, bytes):
            return value.decode('utf-8')
        return str(value)

    def get_prep_value(self, value):
        value = super().get_prep_value(value)
        if value in (None, ''):
            return value
        value = self._coerce_to_text(value)
        token = _get_fernet().encrypt(value.encode('utf-8'))
        return token.decode('utf-8')

    def from_db_value(self, value, expression, connection):
        if value in (None, ''):
            return value
        try:
            value = self._coerce_to_text(value)
            decrypted = _get_fernet().decrypt(value.encode('utf-8'))
            return decrypted.decode('utf-8')
        except InvalidToken:
            return value

    def to_python(self, value):
        if value in (None, ''):
            return value
        value = self._coerce_to_text(value)
        try:
            decrypted = _get_fernet().decrypt(value.encode('utf-8'))
            return decrypted.decode('utf-8')
        except InvalidToken:
            return value
