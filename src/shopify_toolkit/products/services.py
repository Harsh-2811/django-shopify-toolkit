"""Python-facing service functions for the Products area.

Every function takes an explicit ShopifyStore and returns plain dataclasses,
not raw GraphQL response shapes — callers never touch edges/nodes/cursors
directly.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterator, Literal

from .._utils import camelize_keys
from ..client import ShopifyGraphQLClient
from ..exceptions import ShopifyUserError
from ..models import ShopifyStore
from .mutations import CREATE_PRODUCT_MUTATION, DELETE_PRODUCT_MUTATION, UPDATE_PRODUCT_MUTATION
from .queries import GET_PRODUCT_QUERY, LIST_PRODUCTS_QUERY

# For IDE autocomplete on create_product/update_product's status= kwarg —
# Shopify's ProductStatus enum. Product.status itself stays a plain str
# (Shopify's own response), since it's read, not chosen by the caller.
ProductStatus = Literal["ACTIVE", "ARCHIVED", "DRAFT"]


@dataclass
class ProductImage:
    id: str
    url: str
    alt_text: str | None = None


@dataclass
class Product:
    id: str
    title: str
    handle: str
    description: str
    status: str
    vendor: str
    product_type: str
    tags: list[str]
    created_at: str
    updated_at: str
    images: list[ProductImage] = field(default_factory=list)


@dataclass
class ProductPage:
    products: list[Product]
    has_next_page: bool
    end_cursor: str | None


def _parse_product(node: dict) -> Product:
    image_edges = (node.get("images") or {}).get("edges") or []
    images = [
        ProductImage(
            id=edge["node"]["id"],
            url=edge["node"]["url"],
            alt_text=edge["node"].get("altText"),
        )
        for edge in image_edges
    ]
    return Product(
        id=node["id"],
        title=node["title"],
        handle=node["handle"],
        description=node.get("description", ""),
        status=node.get("status", ""),
        vendor=node.get("vendor", ""),
        product_type=node.get("productType", ""),
        tags=node.get("tags", []),
        created_at=node.get("createdAt", ""),
        updated_at=node.get("updatedAt", ""),
        images=images,
    )


def _raise_for_user_errors(user_errors: list) -> None:
    if user_errors:
        raise ShopifyUserError(
            f"Shopify returned userErrors: {user_errors}", user_errors=user_errors
        )


def list_products(store: ShopifyStore, *, first: int = 50, after: str | None = None) -> ProductPage:
    """List products for a store, paginated."""
    client = ShopifyGraphQLClient(store)
    data = client.execute(LIST_PRODUCTS_QUERY, {"first": first, "after": after})
    connection = data["products"]
    products = [_parse_product(edge["node"]) for edge in connection["edges"]]
    page_info = connection["pageInfo"]
    return ProductPage(
        products=products,
        has_next_page=page_info["hasNextPage"],
        end_cursor=page_info.get("endCursor"),
    )


def iter_all_products(store: ShopifyStore, *, batch_size: int = 50) -> Iterator[Product]:
    """Yield every product for a store, fetching subsequent pages automatically.

    for product in iter_all_products(store):
        ...
    """
    after = None
    while True:
        page = list_products(store, first=batch_size, after=after)
        yield from page.products
        if not page.has_next_page:
            return
        after = page.end_cursor


def get_product(store: ShopifyStore, product_id: str) -> Product | None:
    """Fetch a single product by its GraphQL ID. Returns None if not found."""
    client = ShopifyGraphQLClient(store)
    data = client.execute(GET_PRODUCT_QUERY, {"id": product_id})
    node = data.get("product")
    if node is None:
        return None
    return _parse_product(node)


def create_product(
    store: ShopifyStore, *, title: str, status: ProductStatus | None = None, **fields
) -> Product:
    """Create a product. Raises ShopifyUserError on Shopify-side validation failure.

    Extra fields are forwarded to Shopify's ProductInput — either
    Pythonic snake_case (product_type=...) or Shopify's native camelCase
    (productType=...) both work, snake_case is converted automatically.
    `status` is called out explicitly just for IDE autocomplete/validation;
    it works exactly the same as any other field passed through **fields.
    """
    if status is not None:
        fields["status"] = status
    client = ShopifyGraphQLClient(store)
    input_payload = camelize_keys({"title": title, **fields})
    data = client.execute(CREATE_PRODUCT_MUTATION, {"input": input_payload})
    result = data["productCreate"]
    _raise_for_user_errors(result["userErrors"])
    return _parse_product(result["product"])


def update_product(
    store: ShopifyStore, *, product_id: str, status: ProductStatus | None = None, **fields
) -> Product:
    """Update (edit) a product. Raises ShopifyUserError on validation failure.

    Extra fields are forwarded to Shopify's ProductInput — either
    Pythonic snake_case or Shopify's native camelCase both work.
    """
    if status is not None:
        fields["status"] = status
    client = ShopifyGraphQLClient(store)
    input_payload = camelize_keys({"id": product_id, **fields})
    data = client.execute(UPDATE_PRODUCT_MUTATION, {"input": input_payload})
    result = data["productUpdate"]
    _raise_for_user_errors(result["userErrors"])
    return _parse_product(result["product"])


def delete_product(store: ShopifyStore, product_id: str) -> str:
    """Delete a product. Returns the deleted product's GraphQL ID."""
    client = ShopifyGraphQLClient(store)
    data = client.execute(DELETE_PRODUCT_MUTATION, {"input": {"id": product_id}})
    result = data["productDelete"]
    _raise_for_user_errors(result["userErrors"])
    return result["deletedProductId"]
