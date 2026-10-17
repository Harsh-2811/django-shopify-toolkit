"""Store-scoped Shopify Admin GraphQL client.

Every client is built from an explicit ShopifyStore instance, so store A's token can never leak
into store B's request. Rate-limit awareness (reading extensions.cost.throttleStatus) is built
in here, not bolted on later.
"""
from __future__ import annotations

import collections
import logging
import re
import threading
import time
from typing import Any

import requests

from .auth import get_access_token
from .conf import (
    get_max_backoff_seconds,
    get_max_pooled_sessions,
    get_max_retries,
    get_rate_limit_buffer,
    get_request_timeout,
)
from .exceptions import ShopifyGraphQLError, ShopifyRateLimitError, ShopifyRequestError
from .models import ShopifyStore

logger = logging.getLogger(__name__)

# Gateway-level failures Shopify returns while the request never reached (or never finished in)
# the API itself — worth retrying for a read. Not 500: that usually means the query itself
# tripped something server-side, and retrying it just repeats the failure.
_RETRYABLE_STATUS_CODES = frozenset({502, 503, 504})

# Matches a top-level `mutation` operation definition. Anchored to the start of a line rather
# than the start of the string because this package's query strings prepend fragment
# definitions (e.g. CUSTOMER_FIELDS_FRAGMENT + "mutation CreateCustomer...").
_MUTATION_RE = re.compile(r"^\s*mutation\b", re.MULTILINE)

# A connection-pooled requests.Session per shop domain, reused across ShopifyGraphQLClient
# instances so repeat calls to the same store don't each pay a fresh TCP/TLS handshake. Safe
# despite being module-level state: no store-specific secret is ever stored ON a Session (the
# access token is passed per-request via the `headers=` kwarg in execute(), never via
# session.headers), and each store's pool is kept strictly separate by domain key, so no
# store's connections/state can cross into another's request.
#
# Bounded (LRU-evicted) rather than an unbounded dict — a deployment
# managing thousands of stores shouldn't accumulate one Session forever per
# store ever seen. SHOPIFY_TOOLKIT_MAX_POOLED_SESSIONS caps it; the
# least-recently-used session is closed and dropped once exceeded.
_session_pool: "collections.OrderedDict[str, requests.Session]" = collections.OrderedDict()
_session_pool_lock = threading.Lock()


def _get_pooled_session(shop_domain: str) -> requests.Session:
    with _session_pool_lock:
        session = _session_pool.get(shop_domain)
        if session is not None:
            _session_pool.move_to_end(shop_domain)
            return session

        session = requests.Session()
        _session_pool[shop_domain] = session

        max_size = get_max_pooled_sessions()
        while len(_session_pool) > max_size:
            _, evicted = _session_pool.popitem(last=False)
            evicted.close()

        return session


