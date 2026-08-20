"""Typed exceptions for django-shopify-toolkit.

Consumers should catch these instead of requests exceptions or raw dict
inspection — every Shopify GraphQL failure mode surfaces as one of these.
"""


class ShopifyToolkitError(Exception):
    """Base class for all django-shopify-toolkit exceptions."""


class ShopifyGraphQLError(ShopifyToolkitError):
    """Raised when a Shopify GraphQL response contains a top-level "errors" array."""

    def __init__(self, message: str, errors: list | None = None):
        super().__init__(message)
        self.errors = errors or []


class ShopifyUserError(ShopifyToolkitError):
    """Raised when a mutation succeeds at the transport level but reports
    field-level userErrors (e.g. validation failures on productCreate)."""

    def __init__(self, message: str, user_errors: list | None = None):
        super().__init__(message)
        self.user_errors = user_errors or []


class ShopifyRateLimitError(ShopifyToolkitError):
    """Raised when a request is throttled by Shopify's cost-based rate limiter."""

    def __init__(self, message: str, retry_after: str | None = None):
        super().__init__(message)
        self.retry_after = retry_after


class ShopifyRequestError(ShopifyToolkitError):
    """Raised for network-layer failures after retries are exhausted, or a
    malformed (non-JSON) response from Shopify."""


class ShopifyStoreNotConfigured(ShopifyToolkitError):
    """Raised when a ShopifyStore has neither access_token nor
    client_id/client_secret set, so no request can be authenticated."""
