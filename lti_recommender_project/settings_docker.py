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
    'pylti1p3.contrib.django.lti1p3_tool_config',
    
    # Project apps
    'lti_recommender_project.apps.resources',
    'lti_recommender_project.apps.interactions',
    'lti_recommender_project.apps.lti_integration',
    'lti_recommender_project.apps.users',
    'lti_recommender_project.apps.recommendations',
]

MIDDLEWARE = [
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
            'BACKEND': 'django.core.cache.backends.redis.RedisCache',
            'LOCATION': REDIS_URL,
            'OPTIONS': {
                'parser_class': 'redis.connection.HiredisParser',
            },
            'TIMEOUT': env.int('CACHE_TTL', default=300),
        }
    }
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
STATIC_ROOT = env('STATIC_ROOT', default=str(BASE_DIR / 'staticfiles'))
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

MEDIA_URL = env('MEDIA_URL', default='/media/')
MEDIA_ROOT = env('MEDIA_ROOT', default=str(BASE_DIR / 'media'))

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
    'EMBEDDING_MODEL': env('ML_EMBEDDING_MODEL', default='sentence-transformers/all-MiniLM-L6-v2'),
    'EMBEDDING_DIMENSION': env.int('ML_EMBEDDING_DIMENSION', default=384),
    'SIMILARITY_THRESHOLD': env.float('ML_SIMILARITY_THRESHOLD', default=0.3),
    'CONTENT_WEIGHT': env.float('ML_CONTENT_WEIGHT', default=0.5),
    'USER_WEIGHT': env.float('ML_USER_WEIGHT', default=0.3),
    'POPULARITY_WEIGHT': env.float('ML_POPULARITY_WEIGHT', default=0.2),
}

EMBEDDING_MODEL = RECOMMENDATION_CONFIG['EMBEDDING_MODEL']

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
