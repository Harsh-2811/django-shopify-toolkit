"""Python-facing service functions for the Orders area.

Reuses client.py — no new HTTP logic lives here, only queries/mutations and
parsing.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator

from .._utils import camelize_keys, iter_pages, parse_page_info, raise_for_user_errors
from ..client import ShopifyGraphQLClient
from ..models import ShopifyStore
from .queries import (
    FULFILL_ORDER_MUTATION,
    GET_ORDER_QUERY,
    LIST_ORDERS_QUERY,
    UPDATE_ORDER_MUTATION,
)


@dataclass
class Order:
    id: str
    name: str
    email: str | None
    financial_status: str
    fulfillment_status: str
    total_price: str | None
    currency_code: str | None
    created_at: str
    updated_at: str


@dataclass
class OrderPage:
    orders: list[Order]
    has_next_page: bool
    end_cursor: str | None


def _parse_order(node: dict) -> Order:
    money = (node.get("totalPriceSet") or {}).get("shopMoney") or {}
    return Order(
        id=node["id"],
        name=node["name"],
        email=node.get("email"),
        financial_status=node.get("displayFinancialStatus", ""),
        fulfillment_status=node.get("displayFulfillmentStatus", ""),
        total_price=money.get("amount"),
        currency_code=money.get("currencyCode"),
        created_at=node.get("createdAt", ""),
        updated_at=node.get("updatedAt", ""),
    )


def list_orders(
    store: ShopifyStore,
    *,
    first: int = 50,
    after: str | None = None,
    query: str | None = None,
) -> OrderPage:
    """List orders for a store, paginated.

    `query` is passed through as Shopify's search syntax, e.g.
    "financial_status:paid created_at:>=2026-01-01".
    See https://shopify.dev/docs/api/usage/search-syntax.
    Omitted (None) means no filtering.
    """
    client = ShopifyGraphQLClient(store)
    data = client.execute(LIST_ORDERS_QUERY, {"first": first, "after": after, "query": query})
    connection = data["orders"]
    orders = [_parse_order(edge["node"]) for edge in connection["edges"]]
    has_next_page, end_cursor = parse_page_info(connection)
    return OrderPage(orders=orders, has_next_page=has_next_page, end_cursor=end_cursor)


def iter_all_orders(
    store: ShopifyStore, *, batch_size: int = 50, query: str | None = None
) -> Iterator[Order]:
    """Yield every order for a store (optionally filtered by `query`, same syntax as
    list_orders), fetching subsequent pages automatically."""
    return iter_pages(
        lambda after: list_orders(store, first=batch_size, after=after, query=query),
        lambda page: page.orders,
    )


def get_order(store: ShopifyStore, order_id: str) -> Order | None:
    """Fetch a single order by its GraphQL ID. Returns None if not found."""
    client = ShopifyGraphQLClient(store)
    data = client.execute(GET_ORDER_QUERY, {"id": order_id})
    node = data.get("order")
    if node is None:
        return None
    return _parse_order(node)


def update_order(store: ShopifyStore, *, order_id: str, **fields) -> Order:
    """Update order-level fields (e.g. tags, note, email).

    Fields are forwarded to Shopify's OrderInput — either Pythonic
    snake_case or Shopify's native camelCase both work.
    """
    client = ShopifyGraphQLClient(store)
    input_payload = camelize_keys({"id": order_id, **fields})
    data = client.execute(UPDATE_ORDER_MUTATION, {"input": input_payload})
    result = data["orderUpdate"]
    raise_for_user_errors(result["userErrors"])
    return _parse_order(result["order"])


def update_fulfillment_status(
    store: ShopifyStore,
    fulfillment_order_id: str,
    *,
    tracking_number: str | None = None,
    tracking_company: str | None = None,
    notify_customer: bool = True,
) -> Order:
    """Mark an order as fulfilled (optionally with tracking info).

    fulfillment_order_id is a Shopify FulfillmentOrder GraphQL ID, not an
    Order ID — that's how the Admin GraphQL API models fulfillment status
    changes. Returns the parent Order after fulfillment.
    """
    client = ShopifyGraphQLClient(store)
    fulfillment_input = {
        "lineItemsByFulfillmentOrder": [{"fulfillmentOrderId": fulfillment_order_id}],
        "notifyCustomer": notify_customer,
    }
    if tracking_number or tracking_company:
        fulfillment_input["trackingInfo"] = {
            "number": tracking_number,
            "company": tracking_company,
        }
    data = client.execute(FULFILL_ORDER_MUTATION, {"fulfillment": fulfillment_input})
    result = data["fulfillmentCreateV2"]
    raise_for_user_errors(result["userErrors"])
    return _parse_order(result["fulfillment"]["order"])
