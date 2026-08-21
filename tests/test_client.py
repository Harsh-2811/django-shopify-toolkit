import pytest
import responses
from requests.exceptions import ConnectionError as RequestsConnectionError

from shopify_toolkit.client import ShopifyGraphQLClient
from shopify_toolkit.exceptions import (
    ShopifyGraphQLError,
    ShopifyRateLimitError,
    ShopifyRequestError,
)

ENDPOINT = "https://test-store.myshopify.com/admin/api/2025-01/graphql.json"
OTHER_ENDPOINT = "https://other-store.myshopify.com/admin/api/2025-01/graphql.json"


@responses.activate
@pytest.mark.django_db
def test_execute_success(shopify_store):
    responses.add(
        responses.POST,
        ENDPOINT,
        json={
            "data": {"shop": {"name": "Test Shop"}},
            "extensions": {
                "cost": {"throttleStatus": {"currentlyAvailable": 1000, "restoreRate": 50}}
            },
        },
        status=200,
    )
    client = ShopifyGraphQLClient(shopify_store)
    data = client.execute("query { shop { name } }")

    assert data == {"shop": {"name": "Test Shop"}}
    assert len(responses.calls) == 1
    assert responses.calls[0].request.headers["X-Shopify-Access-Token"] == "shpat_test_token_1"


@responses.activate
@pytest.mark.django_db
def test_execute_graphql_errors_array_raises(shopify_store):
    responses.add(
        responses.POST,
        ENDPOINT,
        json={"errors": [{"message": "Field 'bogus' doesn't exist"}]},
        status=200,
    )
    client = ShopifyGraphQLClient(shopify_store)

    with pytest.raises(ShopifyGraphQLError) as exc_info:
        client.execute("query { bogus }")
    assert "bogus" in str(exc_info.value)
    assert exc_info.value.errors


@responses.activate
@pytest.mark.django_db
def test_execute_bare_string_errors_raises_graphql_error_not_attributeerror(shopify_store):
    """Shopify doesn't always shape "errors" as the standard GraphQL array of dicts — an auth
    failure (401) sends a bare string instead. Must raise ShopifyGraphQLError, not crash."""
    responses.add(
        responses.POST,
        ENDPOINT,
        json={"errors": "[API] Invalid API key or access token (unrecognized login or wrong password)"},
        status=401,
    )
    client = ShopifyGraphQLClient(shopify_store)

    with pytest.raises(ShopifyGraphQLError) as exc_info:
        client.execute("query { shop { name } }")

    assert "Invalid API key" in str(exc_info.value)
    assert exc_info.value.errors == [
        {"message": "[API] Invalid API key or access token (unrecognized login or wrong password)"}
    ]


@responses.activate
@pytest.mark.django_db
def test_execute_low_cost_bucket_triggers_backoff_sleep(shopify_store, monkeypatch):
    sleeps = []
    monkeypatch.setattr("shopify_toolkit.client.time.sleep", lambda s: sleeps.append(s))

    responses.add(
        responses.POST,
        ENDPOINT,
        json={
            "data": {"shop": {"name": "Test Shop"}},
            "extensions": {
                "cost": {"throttleStatus": {"currentlyAvailable": 10, "restoreRate": 50}}
            },
        },
        status=200,
    )
    client = ShopifyGraphQLClient(shopify_store)
    data = client.execute("query { shop { name } }")

    # default SHOPIFY_TOOLKIT_RATE_LIMIT_BUFFER is 100, bucket is at 10 -> must back off
    assert data == {"shop": {"name": "Test Shop"}}
    assert sleeps and sleeps[0] > 0


@responses.activate
@pytest.mark.django_db
def test_execute_throttled_error_code_raises_rate_limit_error(shopify_store, monkeypatch):
    monkeypatch.setattr("shopify_toolkit.client.time.sleep", lambda s: None)
    responses.add(
        responses.POST,
        ENDPOINT,
        json={"errors": [{"message": "Throttled", "extensions": {"code": "THROTTLED"}}]},
        status=200,
    )
    client = ShopifyGraphQLClient(shopify_store)

    with pytest.raises(ShopifyRateLimitError):
        client.execute("query { shop { name } }")


@responses.activate
@pytest.mark.django_db
def test_execute_retries_transient_network_error_then_succeeds(shopify_store, monkeypatch, settings):
    settings.SHOPIFY_TOOLKIT_MAX_RETRIES = 2
    sleeps = []
    monkeypatch.setattr("shopify_toolkit.client.time.sleep", lambda s: sleeps.append(s))

    responses.add(responses.POST, ENDPOINT, body=RequestsConnectionError("boom"))
    responses.add(responses.POST, ENDPOINT, json={"data": {"shop": {"name": "Recovered"}}}, status=200)

    client = ShopifyGraphQLClient(shopify_store)
    data = client.execute("query { shop { name } }")

    assert data == {"shop": {"name": "Recovered"}}
    assert len(responses.calls) == 2
    assert sleeps == [1]  # exponential backoff: 2**(1-1)


