import os
from urllib.parse import urlsplit

from django.core.exceptions import ImproperlyConfigured

from .base import *

DEBUG = False
assert not DEBUG, "DEBUG must be False in production settings"

# --- Transport security ---
SECURE_SSL_REDIRECT = True
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

# --- Cookie hardening ---
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_SAMESITE = 'Strict'
CSRF_COOKIE_SAMESITE = 'Strict'

# --- Misc hardening ---
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = 'same-origin'
X_FRAME_OPTIONS = 'DENY'

# --- Production email validation ---
if EMAIL_BACKEND != 'django.core.mail.backends.smtp.EmailBackend':
    raise ImproperlyConfigured(
        'Production requires the configured SMTP email backend.'
    )
if not EMAIL_HOST or EMAIL_HOST.lower() in {'localhost', '127.0.0.1', '::1'}:
    raise ImproperlyConfigured('Production SMTP requires a valid EMAIL_HOST.')
if not 1 <= EMAIL_PORT <= 65535:
    raise ImproperlyConfigured('EMAIL_PORT must be between 1 and 65535.')
if not EMAIL_HOST_USER or not EMAIL_HOST_PASSWORD:
    raise ImproperlyConfigured(
        'Production SMTP requires EMAIL_HOST_USER and EMAIL_HOST_PASSWORD.'
    )
if not os.environ.get('DEFAULT_FROM_EMAIL'):
    raise ImproperlyConfigured(
        'DEFAULT_FROM_EMAIL must be configured explicitly in production.'
    )
if EMAIL_USE_TLS == EMAIL_USE_SSL:
    raise ImproperlyConfigured(
        'Configure exactly one of EMAIL_USE_TLS or EMAIL_USE_SSL in production.'
    )
frontend_url = os.environ.get('FRONTEND_URL', '').strip()
parsed_frontend_url = urlsplit(frontend_url)
if parsed_frontend_url.scheme != 'https' or not parsed_frontend_url.netloc:
    raise ImproperlyConfigured(
        'Production requires FRONTEND_URL to be an absolute HTTPS URL.'
    )
