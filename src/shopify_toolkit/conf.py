"""Central place to read shopify_toolkit settings.

Every SHOPIFY_TOOLKIT_* setting is read here, and only here — product,
order, customer, and webhook modules must never call django.conf.settings
directly. This keeps defaults and validation in exactly one place.
"""
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

DEFAULT_API_VERSION = "2025-01"
DEFAULT_MAX_RETRIES = 3
DEFAULT_RATE_LIMIT_BUFFER = 100
DEFAULT_MAX_BACKOFF_SECONDS = 10
DEFAULT_REQUEST_TIMEOUT = 30


def get_api_secret() -> str:
    """Return SHOPIFY_TOOLKIT_API_SECRET, raising if it isn't configured.

    This is a required setting, but it's only read (and validated) here, at
    first use — e.g. when verifying a webhook signature — never at import
    time. A project that never touches webhook code doesn't need it set.
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
    """Cap on any single blocking sleep (retry backoff or rate-limit backoff).

    Both kinds of backoff in client.py block the calling thread — under a
    sync WSGI deployment that ties up a worker process. This bounds the
    worst case per call so a slow/throttled Shopify can't quietly exhaust
    a worker pool; callers that need longer waits should catch
    ShopifyRateLimitError/ShopifyRequestError and retry via their own queue
    instead of relying on an unbounded in-process sleep.
    """
    return getattr(settings, "SHOPIFY_TOOLKIT_MAX_BACKOFF_SECONDS", DEFAULT_MAX_BACKOFF_SECONDS)


def get_request_timeout() -> float:
    """Per-request timeout (seconds) for GraphQL calls and token exchanges."""
    return getattr(settings, "SHOPIFY_TOOLKIT_REQUEST_TIMEOUT", DEFAULT_REQUEST_TIMEOUT)
