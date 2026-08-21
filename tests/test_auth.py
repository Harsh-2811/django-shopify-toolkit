from datetime import timedelta

import pytest
import responses
from django.db import connections, transaction
from django.db.utils import NotSupportedError
from django.utils import timezone

from shopify_toolkit.auth import get_access_token
from shopify_toolkit.exceptions import ShopifyRequestError, ShopifyStoreNotConfigured
from shopify_toolkit.models import ShopifyStore

EXCHANGE_ENDPOINT = "https://ccg-store.myshopify.com/admin/oauth/access_token"
OTHER_EXCHANGE_ENDPOINT = "https://other-ccg-store.myshopify.com/admin/oauth/access_token"


@pytest.fixture
def ccg_store(db):
    """A store authenticated via Client ID/Secret — no static token yet."""
    return ShopifyStore.objects.create(
        shop_domain="ccg-store.myshopify.com",
        client_id="client-id-1",
        client_secret="client-secret-1",
    )


@pytest.fixture
def other_ccg_store(db):
    return ShopifyStore.objects.create(
        shop_domain="other-ccg-store.myshopify.com",
        client_id="client-id-2",
        client_secret="client-secret-2",
    )


@pytest.mark.django_db
def test_legacy_static_token_used_directly_no_network_call(shopify_store):
    # shopify_store (from conftest) has only access_token set — no
    # client_id/secret, so get_access_token must never hit the network.
    with responses.RequestsMock(assert_all_requests_are_fired=False) as rsps:
        token = get_access_token(shopify_store)
        assert token == "shpat_test_token_1"
        assert len(rsps.calls) == 0


@responses.activate
@pytest.mark.django_db
def test_ccg_store_exchanges_and_caches_token(ccg_store):
    responses.add(
        responses.POST,
        EXCHANGE_ENDPOINT,
        json={"access_token": "shpua_fresh_token", "scope": "read_products", "expires_in": 86399},
        status=200,
    )

    token = get_access_token(ccg_store)

    assert token == "shpua_fresh_token"
    assert len(responses.calls) == 1
    sent_body = responses.calls[0].request.body
    assert "client_id=client-id-1" in sent_body
    assert "client_secret=client-secret-1" in sent_body
    assert "grant_type=client_credentials" in sent_body

    ccg_store.refresh_from_db()
    assert ccg_store.access_token == "shpua_fresh_token"
    assert ccg_store.access_token_expires_at is not None


@responses.activate
@pytest.mark.django_db
def test_ccg_store_reuses_still_valid_cached_token(ccg_store):
    ccg_store.access_token = "shpua_cached_token"
    ccg_store.access_token_expires_at = timezone.now() + timedelta(hours=12)
    ccg_store.save()

    token = get_access_token(ccg_store)

    assert token == "shpua_cached_token"
    assert len(responses.calls) == 0  # reused cache, no exchange needed


@responses.activate
@pytest.mark.django_db
def test_ccg_store_refreshes_expired_cached_token(ccg_store):
    ccg_store.access_token = "shpua_stale_token"
    ccg_store.access_token_expires_at = timezone.now() - timedelta(seconds=5)
    ccg_store.save()

    responses.add(
        responses.POST,
        EXCHANGE_ENDPOINT,
        json={"access_token": "shpua_renewed_token", "expires_in": 86399},
        status=200,
    )

    token = get_access_token(ccg_store)

    assert token == "shpua_renewed_token"
    assert len(responses.calls) == 1


@pytest.mark.django_db
def test_store_with_neither_credential_raises(db):
    store = ShopifyStore.objects.create(shop_domain="unconfigured-store.myshopify.com")
    with pytest.raises(ShopifyStoreNotConfigured):
        get_access_token(store)


@responses.activate
@pytest.mark.django_db
def test_exchange_non_200_raises_request_error(ccg_store):
    responses.add(
        responses.POST,
        EXCHANGE_ENDPOINT,
        json={"error": "invalid_client"},
        status=401,
    )
    with pytest.raises(ShopifyRequestError):
        get_access_token(ccg_store)


