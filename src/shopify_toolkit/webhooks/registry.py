"""Register and list Shopify webhook subscriptions via GraphQL.

Covers: register webhook subscription, list webhook subscriptions.
"""
from __future__ import annotations

from dataclasses import dataclass

from ..client import ShopifyGraphQLClient
from ..exceptions import ShopifyUserError
from ..models import ShopifyStore

REGISTER_WEBHOOK_MUTATION = """
mutation RegisterWebhook($topic: WebhookSubscriptionTopic!, $webhookSubscription: WebhookSubscriptionInput!) {
    webhookSubscriptionCreate(topic: $topic, webhookSubscription: $webhookSubscription) {
        webhookSubscription {
            id
            topic
            callbackUrl
            createdAt
        }
        userErrors {
            field
            message
        }
    }
}
"""

LIST_WEBHOOKS_QUERY = """
query ListWebhooks($first: Int!) {
    webhookSubscriptions(first: $first) {
        edges {
            node {
                id
                topic
                callbackUrl
                createdAt
            }
        }
    }
}
"""


@dataclass
class WebhookSubscription:
    id: str
    topic: str
    callback_url: str
    created_at: str


def _parse_subscription(node: dict) -> WebhookSubscription:
    return WebhookSubscription(
        id=node["id"],
        topic=node["topic"],
        callback_url=node.get("callbackUrl", ""),
        created_at=node.get("createdAt", ""),
    )


def register_webhook(store: ShopifyStore, *, topic: str, callback_url: str) -> WebhookSubscription:
    """Register a webhook subscription for this store."""
    client = ShopifyGraphQLClient(store)
    data = client.execute(
        REGISTER_WEBHOOK_MUTATION,
        {
            "topic": topic,
            "webhookSubscription": {"callbackUrl": callback_url, "format": "JSON"},
        },
    )
    result = data["webhookSubscriptionCreate"]
    if result["userErrors"]:
        raise ShopifyUserError(
            f"Shopify returned userErrors: {result['userErrors']}",
            user_errors=result["userErrors"],
        )
    return _parse_subscription(result["webhookSubscription"])


def list_webhooks(store: ShopifyStore, *, first: int = 50) -> list[WebhookSubscription]:
    """List existing webhook subscriptions for this store."""
    client = ShopifyGraphQLClient(store)
    data = client.execute(LIST_WEBHOOKS_QUERY, {"first": first})
    edges = data["webhookSubscriptions"]["edges"]
    return [_parse_subscription(edge["node"]) for edge in edges]
