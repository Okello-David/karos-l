"""
Production settings for KarosL.

Usage:
    DJANGO_SETTINGS_MODULE=config.settings_production python manage.py runserver
"""

from .settings import *  # noqa: F403

# ------------------------------------------------------------------
# Security overrides for production
# ------------------------------------------------------------------
DEBUG = False

# Must be explicitly set in production
SECRET_KEY = os.getenv('SECRET_KEY')  # noqa: F405
if not SECRET_KEY:
    raise RuntimeError("SECRET_KEY environment variable is required in production.")

ALLOWED_HOSTS = os.getenv('ALLOWED_HOSTS', '').split(',')  # noqa: F405
if not ALLOWED_HOSTS or ALLOWED_HOSTS == ['']:
    raise RuntimeError("ALLOWED_HOSTS environment variable is required in production.")

# CORS — must be explicit in production
CORS_ALLOW_ALL_ORIGINS = False
CORS_ALLOWED_ORIGINS = os.getenv('CORS_ALLOWED_ORIGINS', '').split(',')  # noqa: F405

# CSRF
CSRF_TRUSTED_ORIGINS = os.getenv('CSRF_TRUSTED_ORIGINS', '').split(',')  # noqa: F405

# Security
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# ------------------------------------------------------------------
# Database — use PostgreSQL in production
# ------------------------------------------------------------------
DATABASES = {
    'default': {
        'ENGINE': os.getenv('DB_ENGINE', 'django.db.backends.postgresql'),  # noqa: F405
        'NAME': os.getenv('DB_NAME'),  # noqa: F405
        'USER': os.getenv('DB_USER'),  # noqa: F405
        'PASSWORD': os.getenv('DB_PASSWORD'),  # noqa: F405
        'HOST': os.getenv('DB_HOST', 'localhost'),  # noqa: F405
        'PORT': os.getenv('DB_PORT', '5432'),  # noqa: F405
        'CONN_MAX_AGE': 60,
        'OPTIONS': {
            'connect_timeout': 5,
        },
    }
}

# ------------------------------------------------------------------
# Static files — serve from S3 or CDN in production
# ------------------------------------------------------------------
STATIC_ROOT = BASE_DIR / 'staticfiles'  # noqa: F405
STATICFILES_STORAGE = 'django.contrib.staticfiles.storage.ManifestStaticFilesStorage'

# ------------------------------------------------------------------
# Logging — rotate files + email admins on errors
# ------------------------------------------------------------------
LOGGING['handlers']['file'] = {  # noqa: F405
    'level': 'WARNING',
    'class': 'logging.handlers.RotatingFileHandler',
    'filename': BASE_DIR / 'logs' / 'karosl.log',  # noqa: F405
    'maxBytes': 10485760,
    'backupCount': 10,
    'formatter': 'verbose',
}
LOGGING['handlers']['mail_admins'] = {  # noqa: F405
    'level': 'ERROR',
    'class': 'django.utils.log.AdminEmailHandler',
    'include_html': False,
}
LOGGING['root']['handlers'] = ['console', 'file', 'mail_admins']  # noqa: F405
for logger_config in LOGGING['loggers'].values():  # noqa: F405
    if 'mail_admins' not in logger_config['handlers']:
        logger_config['handlers'].append('mail_admins')

# ------------------------------------------------------------------
# Email
# ------------------------------------------------------------------
ADMINS = [('Admin', os.getenv('ADMIN_EMAIL', 'admin@karosl.com'))]  # noqa: F405
SERVER_EMAIL = os.getenv('SERVER_EMAIL', 'noreply@karosl.com')  # noqa: F405
DEFAULT_FROM_EMAIL = os.getenv('DEFAULT_FROM_EMAIL', SERVER_EMAIL)  # noqa: F405

# ------------------------------------------------------------------
# DRF — disable browsable API in production
# ------------------------------------------------------------------
REST_FRAMEWORK['DEFAULT_RENDERER_CLASSES'] = [  # noqa: F405
    'rest_framework.renderers.JSONRenderer',
]

# ------------------------------------------------------------------
# Throttling — stricter limits in production
# ------------------------------------------------------------------
REST_FRAMEWORK['DEFAULT_THROTTLE_RATES'] = {  # noqa: F405
    'anon': '20/hour',
    'user': '200/hour',
}
