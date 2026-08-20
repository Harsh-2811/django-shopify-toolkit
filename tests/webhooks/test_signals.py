import base64
import hashlib
import hmac
import json

import pytest
from django.test import RequestFactory

from shopify_toolkit.models import WebhookEvent
from shopify_toolkit.signals import webhook_received
from shopify_toolkit.webhooks.views import receive_webhook

SECRET = "test-api-secret"


def _sign(body: bytes) -> str:
    digest = hmac.new(SECRET.encode("utf-8"), body, hashlib.sha256).digest()
    return base64.b64encode(digest).decode("utf-8")


@pytest.mark.django_db
def test_webhook_received_signal_fires_with_correct_kwargs(shopify_store):
    received = []

    def handler(sender, **kwargs):
        received.append((sender, kwargs))

    webhook_received.connect(handler)
    try:
        body = json.dumps({"id": 123}).encode("utf-8")
        request = RequestFactory().generic(
            "POST",
            "/webhooks/receive/",
            data=body,
            content_type="application/json",
            HTTP_X_SHOPIFY_HMAC_SHA256=_sign(body),
            HTTP_X_SHOPIFY_SHOP_DOMAIN=shopify_store.shop_domain,
            HTTP_X_SHOPIFY_TOPIC="orders/create",
        )
        response = receive_webhook(request)

        assert response.status_code == 200
        assert len(received) == 1
        sender, kwargs = received[0]
        assert sender is WebhookEvent
        assert kwargs["store"] == shopify_store
        assert kwargs["topic"] == "orders/create"
        assert kwargs["payload"] == {"id": 123}
        assert isinstance(kwargs["event"], WebhookEvent)
        assert kwargs["event"].pk is not None
    finally:
        webhook_received.disconnect(handler)


@pytest.mark.django_db
def test_webhook_received_signal_does_not_fire_on_invalid_signature(shopify_store):
    received = []

    def handler(sender, **kwargs):
        received.append(kwargs)

    webhook_received.connect(handler)
    try:
        body = json.dumps({"id": 123}).encode("utf-8")
        request = RequestFactory().generic(
            "POST",
            "/webhooks/receive/",
            data=body,
            content_type="application/json",
            HTTP_X_SHOPIFY_HMAC_SHA256="bogus",
            HTTP_X_SHOPIFY_SHOP_DOMAIN=shopify_store.shop_domain,
        )
        response = receive_webhook(request)

        assert response.status_code == 401
        assert received == []
    finally:
        webhook_received.disconnect(handler)
