"""Access token resolution for ShopifyStore.

Shopify custom apps created before January 1, 2026 get a static Admin API
access token (shpat_...) shown once in the admin UI, which never expires —
that's stored directly in ShopifyStore.access_token and used as-is.

Apps created via the Dev Dashboard (Jan 1, 2026 onward) don't expose a
static token at all — only a Client ID and Client Secret, which must be
exchanged for a token that expires roughly every 24 hours. See:
https://shopify.dev/docs/apps/build/authentication-authorization/access-tokens/client-credentials-grant

get_access_token() below picks the right path per store: if client_id and
client_secret are set, it exchanges (or reuses a still-valid cached
exchange) and persists the result on that store's own row. That's per-store
persisted state, not module-level shared state, so it stays safe for
multi-tenant use per CLAUDE.md principle #2 — store A's exchange can never
leak into store B's request.
"""
from __future__ import annotations

from datetime import timedelta

import requests
from django.db import transaction
from django.utils import timezone

from .conf import get_request_timeout
from .exceptions import ShopifyRequestError, ShopifyStoreNotConfigured
from .models import ShopifyStore

# Refresh this many seconds before actual expiry, so a request never gets
# built with a token that expires mid-flight.
_EXPIRY_BUFFER_SECONDS = 60


def get_access_token(store: ShopifyStore) -> str:
    """Return a usable Admin API access token for this store.

    Exchanges and caches a fresh token via the client credentials grant if
    the store has client_id/client_secret configured and no still-valid
    cached token; otherwise returns the static access_token as-is. Raises
    ShopifyStoreNotConfigured if neither is set.
    """
    if store.client_id and store.client_secret:
        if store.access_token and not _is_expired(store):
            return store.access_token
        return _exchange_client_credentials_locked(store)

    if store.access_token:
        return store.access_token

    raise ShopifyStoreNotConfigured(
        f"ShopifyStore '{store.shop_domain}' has neither access_token nor "
        f"client_id/client_secret configured — set one of them before "
        f"making API calls."
    )


def _is_expired(store: ShopifyStore) -> bool:
    if store.access_token_expires_at is None:
        # A legacy static token has no expiry recorded — never expires.
        # A freshly-created client_id/secret store with no exchange yet
        # also has no expiry recorded, which correctly forces an exchange
        # since access_token would be empty in that case anyway.
        return False
    return timezone.now() >= store.access_token_expires_at - timedelta(
        seconds=_EXPIRY_BUFFER_SECONDS
    )


def _exchange_client_credentials_locked(store: ShopifyStore) -> str:
    """Exchange under a row lock, so concurrent requests for the same store
    serialize instead of each independently hitting Shopify's OAuth endpoint
    at once when a token expires under heavy traffic (a "thundering herd").

    On backends that support SELECT ... FOR UPDATE (Postgres, MySQL — what
    any real deployment should be running) this acquires a genuine row
    lock. On SQLite it's a harmless no-op (SQLite has no concurrent writers
    to race in the first place), so this is safe for tests/dev too.
    """
    with transaction.atomic():
        locked_store = ShopifyStore.objects.select_for_update().get(pk=store.pk)
        # Re-check after acquiring the lock: another request may have
        # already refreshed the token while we were waiting for it.
        if locked_store.access_token and not _is_expired(locked_store):
            store.access_token = locked_store.access_token
            store.access_token_expires_at = locked_store.access_token_expires_at
            return locked_store.access_token

        token = _exchange_client_credentials(locked_store)
        store.access_token = locked_store.access_token
        store.access_token_expires_at = locked_store.access_token_expires_at
        return token


def _exchange_client_credentials(store: ShopifyStore) -> str:
    """POST the client credentials grant and persist the resulting token."""
    url = f"https://{store.shop_domain}/admin/oauth/access_token"
    try:
        response = requests.post(
            url,
            data={
                "client_id": store.client_id,
                "client_secret": store.client_secret,
                "grant_type": "client_credentials",
            },
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json",
            },
            timeout=get_request_timeout(),
        )
    except requests.RequestException as exc:
        raise ShopifyRequestError(
            f"Client credentials exchange failed for {store.shop_domain}: {exc}"
        ) from exc

    if response.status_code != 200:
        raise ShopifyRequestError(
            f"Client credentials exchange for {store.shop_domain} returned "
            f"HTTP {response.status_code}: {response.text}"
        )

    body = response.json()
    token = body["access_token"]
    expires_in = body.get("expires_in", 86399)

    store.access_token = token
    store.access_token_expires_at = timezone.now() + timedelta(seconds=expires_in)
    store.save(update_fields=["access_token", "access_token_expires_at", "updated_at"])

    return token
