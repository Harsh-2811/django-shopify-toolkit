"""Python-facing service functions for the Customers area."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator

from .._utils import camelize_keys, iter_pages, parse_page_info, raise_for_user_errors
from ..client import ShopifyGraphQLClient
from ..models import ShopifyStore
from .queries import (
    CREATE_CUSTOMER_MUTATION,
    DELETE_CUSTOMER_MUTATION,
    GET_CUSTOMER_QUERY,
    LIST_CUSTOMERS_QUERY,
    UPDATE_CUSTOMER_MUTATION,
)


@dataclass
class Customer:
    id: str
    first_name: str | None
    last_name: str | None
    email: str | None
    phone: str | None
    tags: list[str]
    created_at: str
    updated_at: str


@dataclass
class CustomerPage:
    customers: list[Customer]
    has_next_page: bool
    end_cursor: str | None


def _parse_customer(node: dict) -> Customer:
    return Customer(
        id=node["id"],
        first_name=node.get("firstName"),
        last_name=node.get("lastName"),
        email=node.get("email"),
        phone=node.get("phone"),
        tags=node.get("tags", []),
        created_at=node.get("createdAt", ""),
        updated_at=node.get("updatedAt", ""),
    )


def list_customers(
    store: ShopifyStore,
    *,
    first: int = 50,
    after: str | None = None,
    query: str | None = None,
) -> CustomerPage:
    """List customers for a store, paginated.

    `query` is passed through as Shopify's search syntax, e.g.
    "email:ada@example.com" or "tag:vip".
    See https://shopify.dev/docs/api/usage/search-syntax.
    Omitted (None) means no filtering.
    """
    client = ShopifyGraphQLClient(store)
    data = client.execute(LIST_CUSTOMERS_QUERY, {"first": first, "after": after, "query": query})
    connection = data["customers"]
    customers = [_parse_customer(edge["node"]) for edge in connection["edges"]]
    has_next_page, end_cursor = parse_page_info(connection)
    return CustomerPage(customers=customers, has_next_page=has_next_page, end_cursor=end_cursor)


def iter_all_customers(
    store: ShopifyStore, *, batch_size: int = 50, query: str | None = None
) -> Iterator[Customer]:
    """Yield every customer for a store (optionally filtered by `query`, same syntax as
    list_customers), fetching subsequent pages automatically."""
    return iter_pages(
        lambda after: list_customers(store, first=batch_size, after=after, query=query),
        lambda page: page.customers,
    )


def get_customer(store: ShopifyStore, customer_id: str) -> Customer | None:
    """Fetch a single customer by its GraphQL ID. Returns None if not found."""
    client = ShopifyGraphQLClient(store)
    data = client.execute(GET_CUSTOMER_QUERY, {"id": customer_id})
    node = data.get("customer")
    if node is None:
        return None
    return _parse_customer(node)


def create_customer(store: ShopifyStore, **fields) -> Customer:
    """Create a customer. Raises ShopifyUserError on validation failure.

    Fields are forwarded to Shopify's CustomerInput — either Pythonic
    snake_case (first_name=...) or Shopify's native camelCase
    (firstName=...) both work, snake_case is converted automatically.
    """
    client = ShopifyGraphQLClient(store)
    input_payload = camelize_keys(fields)
    data = client.execute(CREATE_CUSTOMER_MUTATION, {"input": input_payload})
    result = data["customerCreate"]
    raise_for_user_errors(result["userErrors"])
    return _parse_customer(result["customer"])


def update_customer(store: ShopifyStore, *, customer_id: str, **fields) -> Customer:
    """Update a customer. Raises ShopifyUserError on validation failure.

    Fields are forwarded to Shopify's CustomerInput — either Pythonic
    snake_case or Shopify's native camelCase both work.
    """
    client = ShopifyGraphQLClient(store)
    input_payload = camelize_keys({"id": customer_id, **fields})
    data = client.execute(UPDATE_CUSTOMER_MUTATION, {"input": input_payload})
    result = data["customerUpdate"]
    raise_for_user_errors(result["userErrors"])
    return _parse_customer(result["customer"])


def delete_customer(store: ShopifyStore, customer_id: str) -> str:
    """Delete a customer. Returns the deleted customer's GraphQL ID.

    Shopify refuses to delete a customer who has placed orders — that surfaces as
    ShopifyUserError, not a silent no-op.
    """
    client = ShopifyGraphQLClient(store)
    data = client.execute(DELETE_CUSTOMER_MUTATION, {"input": {"id": customer_id}})
    result = data["customerDelete"]
    raise_for_user_errors(result["userErrors"])
    return result["deletedCustomerId"]