@responses.activate
@pytest.mark.django_db
def test_store_isolation_ccg_exchange(ccg_store, other_ccg_store):
    responses.add(
        responses.POST,
        EXCHANGE_ENDPOINT,
        json={"access_token": "shpua_store_a_token", "expires_in": 86399},
        status=200,
    )
    responses.add(
        responses.POST,
        OTHER_EXCHANGE_ENDPOINT,
        json={"access_token": "shpua_store_b_token", "expires_in": 86399},
        status=200,
    )

    token_a = get_access_token(ccg_store)
    token_b = get_access_token(other_ccg_store)

    assert token_a == "shpua_store_a_token"
    assert token_b == "shpua_store_b_token"

    ccg_store.refresh_from_db()
    other_ccg_store.refresh_from_db()
    assert ccg_store.access_token != other_ccg_store.access_token


@responses.activate
@pytest.mark.django_db
def test_locked_exchange_skips_reexchange_if_already_refreshed(ccg_store):
    # Simulate a concurrent request having already refreshed the token in
    # the DB (e.g. it acquired the row lock first) between when this
    # in-memory `ccg_store` object was loaded and when get_access_token()
    # is called on it — its own view of access_token is still empty/stale.
    ShopifyStore.objects.filter(pk=ccg_store.pk).update(
        access_token="shpua_already_refreshed_by_another_request",
        access_token_expires_at=timezone.now() + timedelta(hours=12),
    )
    assert ccg_store.access_token == ""  # in-memory copy is unaware of that update

    token = get_access_token(ccg_store)

    assert token == "shpua_already_refreshed_by_another_request"
    assert len(responses.calls) == 0  # re-checked under the lock, no exchange happened


@responses.activate
@pytest.mark.django_db
def test_ccg_exchange_skips_row_lock_on_non_locking_vendor(monkeypatch, ccg_store):
    monkeypatch.setattr(connections["default"], "vendor", "mongodb")

    def _atomic_must_not_be_called(*args, **kwargs):
        raise NotSupportedError(
            "transaction.atomic() is not supported on this backend "
            "(simulating django-mongodb-backend's real, verified behavior)"
        )

    monkeypatch.setattr("shopify_toolkit.auth.transaction.atomic", _atomic_must_not_be_called)

    responses.add(
        responses.POST,
        EXCHANGE_ENDPOINT,
        json={"access_token": "shpua_mongo_token", "expires_in": 86399},
        status=200,
    )

    token = get_access_token(ccg_store)

    assert token == "shpua_mongo_token"
    assert len(responses.calls) == 1


@responses.activate
@pytest.mark.django_db
@pytest.mark.skipif(
    connections["default"].vendor != "postgresql",
    reason="asserts the real-row-lock path specifically; only meaningful when this suite is "
    "actually running against Postgres (e.g. skipped under tests.settings_mongodb)",
)
def test_ccg_exchange_uses_row_lock_on_postgresql(monkeypatch, ccg_store):
    """Inverse sanity check of the test above: on a real row-locking vendor (this suite's actual
    Postgres connection), the locked path must still be taken — transaction.atomic() actually
    gets called, not silently skipped for every backend."""
    assert connections["default"].vendor == "postgresql"  # sanity: confirms what's being tested

    calls = []
    real_atomic = transaction.atomic

    def _spy_atomic(*args, **kwargs):
        calls.append((args, kwargs))
        return real_atomic(*args, **kwargs)

    monkeypatch.setattr("shopify_toolkit.auth.transaction.atomic", _spy_atomic)

    responses.add(
        responses.POST,
        EXCHANGE_ENDPOINT,
        json={"access_token": "shpua_pg_token", "expires_in": 86399},
        status=200,
    )

    token = get_access_token(ccg_store)

    assert token == "shpua_pg_token"
    assert len(calls) == 1
