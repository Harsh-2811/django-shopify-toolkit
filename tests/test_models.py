import pytest
from django.core.exceptions import ImproperlyConfigured
from django.db import connection

from shopify_toolkit.conf import get_api_secret
from shopify_toolkit.models import WebhookEvent


@pytest.mark.django_db
def test_shopify_store_str(shopify_store):
    assert str(shopify_store) == "test-store.myshopify.com"


@pytest.mark.django_db
def test_shopify_store_defaults(shopify_store):
    assert shopify_store.api_version == "2025-01"
    assert shopify_store.is_active is True
    assert shopify_store.scopes == ""


@pytest.mark.django_db
def test_access_token_encrypted_at_rest(shopify_store):
    # The raw DB value must not equal the plaintext token — EncryptedCharField
    # should actually be encrypting it, not just proxying a CharField.
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT access_token FROM shopify_toolkit_shopifystore WHERE id = %s",
            [shopify_store.id],
        )
        raw_value = cursor.fetchone()[0]
    assert raw_value != "shpat_test_token_1"

    # But reading back through the ORM decrypts transparently.
    shopify_store.refresh_from_db()
    assert shopify_store.access_token == "shpat_test_token_1"


@pytest.mark.django_db
def test_webhook_event_linked_to_store(shopify_store):
    event = WebhookEvent.objects.create(
        store=shopify_store,
        topic="orders/create",
        payload={"id": 123},
    )
    assert event in shopify_store.webhook_events.all()
    assert event.processed is False
    assert event.processing_error == ""


@pytest.mark.django_db
def test_webhook_event_str(shopify_store):
    event = WebhookEvent.objects.create(
        store=shopify_store, topic="orders/create", payload={"id": 123}
    )
    assert str(event) == "orders/create (test-store.myshopify.com)"


def test_get_api_secret_raises_when_missing(settings):
    settings.SHOPIFY_TOOLKIT_API_SECRET = None
    with pytest.raises(ImproperlyConfigured):
        get_api_secret()


def test_get_api_secret_returns_value(settings):
    settings.SHOPIFY_TOOLKIT_API_SECRET = "abc123"
    assert get_api_secret() == "abc123"
