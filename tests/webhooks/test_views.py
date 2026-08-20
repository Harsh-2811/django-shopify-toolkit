import base64
import hashlib
import hmac
import json

import pytest
from django.test import RequestFactory

from shopify_toolkit.models import WebhookEvent
from shopify_toolkit.webhooks.views import receive_webhook

SECRET = "test-api-secret"


def _sign(body: bytes) -> str:
    digest = hmac.new(SECRET.encode("utf-8"), body, hashlib.sha256).digest()
    return base64.b64encode(digest).decode("utf-8")


def _post(body: bytes, **headers):
    return RequestFactory().generic(
        "POST", "/webhooks/receive/", data=body, content_type="application/json", **headers
    )


@pytest.mark.django_db
def test_receive_webhook_valid_signature_creates_event(shopify_store):
    body = json.dumps({"id": 123}).encode("utf-8")
    request = _post(
        body,
        HTTP_X_SHOPIFY_HMAC_SHA256=_sign(body),
        HTTP_X_SHOPIFY_SHOP_DOMAIN=shopify_store.shop_domain,
        HTTP_X_SHOPIFY_TOPIC="orders/create",
    )

    response = receive_webhook(request)

    assert response.status_code == 200
    event = WebhookEvent.objects.get()
    assert event.store == shopify_store
    assert event.topic == "orders/create"
    assert event.payload == {"id": 123}


@pytest.mark.django_db
def test_receive_webhook_invalid_signature_returns_401_and_saves_nothing(shopify_store):
    body = json.dumps({"id": 123}).encode("utf-8")
    request = _post(
        body,
        HTTP_X_SHOPIFY_HMAC_SHA256="bogus-signature",
        HTTP_X_SHOPIFY_SHOP_DOMAIN=shopify_store.shop_domain,
    )

    response = receive_webhook(request)

    assert response.status_code == 401
    assert WebhookEvent.objects.count() == 0


@pytest.mark.django_db
def test_receive_webhook_unknown_store_returns_404():
    body = json.dumps({"id": 123}).encode("utf-8")
    request = _post(
        body,
        HTTP_X_SHOPIFY_HMAC_SHA256=_sign(body),
        HTTP_X_SHOPIFY_SHOP_DOMAIN="unknown-store.myshopify.com",
    )

    response = receive_webhook(request)

    assert response.status_code == 404
    assert WebhookEvent.objects.count() == 0
