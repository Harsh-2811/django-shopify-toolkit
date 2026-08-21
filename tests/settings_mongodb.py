
import os

SECRET_KEY = "test-secret-key-not-for-production"
DEBUG = True
USE_TZ = True

DATABASES = {
    "default": {
        "ENGINE": "django_mongodb_backend",
        "NAME": os.environ.get("MONGODB_NAME", "shopify_toolkit_test"),
        "HOST": os.environ.get("MONGODB_HOST", "localhost"),
        "PORT": int(os.environ.get("MONGODB_PORT", "27017")),
    }
}


SHOPIFY_TOOLKIT_DEFAULT_AUTO_FIELD = "django_mongodb_backend.fields.ObjectIdAutoField"
MIGRATION_MODULES = {
    "shopify_toolkit": "shopify_toolkit.migrations_mongodb",
}

INSTALLED_APPS = [
    "django_mongodb_backend",
    "django.contrib.sessions",
    "django.contrib.messages",
    "rest_framework",
    "shopify_toolkit",
]

MIDDLEWARE = [
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
]

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.contrib.messages.context_processors.messages",
            ],
        },
    }
]

FIELD_ENCRYPTION_KEY = "IrmBANwJFzpCieGZo9uFzuxMdLfZisW_DCKyf3rtosc="

SHOPIFY_TOOLKIT_API_SECRET = "test-api-secret"


REST_FRAMEWORK = {
    "UNAUTHENTICATED_USER": None,
}
