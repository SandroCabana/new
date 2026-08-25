"""
Django settings for lti_recommender_project (Docker/Production)
Uses environment variables for all configuration
"""

from pathlib import Path
import environ
import os

# Initialize environment variables
env = environ.Env(
    DEBUG=(bool, False),
    SECRET_KEY=(str, 'CHANGE-ME-IN-PRODUCTION'),
    ALLOWED_HOSTS=(list, []),
    DB_ENGINE=(str, 'django.db.backends.postgresql'),
    DB_CONN_MAX_AGE=(int, 600),
    CACHE_TTL=(int, 300),
    LOG_LEVEL=(str, 'INFO'),
    XAPI_BEARER_TOKEN=(str, 'lti_recommender_xapi_secret_2026'),
)

# Build paths
BASE_DIR = Path(__file__).resolve().parent.parent

# Read .env file if it exists
env_file = BASE_DIR / '.env'
if env_file.exists():
    environ.Env.read_env(str(env_file))

# ==============================================================================
# CORE SETTINGS
# ==============================================================================

SECRET_KEY = env('SECRET_KEY')
DEBUG = env.bool('DEBUG', default=False)
ALLOWED_HOSTS = env.list('ALLOWED_HOSTS', default=['localhost', '127.0.0.1'])

# Allow CSRF from localhost on any port (needed for Docker + non-standard ports)
CSRF_TRUSTED_ORIGINS = [
    'http://localhost',
    'http://localhost:8080',
    'http://127.0.0.1',
    'http://127.0.0.1:8080',
]


# ==============================================================================
# APPLICATION DEFINITION
# ==============================================================================

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    
    # Third party apps
    'rest_framework',
    'rest_framework.authtoken',  # Token authentication for browser extension
    'corsheaders',  # CORS support for browser extension
    'pylti1p3.contrib.django.lti1p3_tool_config',
    'django_celery_beat',   # Celery Beat scheduler
    
    # Project apps
    'lti_recommender_project.apps.resources',
    'lti_recommender_project.apps.interactions',
    'lti_recommender_project.apps.lti_integration',
    'lti_recommender_project.apps.users',
    'lti_recommender_project.apps.recommendations',
    'lti_recommender_project.apps.analytics',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',  # CORS must be first
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',  # For static files in production
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    # X-Frame-Options disabled for LTI embedding
    # 'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'lti_recommender_project.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'lti_recommender_project.wsgi.application'

# ==============================================================================
# DATABASE
# ==============================================================================

DATABASES = {
    'default': {
        'ENGINE': env('DB_ENGINE'),
        'NAME': env('DB_NAME', default='lti_recommender_db'),
        'USER': env('DB_USER', default='lti_user'),
        'PASSWORD': env('DB_PASSWORD', default='lti_password'),
        'HOST': env('DB_HOST', default='db'),
        'PORT': env('DB_PORT', default='5432'),
        'CONN_MAX_AGE': env.int('DB_CONN_MAX_AGE', default=600),
        'OPTIONS': {
            'connect_timeout': 10,
        },
    }
}

# ==============================================================================
# CACHE
# ==============================================================================

REDIS_URL = env('REDIS_URL', default=None)

if REDIS_URL:
    CACHES = {
        'default': {
            'BACKEND': 'django_redis.cache.RedisCache',
            'LOCATION': REDIS_URL,
            'OPTIONS': {
                'CLIENT_CLASS': 'django_redis.client.DefaultClient',
                'SOCKET_CONNECT_TIMEOUT': 5,
                'SOCKET_TIMEOUT': 5,
            },
            'TIMEOUT': env.int('CACHE_TTL', default=1800),
        }
    }
    SESSION_ENGINE = 'django.contrib.sessions.backends.cache'
    SESSION_CACHE_ALIAS = 'default'
else:
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
            'LOCATION': 'unique-snowflake',
        }
    }

# ==============================================================================
# PASSWORD VALIDATION
# ==============================================================================

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# ==============================================================================
# INTERNATIONALIZATION
# ==============================================================================

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# ==============================================================================
# STATIC & MEDIA FILES
# ==============================================================================

STATIC_URL = env('STATIC_URL', default='/static/')
STATIC_ROOT = env('STATIC_ROOT', default='/app/staticfiles')
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

MEDIA_URL = env('MEDIA_URL', default='/media/')
MEDIA_ROOT = env('MEDIA_ROOT', default='/app/media')

# ==============================================================================
# SECURITY SETTINGS
# ==============================================================================

# Session security
SESSION_COOKIE_SECURE = env.bool('SESSION_COOKIE_SECURE', default=not DEBUG)
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = env('SESSION_COOKIE_SAMESITE', default='None')

# CSRF security
CSRF_COOKIE_SECURE = env.bool('CSRF_COOKIE_SECURE', default=not DEBUG)
CSRF_COOKIE_HTTPONLY = True
CSRF_COOKIE_SAMESITE = env('CSRF_COOKIE_SAMESITE', default='None')
CSRF_TRUSTED_ORIGINS = env.list('CSRF_TRUSTED_ORIGINS', default=[])

# Proxy headers (critical for LTI when behind Nginx)
USE_X_FORWARDED_HOST = True
USE_X_FORWARDED_PORT = True
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# X-Frame-Options (allow embedding in LMS)
X_FRAME_OPTIONS = 'ALLOWALL'

# ==============================================================================
# LTI CONFIGURATION
# ==============================================================================

