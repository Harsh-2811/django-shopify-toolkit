"""Central place to read shopify_toolkit settings.

Every SHOPIFY_TOOLKIT_* setting is read here, and only here — product,
order, customer, and webhook modules must never call django.conf.settings
directly. This keeps defaults and validation in exactly one place.
"""
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

# Shopify supports each stable API version for ~12 months. Bump this periodically or it
# silently expires. Next bump needed before ~2027-07.
DEFAULT_API_VERSION = "2026-07"
DEFAULT_MAX_RETRIES = 3
DEFAULT_RATE_LIMIT_BUFFER = 100
DEFAULT_MAX_BACKOFF_SECONDS = 10
DEFAULT_REQUEST_TIMEOUT = 30
DEFAULT_MAX_POOLED_SESSIONS = 500
DEFAULT_DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
DEFAULT_DB_SCHEMA = ""


def get_api_secret() -> str:
    """Return SHOPIFY_TOOLKIT_API_SECRET, raising if it isn't configured.

    Read lazily at first use (e.g. verifying a webhook signature), not at import time — a
    project that never touches webhook code doesn't need it set.
    """
    value = getattr(settings, "SHOPIFY_TOOLKIT_API_SECRET", None)
    if not value:
        raise ImproperlyConfigured(
            "SHOPIFY_TOOLKIT_API_SECRET is required but not set. Add it to "
            "your Django settings — see the django-shopify-toolkit README."
        )
    return value


def get_api_version() -> str:
    """Default Shopify Admin API version for stores that don't override it."""
    return getattr(settings, "SHOPIFY_TOOLKIT_API_VERSION", DEFAULT_API_VERSION)


def get_max_retries() -> int:
    """Max retry attempts for transient network errors in ShopifyGraphQLClient."""
    return getattr(settings, "SHOPIFY_TOOLKIT_MAX_RETRIES", DEFAULT_MAX_RETRIES)


def get_rate_limit_buffer() -> int:
    """Pause outgoing requests when the cost throttle bucket drops below this."""
    return getattr(settings, "SHOPIFY_TOOLKIT_RATE_LIMIT_BUFFER", DEFAULT_RATE_LIMIT_BUFFER)


def get_max_backoff_seconds() -> float:
    """Cap on any single blocking sleep (retry backoff or rate-limit backoff), so a slow/
    throttled Shopify can't tie up a sync worker indefinitely."""
    return getattr(settings, "SHOPIFY_TOOLKIT_MAX_BACKOFF_SECONDS", DEFAULT_MAX_BACKOFF_SECONDS)


def get_request_timeout() -> float:
    """Per-request timeout (seconds) for GraphQL calls and token exchanges."""
    return getattr(settings, "SHOPIFY_TOOLKIT_REQUEST_TIMEOUT", DEFAULT_REQUEST_TIMEOUT)


def get_max_pooled_sessions() -> int:
    """Max distinct store domains kept in client.py's session pool at once; least-recently-used
    sessions are evicted and closed beyond this."""
    return getattr(settings, "SHOPIFY_TOOLKIT_MAX_POOLED_SESSIONS", DEFAULT_MAX_POOLED_SESSIONS)


def get_default_auto_field() -> str:
    """Primary-key field class for ShopifyStore/WebhookEvent. Defaults to BigAutoField. Override
    only for a backend that doesn't support it as a PK — e.g. MongoDB, which needs
    'django_mongodb_backend.fields.ObjectIdAutoField'. See MULTI_DB_SUPPORT_PLAN.md.

    A dedicated setting rather than Django's own project-wide DEFAULT_AUTO_FIELD, which would
    repoint every app's PK type, not just this one.
    """
    return getattr(settings, "SHOPIFY_TOOLKIT_DEFAULT_AUTO_FIELD", DEFAULT_DEFAULT_AUTO_FIELD)


def get_db_schema() -> str:
    """Dedicated PostgreSQL schema for ShopifyStore/WebhookEvent. Empty (default) = no special
    handling. PostgreSQL-only — MySQL/SQLite have no equivalent concept.

    Fresh installs only: set before the first `migrate`. migrations/0002_dedicated_schema.py
    creates the schema and moves the tables in, but only runs its real logic the first time —
    flipping this after that migration has already applied (even as a no-op) does nothing on a
    later `migrate`. An existing install that wants to move needs a manual, one-time
    `CREATE SCHEMA IF NOT EXISTS` + `ALTER TABLE ... SET SCHEMA`, not this setting.
    """
    return getattr(settings, "SHOPIFY_TOOLKIT_DB_SCHEMA", DEFAULT_DB_SCHEMA)


def get_qualified_table_name(unqualified_name: str) -> str | None:
    """Schema-qualified db_table string if SHOPIFY_TOOLKIT_DB_SCHEMA is set, else None.

    Shared by models.py (Meta.db_table) and migrations/0002_dedicated_schema.py (its
    AlterModelTable state_operations) so both agree. Returns None, not `unqualified_name`, when
    unset — Django's migration autodetector cares whether db_table was explicitly set, not just
    its resolved value, so it must be left off the model entirely rather than set to a matching
    default.

    Uses Django's old db_table schema-qualification workaround (ticket #1208): a string with an
    embedded `"."`, which Django wraps once, producing `"schema"."table"`.
    """
    schema = get_db_schema()
    if not schema:
        return None
    return f'{schema}"."{unqualified_name}'