@responses.activate
@pytest.mark.django_db
def test_execute_raises_after_exhausting_retries(shopify_store, monkeypatch, settings):
    settings.SHOPIFY_TOOLKIT_MAX_RETRIES = 1
    monkeypatch.setattr("shopify_toolkit.client.time.sleep", lambda s: None)

    responses.add(responses.POST, ENDPOINT, body=RequestsConnectionError("boom"))
    responses.add(responses.POST, ENDPOINT, body=RequestsConnectionError("boom again"))

    client = ShopifyGraphQLClient(shopify_store)
    with pytest.raises(ShopifyRequestError):
        client.execute("query { shop { name } }")

    assert len(responses.calls) == 2  # initial attempt + 1 retry


@responses.activate
@pytest.mark.django_db
def test_two_stores_never_share_client_or_leak_headers(shopify_store, other_shopify_store, monkeypatch):
    monkeypatch.setattr("shopify_toolkit.client.time.sleep", lambda s: None)
    responses.add(responses.POST, ENDPOINT, json={"data": {"shop": {"name": "Store A"}}}, status=200)
    responses.add(responses.POST, OTHER_ENDPOINT, json={"data": {"shop": {"name": "Store B"}}}, status=200)

    client_a = ShopifyGraphQLClient(shopify_store)
    client_b = ShopifyGraphQLClient(other_shopify_store)

    assert client_a._session is not client_b._session
    assert client_a.endpoint != client_b.endpoint

    client_a.execute("query { shop { name } }")
    client_b.execute("query { shop { name } }")

    call_a, call_b = responses.calls[0], responses.calls[1]
    assert call_a.request.url == ENDPOINT
    assert call_b.request.url == OTHER_ENDPOINT
    assert call_a.request.headers["X-Shopify-Access-Token"] == "shpat_test_token_1"
    assert call_b.request.headers["X-Shopify-Access-Token"] == "shpat_test_token_2"


@pytest.mark.django_db
def test_same_store_reuses_pooled_session(shopify_store):
    # Two separate ShopifyGraphQLClient instances for the *same* store
    # should share one connection-pooled requests.Session (no per-call
    # session churn), while still building headers fresh per call.
    client_a = ShopifyGraphQLClient(shopify_store)
    client_b = ShopifyGraphQLClient(shopify_store)

    assert client_a._session is client_b._session


@pytest.mark.django_db
def test_different_stores_never_share_pooled_session(shopify_store, other_shopify_store):
    client_a = ShopifyGraphQLClient(shopify_store)
    client_b = ShopifyGraphQLClient(other_shopify_store)

    assert client_a._session is not client_b._session


@pytest.mark.django_db
def test_explicit_session_override_is_not_pooled(shopify_store):
    import requests as requests_module

    custom_session = requests_module.Session()
    client = ShopifyGraphQLClient(shopify_store, session=custom_session)

    assert client._session is custom_session


@responses.activate
@pytest.mark.django_db
def test_low_cost_bucket_backoff_is_capped_at_max_backoff(shopify_store, monkeypatch, settings):
    settings.SHOPIFY_TOOLKIT_MAX_BACKOFF_SECONDS = 3
    sleeps = []
    monkeypatch.setattr("shopify_toolkit.client.time.sleep", lambda s: sleeps.append(s))

    # buffer(100) - available(0) = 100 deficit, restoreRate 1/s -> would be a
    # 100s uncapped sleep. Must be clamped to the 3s cap instead.
    responses.add(
        responses.POST,
        ENDPOINT,
        json={
            "data": {"shop": {"name": "Test Shop"}},
            "extensions": {"cost": {"throttleStatus": {"currentlyAvailable": 0, "restoreRate": 1}}},
        },
        status=200,
    )
    client = ShopifyGraphQLClient(shopify_store)
    client.execute("query { shop { name } }")

    assert sleeps == [3]


@pytest.mark.django_db
def test_session_pool_evicts_least_recently_used_beyond_max_size(settings, monkeypatch):
    from shopify_toolkit.client import _get_pooled_session, _session_pool

    settings.SHOPIFY_TOOLKIT_MAX_POOLED_SESSIONS = 2
    _session_pool.clear()

    session_a = _get_pooled_session("evict-a.myshopify.com")
    session_b = _get_pooled_session("evict-b.myshopify.com")
    assert list(_session_pool.keys()) == ["evict-a.myshopify.com", "evict-b.myshopify.com"]

    close_calls = []
    monkeypatch.setattr(session_b, "close", lambda: close_calls.append(session_b))

    # Touch A again so B becomes the least-recently-used.
    assert _get_pooled_session("evict-a.myshopify.com") is session_a

    # Adding a third store should evict B (LRU), not A (recently touched).
    _get_pooled_session("evict-c.myshopify.com")

    assert list(_session_pool.keys()) == ["evict-a.myshopify.com", "evict-c.myshopify.com"]
    assert "evict-b.myshopify.com" not in _session_pool
    assert close_calls == [session_b]  # evicted session must be closed, not just dropped
    _session_pool.clear()
