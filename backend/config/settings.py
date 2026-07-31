import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# ------------------------------------------------------------------
# Paths
# ------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent

# ------------------------------------------------------------------
# Security
# ------------------------------------------------------------------
SECRET_KEY = os.getenv('SECRET_KEY', 'django-insecure-dev-key-change-in-production')

DEBUG = os.getenv('DEBUG', 'True').lower() in ('true', '1', 'yes')

ALLOWED_HOSTS = os.getenv('ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',')

# Security middleware settings
# HTTPS-enforcing settings default to "on whenever DEBUG is off", but are
# independently overridable via env var. This matters because DEBUG=False
# does not imply a request actually arrived over HTTPS — e.g. this repo's
# local Docker Compose environment runs DEBUG=False with no TLS termination
# anywhere in the chain (see docs/DEVOPS.md), so forcing HTTPS redirects and
# Secure-flagged cookies there would break all HTTP access, including admin
# login. Real production behind a TLS-terminating proxy/load balancer keeps
# the DEBUG=False default with no extra env vars needed.
def _bool_env(name, default):
    return os.getenv(name, str(default)).lower() in ('true', '1', 'yes')


SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_BROWSER_XSS_FILTER = True
X_FRAME_OPTIONS = 'DENY'
CSRF_COOKIE_HTTPONLY = True
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_SECURE = _bool_env('CSRF_COOKIE_SECURE', not DEBUG)
SESSION_COOKIE_SECURE = _bool_env('SESSION_COOKIE_SECURE', not DEBUG)
SECURE_SSL_REDIRECT = _bool_env('SECURE_SSL_REDIRECT', not DEBUG)

# When TLS terminates at a reverse proxy (nginx on the staging EC2 box, a load
# balancer later), the request reaching Django arrives over plain HTTP, so
# request.is_secure() is False and SECURE_SSL_REDIRECT would redirect to HTTPS
# forever. Trusting the proxy's X-Forwarded-Proto header fixes that — but only
# where clients genuinely cannot bypass the proxy, since the header is
# client-settable and a spoofed value would make Django treat a plaintext
# request as secure. Hence opt-in rather than tied to DEBUG: staging binds
# Gunicorn to 127.0.0.1 only and nginx always overwrites the header
# (frontend/nginx.conf), so it is safe there and unsafe for an exposed
# Gunicorn. See docs/DOMAIN_HTTPS_PLAN.md.
if _bool_env('USE_X_FORWARDED_PROTO', False):
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# Overridable because HSTS is a browser-side commitment that outlives the
# deployment: staging is reached at an IP-derived hostname that will eventually
# point elsewhere, so it uses a short max-age. Production keeps the one-year
# default.
# The container HEALTHCHECK curls http://localhost:8000/api/health/ straight at
# Gunicorn, bypassing nginx, so that request carries no X-Forwarded-Proto and
# Django would answer it with a redirect to HTTPS. curl treats a 301 as success,
# so the check would keep reporting "healthy" while no longer verifying anything
# — including the database connectivity it exists to test. Exempting the path
# keeps the healthcheck honest. Externally this is not a bypass: nginx still
# redirects every non-ACME HTTP request before it reaches Django.
SECURE_REDIRECT_EXEMPT = [r'^api/health/$']

SECURE_HSTS_SECONDS = int(os.getenv('SECURE_HSTS_SECONDS', 31536000)) if SECURE_SSL_REDIRECT else 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = SECURE_HSTS_SECONDS > 0
SECURE_HSTS_PRELOAD = SECURE_HSTS_SECONDS > 0

# ------------------------------------------------------------------
# Application definition
# ------------------------------------------------------------------
INSTALLED_APPS = [
    # Django core
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # Third-party
    'rest_framework',
    'rest_framework.authtoken',
    'corsheaders',
    # Local apps
    'apps.core',
    'apps.accounts',
    'apps.properties',
    'apps.sections',
    'apps.units',
    'apps.occupants',
    'apps.occupancy',
    'apps.payments',
    'apps.dashboard',
    'apps.administration',
    'apps.audit',
    'apps.backup',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

# ------------------------------------------------------------------
# Database
# ------------------------------------------------------------------
_db_engine = os.getenv('DB_ENGINE', 'django.db.backends.sqlite3')
_db_name = os.getenv('DB_NAME')

if 'sqlite3' in _db_engine:
    # SQLite's NAME is a filesystem path — resolve relative paths against
    # BASE_DIR so local dev keeps working from any working directory.
    if _db_name:
        _db_path = Path(_db_name)
        _db_name = str(_db_path if _db_path.is_absolute() else BASE_DIR / _db_path)
    else:
        _db_name = str(BASE_DIR / 'db.sqlite3')
else:
    # PostgreSQL (and other server-based engines): NAME is a database name,
    # not a path — must not be resolved against BASE_DIR.
    _db_name = _db_name or 'karosl'

DATABASES = {
    'default': {
        'ENGINE': _db_engine,
        'NAME': _db_name,
        'USER': os.getenv('DB_USER', ''),
        'PASSWORD': os.getenv('DB_PASSWORD', ''),
        'HOST': os.getenv('DB_HOST', ''),
        'PORT': os.getenv('DB_PORT', ''),
    }
}

# ------------------------------------------------------------------
# Authentication
# ------------------------------------------------------------------
AUTH_USER_MODEL = 'accounts.User'

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# ------------------------------------------------------------------
# Internationalization
# ------------------------------------------------------------------
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# ------------------------------------------------------------------
# Static files
# ------------------------------------------------------------------
STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

# WhiteNoise serves Django's own static assets (admin, DRF browsable API)
# straight from the app container — no separate static file server needed
# for these. App file uploads are unaffected (there are none today; see
# docs/DEVOPS.md's "Static and Media Files" section).
STORAGES = {
    'default': {
        'BACKEND': 'django.core.files.storage.FileSystemStorage',
    },
    'staticfiles': {
        'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage',
    },
}

# ------------------------------------------------------------------
# Default primary key
# ------------------------------------------------------------------
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ------------------------------------------------------------------
# CORS
# ------------------------------------------------------------------
CORS_ALLOW_ALL_ORIGINS = os.getenv('CORS_ALLOW_ALL_ORIGINS', 'True').lower() in ('true', '1', 'yes')
CORS_ALLOWED_ORIGINS = os.getenv('CORS_ALLOWED_ORIGINS', 'http://localhost:5173').split(',')
CORS_ALLOW_CREDENTIALS = True
CSRF_TRUSTED_ORIGINS = os.getenv('CSRF_TRUSTED_ORIGINS', 'http://localhost:5173').split(',')

# ------------------------------------------------------------------
# Django REST Framework
# ------------------------------------------------------------------
REST_FRAMEWORK = {
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.TokenAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
        'rest_framework.renderers.BrowsableAPIRenderer',
    ],
    'EXCEPTION_HANDLER': 'apps.core.exceptions.drf_exception_handler',
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '100/hour',
        'user': '1000/hour',
    },
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
    'MAX_PAGE_SIZE': 100,
}

# ------------------------------------------------------------------
# Logging
# ------------------------------------------------------------------
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'level': 'DEBUG',
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
        'file': {
            'level': 'WARNING',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': BASE_DIR / 'logs' / 'karosl.log',
            'maxBytes': 10485760,
            'backupCount': 5,
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console', 'file'],
        'level': 'INFO',
    },
    'loggers': {
        'django': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': False,
        },
        'django.request': {
            'handlers': ['console', 'file'],
            'level': 'WARNING',
            'propagate': False,
        },
        'karosl': {
            'handlers': ['console', 'file'],
            'level': 'DEBUG',
            'propagate': False,
        },
    },
}