class ShopifyGraphQLClient:
    """A GraphQL client scoped to exactly one ShopifyStore.

    Construct a fresh instance per store — never share a client or headers
    across two ShopifyStore rows. (The underlying HTTP session *is* pooled
    per store domain for connection reuse — see _get_pooled_session — but
    that carries no per-store secrets and never crosses store boundaries.)
    """

    def __init__(self, store: ShopifyStore, *, session: requests.Session | None = None):
        self.store = store
        self.endpoint = (
            f"https://{store.shop_domain}/admin/api/{store.api_version}/graphql.json"
        )
        self._session = session or _get_pooled_session(store.shop_domain)
        self._max_retries = get_max_retries()
        self._rate_limit_buffer = get_rate_limit_buffer()
        self._max_backoff = get_max_backoff_seconds()
        self._timeout = get_request_timeout()

    def _headers(self) -> dict[str, str]:
        # get_access_token() resolves a static access_token or transparently
        # exchanges/refreshes one via the client credentials grant — see
        # auth.py. Resolved per call (not cached on self) so a token
        # refreshed mid-session is always picked up.
        return {
            "Content-Type": "application/json",
            "X-Shopify-Access-Token": get_access_token(self.store),
        }

    def execute(self, query: str, variables: dict[str, Any] | None = None) -> dict[str, Any]:
        """Execute a GraphQL query or mutation against this store.

        Returns the "data" portion of a successful response. Raises
        ShopifyGraphQLError if the response body has an "errors" array (and
        it isn't a throttling error), ShopifyRateLimitError if the request
        was still throttled after all retries, and ShopifyRequestError if the
        transport itself fails after all retries are exhausted.

        Retried, up to SHOPIFY_TOOLKIT_MAX_RETRIES times with capped
        exponential backoff:
          * network errors (connection refused, timeouts, ...) — except a
            read timeout on a mutation: the request was already sent and may
            have been applied, so it's surfaced rather than risk a duplicate
            write.
          * throttling (HTTP 429 or a THROTTLED GraphQL error) — Shopify
            rejects these before executing anything, so retrying is safe even
            for mutations. Retry-After is honoured when present.
          * HTTP 502/503/504 — queries only. A mutation that hit a gateway
            timeout may still have been applied, so it's surfaced to the
            caller instead of risking a duplicate write.
        """
        payload = {"query": query, "variables": variables or {}}
        is_mutation = _is_mutation(query)

        attempt = 0
        while True:
            try:
                response = self._session.post(
                    self.endpoint,
                    json=payload,
                    headers=self._headers(),
                    timeout=self._timeout,
                )
            except requests.ReadTimeout as exc:
                if is_mutation:
                    raise ShopifyRequestError(
                        f"Mutation to {self.endpoint} timed out waiting for a response; not "
                        f"retried since it may already have been applied: {exc}"
                    ) from exc
                if attempt >= self._max_retries:
                    raise ShopifyRequestError(
                        f"Request to {self.endpoint} failed after {self._max_retries} "
                        f"retries: {exc}"
                    ) from exc
                attempt += 1
                self._sleep_backoff(attempt, reason=type(exc).__name__)
                continue
            except requests.RequestException as exc:
                if attempt >= self._max_retries:
                    raise ShopifyRequestError(
                        f"Request to {self.endpoint} failed after {self._max_retries} "
                        f"retries: {exc}"
                    ) from exc
                attempt += 1
                self._sleep_backoff(attempt, reason=type(exc).__name__)
                continue

            if (
                response.status_code in _RETRYABLE_STATUS_CODES
                and not is_mutation
                and attempt < self._max_retries
            ):
                attempt += 1
                self._sleep_backoff(attempt, reason=f"HTTP {response.status_code}")
                continue

            try:
                return self._handle_response(response)
            except ShopifyRateLimitError as exc:
                if attempt >= self._max_retries:
                    raise
                attempt += 1
                self._sleep_backoff(attempt, reason="throttled", retry_after=exc.retry_after)

    def _handle_response(self, response: requests.Response) -> dict[str, Any]:
        if response.status_code == 429:
            raise ShopifyRateLimitError(
                "Shopify returned HTTP 429 Too Many Requests",
                retry_after=response.headers.get("Retry-After"),
            )

        try:
            body = response.json()
        except ValueError as exc:
            raise ShopifyRequestError(
                f"Non-JSON response from Shopify (status {response.status_code})"
            ) from exc

        errors = body.get("errors")
        if errors:
            # Shopify doesn't always send the standard GraphQL errors array of dicts — an auth
            # failure (401) sends a bare string instead. Normalize before it reaches
            # _is_throttled() or the exception below.
            if isinstance(errors, str):
                errors = [{"message": errors}]
            # THROTTLED is Shopify's cost-based rate-limit signal, surfaced
            # inside the errors array rather than as an HTTP status code.
            if _is_throttled(errors):
                raise ShopifyRateLimitError("Shopify GraphQL request was throttled")
            raise ShopifyGraphQLError(
                f"Shopify GraphQL returned errors: {errors}", errors=errors
            )

        self._maybe_backoff_for_cost(body)

        return body.get("data", {})

    def _maybe_backoff_for_cost(self, body: dict[str, Any]) -> None:
        """Read extensions.cost.throttleStatus and pause if the bucket is low.

        We sleep before returning to the caller, once we already know the
        bucket dropped below SHOPIFY_TOOLKIT_RATE_LIMIT_BUFFER on *this*
        response — rather than deferring the check to the next call. That
        keeps the client safe even for a caller who only ever makes a single
        call in a request cycle: it won't hand back control while the bucket
        is still recovering. The sleep is capped at
        SHOPIFY_TOOLKIT_MAX_BACKOFF_SECONDS so a single call can't block the
        thread indefinitely under a sync WSGI worker — a caller needing a
        longer wait should catch ShopifyRateLimitError and retry via its own
        queue instead.
        """
        throttle_status = (body.get("extensions") or {}).get("cost", {}).get(
            "throttleStatus", {}
        )
        available = throttle_status.get("currentlyAvailable")
        restore_rate = throttle_status.get("restoreRate") or 50
        if available is not None and available < self._rate_limit_buffer:
            deficit = self._rate_limit_buffer - available
            sleep_for = min(max(deficit / restore_rate, 0), self._max_backoff)
            logger.info(
                "Shopify rate limit bucket low (%s available, buffer %s); "
                "sleeping %.2fs before returning",
                available,
                self._rate_limit_buffer,
                sleep_for,
            )
            time.sleep(sleep_for)

    def _sleep_backoff(
        self, attempt: int, *, reason: str, retry_after: str | None = None
    ) -> None:
        delay = _parse_retry_after(retry_after)
        if delay is None:
            delay = 2 ** (attempt - 1)
        delay = min(delay, self._max_backoff)
        logger.info(
            "Retrying Shopify request to %s (attempt %s, %s) after %.2fs",
            self.store.shop_domain,
            attempt,
            reason,
            delay,
        )
        time.sleep(delay)


def _is_mutation(query: str) -> bool:
    return _MUTATION_RE.search(query) is not None


def _parse_retry_after(value: str | None) -> float | None:
    """Seconds from a Retry-After header, or None if absent/unparseable.

    Shopify sends a plain number of seconds (e.g. "2.0"); the HTTP-date form isn't used by the
    Admin API, so it's treated as unparseable and falls back to exponential backoff.
    """
    if not value:
        return None
    try:
        seconds = float(value)
    except ValueError:
        return None
    return max(seconds, 0.0)


def _is_throttled(errors: list) -> bool:
    for error in errors:
        if not isinstance(error, dict):
            continue
        extensions = error.get("extensions") or {}
        if extensions.get("code") == "THROTTLED":
            return True
    return False
