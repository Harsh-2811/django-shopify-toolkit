import pytest
import responses

from shopify_toolkit.exceptions import ShopifyGraphQLError, ShopifyUserError
from shopify_toolkit.webhooks import registry

ENDPOINT = "https://test-store.myshopify.com/admin/api/2025-01/graphql.json"
OTHER_ENDPOINT = "https://other-store.myshopify.com/admin/api/2025-01/graphql.json"


@responses.activate
@pytest.mark.django_db
def test_register_webhook_success(shopify_store):
    responses.add(
        responses.POST,
        ENDPOINT,
        json={
            "data": {
                "webhookSubscriptionCreate": {
                    "webhookSubscription": {
                        "id": "gid://shopify/WebhookSubscription/1",
                        "topic": "ORDERS_CREATE",
                        "callbackUrl": "https://example.com/webhooks/receive/",
                        "createdAt": "2026-01-01T00:00:00Z",
                    },
                    "userErrors": [],
                }
            }
        },
        status=200,
    )
    sub = registry.register_webhook(
        shopify_store, topic="ORDERS_CREATE", callback_url="https://example.com/webhooks/receive/"
    )
    assert sub.topic == "ORDERS_CREATE"


@responses.activate
@pytest.mark.django_db
def test_register_webhook_user_error_raises(shopify_store):
    responses.add(
        responses.POST,
        ENDPOINT,
        json={
            "data": {
                "webhookSubscriptionCreate": {
                    "webhookSubscription": None,
                    "userErrors": [{"field": ["callbackUrl"], "message": "is invalid"}],
                }
            }
        },
        status=200,
    )
    with pytest.raises(ShopifyUserError):
        registry.register_webhook(shopify_store, topic="ORDERS_CREATE", callback_url="not-a-url")


@responses.activate
@pytest.mark.django_db
def test_list_webhooks_graphql_error_raises(shopify_store):
    responses.add(responses.POST, ENDPOINT, json={"errors": [{"message": "boom"}]}, status=200)
    with pytest.raises(ShopifyGraphQLError):
        registry.list_webhooks(shopify_store)


@responses.activate
@pytest.mark.django_db
def test_store_isolation_list_webhooks(shopify_store, other_shopify_store):
    empty = {"data": {"webhookSubscriptions": {"edges": []}}}
    responses.add(responses.POST, ENDPOINT, json=empty, status=200)
    responses.add(responses.POST, OTHER_ENDPOINT, json=empty, status=200)

    registry.list_webhooks(shopify_store)
    registry.list_webhooks(other_shopify_store)

    call_a, call_b = responses.calls[0], responses.calls[1]
    assert call_a.request.headers["X-Shopify-Access-Token"] == "shpat_test_token_1"
    assert call_b.request.headers["X-Shopify-Access-Token"] == "shpat_test_token_2"