LTI_TOOL_CONFIG = {
    'CLIENT_ID': env('LTI_CLIENT_ID', default='your-client-id'),
    'JWKS_URL': env('LTI_JWKS_URL', default='http://localhost:8000/lti/jwks/'),
    'AUTH_LOGIN_URL': env('LTI_AUTH_LOGIN_URL', default='http://localhost:8000/lti/login/'),
    'LAUNCH_URL': env('LTI_LAUNCH_URL', default='http://localhost:8000/lti/launch/'),
    'TOOL_NAME': env('LTI_TOOL_NAME', default='Sistema de Recomendación EPAI'),
    'TOOL_DESCRIPTION': env('LTI_TOOL_DESCRIPTION', default='Sistema de recomendación de temas de interés para Moodle'),
    'PUBLIC_KEY_FILE': env('LTI_PUBLIC_KEY_PATH', default=str(BASE_DIR / 'keys' / 'lti_public_key.pem')),
    'PRIVATE_KEY_FILE': env('LTI_PRIVATE_KEY_PATH', default=str(BASE_DIR / 'keys' / 'lti_private_key.pem')),
    'ENABLE_NRPS': env.bool('ENABLE_NRPS', default=True),
    'ENABLE_AGS': env.bool('ENABLE_AGS', default=False),
    'ENABLE_DEEP_LINKING': env.bool('ENABLE_DEEP_LINKING', default=True),
    'MOODLE_AUTH_URL': env('MOODLE_AUTH_URL', default='https://your-moodle.com/mod/lti/auth.php'),
    'MOODLE_TOKEN_URL': env('MOODLE_TOKEN_URL', default='https://your-moodle.com/mod/lti/token.php'),
    'MOODLE_JWKS_URL': env('MOODLE_JWKS_URL', default='https://your-moodle.com/mod/lti/certs.php'),
}

# ==============================================================================
# RECOMMENDATION ENGINE SETTINGS
# ==============================================================================

RECOMMENDATION_CONFIG = {
    # Multilingual model — supports Spanish + English
    'EMBEDDING_MODEL': env('ML_EMBEDDING_MODEL', default='paraphrase-multilingual-mpnet-base-v2'),
    'EMBEDDING_DIMENSION': env.int('ML_EMBEDDING_DIMENSION', default=768),
    'SIMILARITY_THRESHOLD': env.float('ML_SIMILARITY_THRESHOLD', default=0.3),
    'CONTENT_WEIGHT': env.float('ML_CONTENT_WEIGHT', default=0.5),
    'USER_WEIGHT': env.float('ML_USER_WEIGHT', default=0.3),
    'POPULARITY_WEIGHT': env.float('ML_POPULARITY_WEIGHT', default=0.2),
    # Cache TTL for precomputed recommendations (seconds)
    'RECOMMENDATION_CACHE_TTL': env.int('RECOMMENDATION_CACHE_TTL', default=1800),
    # Precompute for users active in last N days
    'ACTIVE_USER_DAYS': env.int('ACTIVE_USER_DAYS', default=7),
}

EMBEDDING_MODEL = RECOMMENDATION_CONFIG['EMBEDDING_MODEL']

# ==============================================================================
# CELERY SETTINGS
# ==============================================================================

CELERY_BROKER_URL = env('CELERY_BROKER_URL', default=REDIS_URL or 'redis://localhost:6379/0')
CELERY_RESULT_BACKEND = env('CELERY_RESULT_BACKEND', default=REDIS_URL or 'redis://localhost:6379/0')
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'UTC'
CELERY_BEAT_SCHEDULER = 'django_celery_beat.schedulers:DatabaseScheduler'
# Prevent tasks from running too long (30 min limit)
CELERY_TASK_SOFT_TIME_LIMIT = 1800
CELERY_TASK_TIME_LIMIT = 2100

# ==============================================================================
# LOGGING
# ==============================================================================

LOG_LEVEL = env('LOG_LEVEL', default='INFO')

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
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
        'file': {
            'class': 'logging.FileHandler',
            'filename': env('LOG_FILE', default='/app/logs/django.log'),
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console', 'file'],
        'level': LOG_LEVEL,
    },
    'loggers': {
        'django': {
            'handlers': ['console', 'file'],
            'level': LOG_LEVEL,
            'propagate': False,
        },
    },
}

# ==============================================================================
# OTHER SETTINGS
# ==============================================================================

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ==============================================================================
# REST FRAMEWORK SETTINGS
# ==============================================================================

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
        'rest_framework.authentication.TokenAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ],
}

# ==============================================================================
# CORS SETTINGS (for browser extension)
# ==============================================================================

# Allow all origins in development, restrict in production
CORS_ALLOW_ALL_ORIGINS = env.bool('CORS_ALLOW_ALL_ORIGINS', default=DEBUG)

# For production, specify allowed origins
CORS_ALLOWED_ORIGINS = env.list('CORS_ALLOWED_ORIGINS', default=[
    'chrome-extension://*',  # Chrome extensions
    'moz-extension://*',     # Firefox extensions
])

# Allow credentials (cookies, authorization headers)
CORS_ALLOW_CREDENTIALS = True

# Allow specific headers
CORS_ALLOW_HEADERS = [
    'accept',
    'accept-encoding',
    'authorization',
    'content-type',
    'origin',
    'x-requested-with',
]

# ==============================================================================
# SIMPLE JWT SETTINGS
# ==============================================================================
from datetime import timedelta
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(hours=24),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=30),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'ALGORITHM': 'HS256',
    'SIGNING_KEY': SECRET_KEY,
    'AUTH_HEADER_TYPES': ('Bearer',),
    'USER_ID_FIELD': 'id',
    'USER_ID_CLAIM': 'user_id',
}
