from pathlib import Path
from decouple import config
import dj_database_url
import dj_database_url
BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY
SECRET_KEY = config(
    "SECRET_KEY",
    default="django-insecure-$@vt=8b)un9e=m^zp0l97nnw0v#emzdw#!h3&rtrf!xcxutxu^"
)

DEBUG = config("DEBUG", default=True, cast=bool)

ALLOWED_HOSTS = config(
    "ALLOWED_HOSTS",
    default="localhost,127.0.0.1,auction-crm-api.onrender.com"
).split(",")

CSRF_TRUSTED_ORIGINS = config(
    "CSRF_TRUSTED_ORIGINS",
    default="https://auction-crm-frontend.onrender.com"
).split(",")

SESSION_COOKIE_SECURE = not DEBUG
SESSION_COOKIE_HTTPONLY = True
SECURE_SSL_REDIRECT = not DEBUG
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
PDFSHIFT_API_KEY = config("PDFSHIFT_API_KEY", default="")

# Application definition
INSTALLED_APPS = [

    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

    "corsheaders",
    "rest_framework",
    'rest_framework.authtoken',

    "invoices",
]


MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "auction_crm.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "auction_crm.wsgi.application"


# Database


DATABASES = {
    'default': dj_database_url.config(
        default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}",
        conn_max_age=60,
        conn_health_checks=True,
        ssl_require=not DEBUG,
    )
}


# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]


# Internationalization
LANGUAGE_CODE = "en-us"

TIME_ZONE = "Africa/Addis_Ababa"

USE_I18N = True

USE_TZ = True


# Static files
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STORAGES = {
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage'},
}

# Durable private file storage (receipts, attachments, generated reports).
# Uses Backblaze B2 through its S3-compatible API when B2_BUCKET_NAME is set;
# falls back to local disk (MEDIA_ROOT) when it is not, so local dev needs nothing.
if config("B2_BUCKET_NAME", default=""):
    STORAGES["default"] = {
        "BACKEND": "storages.backends.s3.S3Storage",
        "OPTIONS": {
            "bucket_name": config("B2_BUCKET_NAME"),
            "endpoint_url": config("B2_ENDPOINT_URL"),
            "access_key": config("B2_KEY_ID"),
            "secret_key": config("B2_APPLICATION_KEY"),
            "region_name": config("B2_REGION", default=""),
            "signature_version": "s3v4",
            "default_acl": None,
            "querystring_auth": True,
            "querystring_expire": 300,
            "file_overwrite": False,
        },
    }

CORS_ALLOWED_ORIGINS = config(
    'CORS_ALLOWED_ORIGINS',
    default='http://localhost:5173,http://localhost:3000'
).split(',')

# Media files (keep local for now)
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# Future AWS S3 configuration
# DEFAULT_FILE_STORAGE = "storages.backends.s3boto3.S3Boto3Storage"
# AWS_ACCESS_KEY_ID = config("AWS_ACCESS_KEY_ID", default="")
# AWS_SECRET_ACCESS_KEY = config("AWS_SECRET_ACCESS_KEY", default="")
# AWS_STORAGE_BUCKET_NAME = config("AWS_STORAGE_BUCKET_NAME", default="")

# --- SMS (Phase 4) ---
FRONTEND_BASE_URL = config("FRONTEND_BASE_URL", default="http://localhost:5173").rstrip("/")
SMS_BACKEND = config("SMS_BACKEND", default="console")   # 'console' sends nothing; 'textbee' sends for real
SMS_ALLOWED_NUMBERS = [n.strip() for n in config("SMS_ALLOWED_NUMBERS", default="").split(",") if n.strip()]
SMS_DEFAULT_DUE_DAYS = config("SMS_DEFAULT_DUE_DAYS", default=14, cast=int)
TEXTBEE_API_KEY = config("TEXTBEE_API_KEY", default="")
TEXTBEE_DEVICE_ID = config("TEXTBEE_DEVICE_ID", default="")
# --- Google OAuth (Phase 7) ---
GOOGLE_CLIENT_ID = config("GOOGLE_CLIENT_ID", default="")
# --- Gemini receipt extraction (Phase 9) ---
GEMINI_API_KEY = config("GEMINI_API_KEY", default="")
# --- Verify.ET transaction verification ---
# Inert until VERIFY_ET_API_KEY is set; check_transaction() returns a
# "not configured" error rather than calling out.
VERIFY_ET_API_KEY = config("VERIFY_ET_API_KEY", default="")
# Map bank code -> Auction Ethiopia's own settlement account, e.g.
# {"cbe": "1000123456789", "telebirr": "0911234567"}. Leave empty until the
# real numbers are known; settlementMatched then comes back null and the UI
# shows no settlement warning.
VERIFY_ET_SETTLEMENT_ACCOUNTS = {}
# --- Cron (Phase 4) ---
# Shared secret for the external daily pinger that hits POST /api/cron/flag-overdue/.
# Empty means the endpoint always answers 403, so nothing runs unprompted.
CRON_SECRET = config("CRON_SECRET", default="")




# Django REST Framework
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.TokenAuthentication",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_THROTTLE_RATES": {
        "public_receipt_upload": "10/hour",
        "public_invoice_pdf": "30/hour",
    },
}

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "console": {"class": "logging.StreamHandler"},
    },
    "root": {"handlers": ["console"], "level": "INFO"},
    "loggers": {
        "django": {"handlers": ["console"], "level": "INFO", "propagate": False},
    },
}







