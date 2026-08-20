"""Django settings for running this package's test suite.

Not shipped to consumers — this is a throwaway project config used only by
pytest-django (see DJANGO_SETTINGS_MODULE in pyproject.toml).

Backed by Postgres, not SQLite — SQLite's SELECT ... FOR UPDATE is a
documented no-op, so it can't exercise the row-locking that protects
Client Credentials Grant token exchange from a "thundering herd" of
concurrent requests (see auth.py). Needs a reachable Postgres instance;
override the POSTGRES_* env vars below to point it at yours. Defaults match
`docker run -e POSTGRES_PASSWORD=postgres -p 5432:5432 postgres:16-alpine`.
"""
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

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "django.contrib.admin",
    "django.contrib.sessions",
    "django.contrib.messages",
    "rest_framework",
    "shopify_toolkit",
]

MIDDLEWARE = [
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
]

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    }
]

# Test-only key — generated with Fernet.generate_key(), never reused outside
# this throwaway settings module.
FIELD_ENCRYPTION_KEY = "IrmBANwJFzpCieGZo9uFzuxMdLfZisW_DCKyf3rtosc="

SHOPIFY_TOOLKIT_API_SECRET = "test-api-secret"
