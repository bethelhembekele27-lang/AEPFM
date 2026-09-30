from pathlib import Path
from decouple import config
import dj_database_url
BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY
SECRET_KEY = config(
    "SECRET_KEY",
    default="django-insecure-$@vt=8b)un9e=m^zp0l97nnw0v#emzdw#!h3&rtrf!xcxutxu^"
)

DEBUG = config("DEBUG", default=False, cast=bool)

# --- Error monitoring (Sentry, free tier) ------------------------------
# Inert until SENTRY_DSN is set in the environment. send_default_pii stays
# False on purpose: this app holds bidder TINs, phone numbers, bank suffixes
# and account numbers, and none of that belongs in a third-party error
# tracker. The tradeoff is that a report won't show the request body, which
# is the correct trade for this data.
SENTRY_DSN = config("SENTRY_DSN", default="")
if SENTRY_DSN:
    import sentry_sdk
    from sentry_sdk.integrations.django import DjangoIntegration
    sentry_sdk.init(
        dsn=SENTRY_DSN,
        integrations=[DjangoIntegration()],
        traces_sample_rate=0.1,
        send_default_pii=False,
    )

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
SMS_BACKEND = config("SMS_BACKEND", default="console")   # 'console' sends nothing; 'afromessage' sends for real
SMS_ALLOWED_NUMBERS = [n.strip() for n in config("SMS_ALLOWED_NUMBERS", default="").split(",") if n.strip()]
SMS_DEFAULT_DUE_DAYS = config("SMS_DEFAULT_DUE_DAYS", default=14, cast=int)
# Afro Message — the live SMS provider
AFROMESSAGE_TOKEN = config("AFROMESSAGE_TOKEN", default="")
AFROMESSAGE_IDENTIFIER_ID = config("AFROMESSAGE_IDENTIFIER_ID", default="")
AFROMESSAGE_SENDER = config("AFROMESSAGE_SENDER", default="")
# --- Google OAuth (Phase 7) ---
GOOGLE_CLIENT_ID = config("GOOGLE_CLIENT_ID", default="")
# --- Gemini receipt extraction (Phase 9) ---
GEMINI_API_KEY = config("GEMINI_API_KEY", default="")
GEMINI_MODEL = config("GEMINI_MODEL", default="gemini-3.8-flash")
# --- Verify.ET transaction verification ---
# Inert until VERIFY_ET_API_KEY is set; check_transaction() returns a
# "not configured" error rather than calling out.
VERIFY_ET_API_KEY = config("VERIFY_ET_API_KEY", default="")
# Map bank code -> Auction Ethiopia's own settlement account, e.g.
# {"cbe": "1000123456789", "telebirr": "0911234567"}. Leave empty until the
# real numbers are known; settlementMatched then comes back null and the UI
# shows no settlement warning.
_CBE_ACCOUNT = config("VERIFY_ET_CBE_ACCOUNT", default="1000547266289")
VERIFY_ET_SETTLEMENT_ACCOUNTS = {"cbe": _CBE_ACCOUNT}
VERIFY_ET_CBE_SUFFIX = config("VERIFY_ET_CBE_SUFFIX", default=_CBE_ACCOUNT[-8:])
VERIFY_ET_PROCESS_ASYNC = config("VERIFY_ET_PROCESS_ASYNC", default=True, cast=bool)
# --- Cron (Phase 4) ---
# Shared secret for the external daily pinger that hits POST /api/cron/flag-overdue/.
# Empty means the endpoint always answers 403, so nothing runs unprompted.
CRON_SECRET = config("CRON_SECRET", default="")




# Django REST Framework
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "invoices.auth.ExpiringTokenAuthentication",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_THROTTLE_RATES": {
        "public_receipt_upload": "10/hour",
        "public_invoice_pdf": "30/hour",
        "verify_et_check": "60/hour",
        "verify_et_refresh": "300/hour",
        # Brute-force protection on the unauthenticated login endpoint. Keyed
        # by IP; enough to make credential stuffing impractical without
        # locking out a shared-office NAT.
        "login": "10/hour",
    },
}

# --- Security headers -------------------------------------------------
# Applied only when DEBUG is off, i.e. in production. The public invoice PDF
# is the one view that must render in an iframe; it opts out with
# @xframe_options_exempt, which overrides X_FRAME_OPTIONS for that route
# only, so DENY is safe globally.
SECURE_HSTS_SECONDS = 0 if DEBUG else 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = not DEBUG
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'

# Blanket cap on request body size. Individual validators cap receipts and
# attachments at 10MB; this stops an oversized multipart body being fully
# read into memory before any of those validators get a chance to run.
DATA_UPLOAD_MAX_MEMORY_SIZE = 15 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 15 * 1024 * 1024

# Admin is moved off the guessable /admin/ path to keep it out of the
# constant automated bot traffic every public Django deployment attracts.
# This is noise reduction, not access control — real protection is the
# staff-only accounts and 2FA/strong passwords behind it.
DJANGO_ADMIN_URL = config("DJANGO_ADMIN_URL", default="admin/")

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







