import os

SECRET_KEY = "test-secret-key-not-for-production"
DEBUG = True
USE_TZ = True

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("POSTGRES_DB", "postgres"),
        "USER": os.environ.get("POSTGRES_USER", "postgres"),
        "PASSWORD": os.environ.get("POSTGRES_PASSWORD", "postgres"),
        "HOST": os.environ.get("POSTGRES_HOST", "localhost"),
        "PORT": os.environ.get("POSTGRES_PORT", "5432"),
    }
}

SHOPIFY_TOOLKIT_DB_SCHEMA = "shopify_data"

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "shopify_toolkit",
]

MIDDLEWARE = []

FIELD_ENCRYPTION_KEY = "IrmBANwJFzpCieGZo9uFzuxMdLfZisW_DCKyf3rtosc="
SHOPIFY_TOOLKIT_API_SECRET = "test-api-secret"
