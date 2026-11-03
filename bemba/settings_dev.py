import os

os.environ.setdefault('DJANGO_DEBUG', 'True')
os.environ.setdefault('DJANGO_SECRET_KEY', 'bemba-local-development-key-not-for-production-2026')

from .settings import *

# Use SQLite for development when MariaDB is not available or incompatible.
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# Local HTTP development must not inherit production HTTPS redirects from .env.
DEBUG = True
SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
SECURE_HSTS_SECONDS = 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = False
SECURE_HSTS_PRELOAD = False

EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
DEFAULT_FROM_EMAIL = 'bemba@example.com'
ALERT_EMAIL_RECIPIENTS = os.getenv('ALERT_EMAIL_RECIPIENTS', 'admin@example.com').split(',')
