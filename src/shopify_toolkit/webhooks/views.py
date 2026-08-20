"""Webhook receiver view.

Verifies the HMAC signature, resolves the store from the
X-Shopify-Shop-Domain header, and saves a WebhookEvent row tied to it.
"""
from __future__ import annotations

import json
import logging

from django.http import HttpRequest, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from ..models import ShopifyStore, WebhookEvent
from ..signals import webhook_received
from .verify import verify_webhook

logger = logging.getLogger(__name__)


@csrf_exempt
@require_POST
def receive_webhook(request: HttpRequest) -> HttpResponse:
    raw_body = request.body
    hmac_header = request.headers.get("X-Shopify-Hmac-Sha256")

    if not verify_webhook(raw_body, hmac_header):
        logger.warning("Rejected webhook with invalid or missing HMAC signature")
        return HttpResponse(status=401)

    shop_domain = request.headers.get("X-Shopify-Shop-Domain")
    topic = request.headers.get("X-Shopify-Topic", "")

    try:
        store = ShopifyStore.objects.get(shop_domain=shop_domain, is_active=True)
    except ShopifyStore.DoesNotExist:
        logger.warning("Rejected webhook for unknown or inactive store: %s", shop_domain)
        return HttpResponse(status=404)

    try:
        payload = json.loads(raw_body) if raw_body else {}
    except ValueError:
        payload = {}

    event = WebhookEvent.objects.create(store=store, topic=topic, payload=payload)
    webhook_received.send(sender=WebhookEvent, store=store, topic=topic, payload=payload, event=event)

    return HttpResponse(status=200)
