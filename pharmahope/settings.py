"""
Django settings for the pharmahope project.

All secrets and environment-specific values come from environment variables
(optionally loaded from a local `.env` file, see `.env.example`). Nothing
sensitive is stored in this file.

For the full list of settings and their values, see
https://docs.djangoproject.com/en/5.2/ref/settings/
"""

import importlib.util
import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Load a local .env file if python-dotenv is installed (development convenience).
try:
    from dotenv import load_dotenv

    load_dotenv(BASE_DIR / '.env')
except ImportError:
    pass


def env_bool(name, default=False):
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in ('1', 'true', 'yes', 'on')


def env_list(name, default=''):
    return [item.strip() for item in os.environ.get(name, default).split(',') if item.strip()]


def module_available(name):
    return importlib.util.find_spec(name) is not None


# --- Core -------------------------------------------------------------------

# SECURITY WARNING: never run with DEBUG on in production. It defaults to off.
DEBUG = env_bool('DJANGO_DEBUG', False)

SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY')
if not SECRET_KEY:
    if DEBUG:
        SECRET_KEY = 'dev-only-insecure-key-do-not-use-in-production'
    else:
        raise ImproperlyConfigured(
            'DJANGO_SECRET_KEY is not set. Set it in the environment or in a .env file.'
        )

ALLOWED_HOSTS = env_list('DJANGO_ALLOWED_HOSTS', 'localhost,127.0.0.1' if DEBUG else '')
if not DEBUG and not ALLOWED_HOSTS:
    raise ImproperlyConfigured('DJANGO_ALLOWED_HOSTS must be set when DJANGO_DEBUG is False.')

CSRF_TRUSTED_ORIGINS = env_list('DJANGO_CSRF_TRUSTED_ORIGINS')

# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'store',
    'cart',
    'payment',
    'tailwind',
    'theme',
    'paypal.standard.ipn',
    'blog',
    'forum',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.locale.LocaleMiddleware',  # must come after SessionMiddleware
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

# Development-only tooling (see requirements-dev.txt). Never enabled in production.
USE_BROWSER_RELOAD = DEBUG and module_available('django_browser_reload')
if USE_BROWSER_RELOAD:
    INSTALLED_APPS.append('django_browser_reload')
    MIDDLEWARE.append('django_browser_reload.middleware.BrowserReloadMiddleware')
if DEBUG and module_available('django_extensions'):
    INSTALLED_APPS.append('django_extensions')

ROOT_URLCONF = 'pharmahope.urls'

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
                'cart.context_processors.cart',
            ],
        },
    },
]

WSGI_APPLICATION = 'pharmahope.wsgi.application'

# --- Database ---------------------------------------------------------------
# DB_ENGINE=sqlite is the simplest option for local development.
# Otherwise MySQL is used; credentials must be provided in production.

DB_ENGINE = os.environ.get('DB_ENGINE', 'mysql').lower()

if DB_ENGINE == 'sqlite':
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / os.environ.get('DB_NAME', 'db.sqlite3'),
        }
    }
else:
    db_user = os.environ.get('DB_USER', 'root' if DEBUG else '')
    db_password = os.environ.get('DB_PASSWORD', '')
    if not DEBUG and (not db_user or not db_password):
        raise ImproperlyConfigured('DB_USER and DB_PASSWORD must be set when DJANGO_DEBUG is False.')
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.mysql',
            'NAME': os.environ.get('DB_NAME', 'pharmadb'),
            'USER': db_user,
            'PASSWORD': db_password,
            'HOST': os.environ.get('DB_HOST', 'localhost'),
            'PORT': os.environ.get('DB_PORT', '3306'),
            'OPTIONS': {'charset': 'utf8mb4'},
        }
    }

# Password validation
# https://docs.djangoproject.com/en/5.2/ref/settings/#auth-password-validators

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

# Internationalization

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True

# --- Static and media files -------------------------------------------------

STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'  # target of `collectstatic` in production

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

TAILWIND_APP_NAME = 'theme'

INTERNAL_IPS = [
    '127.0.0.1',
]

# Only needed for `manage.py tailwind ...` on machines where npm is not on PATH.
if os.environ.get('NPM_BIN_PATH'):
    NPM_BIN_PATH = os.environ['NPM_BIN_PATH']

# --- Authentication ---------------------------------------------------------

# Where @login_required sends anonymous users (this project's login view is named 'login').
LOGIN_URL = 'login'

# --- Sessions ---------------------------------------------------------------

SESSION_COOKIE_AGE = 1209600  # 2 weeks in seconds
SESSION_EXPIRE_AT_BROWSER_CLOSE = False
SESSION_SAVE_EVERY_REQUEST = True

# --- Production security ----------------------------------------------------

if not DEBUG:
    SECURE_SSL_REDIRECT = env_bool('DJANGO_SECURE_SSL_REDIRECT', True)
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    # Start with a short HSTS lifetime and raise it once HTTPS is confirmed to work.
    SECURE_HSTS_SECONDS = int(os.environ.get('DJANGO_HSTS_SECONDS', '3600'))
    SECURE_HSTS_INCLUDE_SUBDOMAINS = env_bool('DJANGO_HSTS_INCLUDE_SUBDOMAINS', False)
    if env_bool('DJANGO_BEHIND_PROXY', False):
        SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# --- PayPal -----------------------------------------------------------------

PAYPAL_TEST = env_bool('PAYPAL_TEST', True)  # True = sandbox
PAYPAL_RECEIVER_EMAIL = os.environ.get('PAYPAL_RECEIVER_EMAIL', '')

# Prices are stored in STORE_CURRENCY. PayPal does not support XAF (Fcfa), so the
# amount sent to PayPal is converted with PAYPAL_EXCHANGE_RATE (store-currency
# units per 1 unit of PAYPAL_CURRENCY). See payment/services.py.
STORE_CURRENCY = os.environ.get('STORE_CURRENCY', 'XAF')
PAYPAL_CURRENCY = os.environ.get('PAYPAL_CURRENCY', 'USD')
PAYPAL_EXCHANGE_RATE = os.environ.get('PAYPAL_EXCHANGE_RATE', '')

# --- Shop -------------------------------------------------------------------

CART_MAX_QTY = int(os.environ.get('CART_MAX_QTY', '5'))

# --- Logging ----------------------------------------------------------------

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'standard': {'format': '{asctime} {levelname} {name}: {message}', 'style': '{'},
    },
    'handlers': {
        'console': {'class': 'logging.StreamHandler', 'formatter': 'standard'},
    },
    'root': {
        'handlers': ['console'],
        'level': os.environ.get('DJANGO_LOG_LEVEL', 'INFO'),
    },
}
