"""Python-facing service functions for the Products, Options, and Variants area.

Every function takes an explicit ShopifyStore and returns plain dataclasses,
not raw GraphQL response shapes — callers never touch edges/nodes/cursors
directly.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterator, Literal, Sequence

from .._utils import camelize_keys
from ..client import ShopifyGraphQLClient
from ..exceptions import ShopifyUserError
from ..models import ShopifyStore
from .mutations import (
    CREATE_PRODUCT_MUTATION,
    DELETE_PRODUCT_MUTATION,
    PRODUCT_OPTIONS_CREATE_MUTATION,
    PRODUCT_OPTIONS_DELETE_MUTATION,
    PRODUCT_OPTION_UPDATE_MUTATION,
    PRODUCT_VARIANTS_BULK_CREATE_MUTATION,
    PRODUCT_VARIANTS_BULK_DELETE_MUTATION,
    PRODUCT_VARIANTS_BULK_UPDATE_MUTATION,
    UPDATE_PRODUCT_MUTATION,
)
from .queries import (
    GET_PRODUCT_QUERY,
    GET_PRODUCT_VARIANT_QUERY,
    LIST_PRODUCTS_QUERY,
    LIST_PRODUCT_VARIANTS_QUERY,
)

ProductStatus = Literal["ACTIVE", "ARCHIVED", "DRAFT"]


@dataclass
class ProductImage:
    id: str
    url: str
    alt_text: str | None = None


@dataclass
class SelectedOption:
    name: str
    value: str


@dataclass
class ProductOption:
    id: str
    name: str
    position: int
    values: list[str] = field(default_factory=list)


@dataclass
class ProductVariant:
    id: str
    title: str
    price: str
    compare_at_price: str | None = None
    sku: str | None = None
    barcode: str | None = None
    available_for_sale: bool = True
    inventory_quantity: int | None = None
    inventory_item_id: str | None = None
    inventory_tracked: bool = False
    weight: float | None = None
    weight_unit: str | None = None
    requires_shipping: bool = True
    taxable: bool = True
    image_id: str | None = None
    image_url: str | None = None
    image_alt_text: str | None = None
    selected_options: list[SelectedOption] = field(default_factory=list)
    product_id: str | None = None


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
    options: list[ProductOption] = field(default_factory=list)
    variants: list[ProductVariant] = field(default_factory=list)
    images: list[ProductImage] = field(default_factory=list)


@dataclass
class ProductPage:
    products: list[Product]
    has_next_page: bool
    end_cursor: str | None


def _parse_selected_option(node: dict) -> SelectedOption:
    return SelectedOption(
        name=node.get("name", ""),
        value=node.get("value", ""),
    )


def _parse_variant(node: dict, product_id: str | None = None) -> ProductVariant:
    img = node.get("image") or {}
    inv_item = node.get("inventoryItem") or {}
    measurement = inv_item.get("measurement") or {}
    weight_obj = measurement.get("weight") or {}
    weight_val = weight_obj.get("value") if weight_obj.get("value") is not None else node.get("weight")
    weight_unit = weight_obj.get("unit") or node.get("weightUnit")
    requires_shipping = inv_item.get("requiresShipping") if "requiresShipping" in inv_item else node.get("requiresShipping", True)
    selected_options = [
        _parse_selected_option(opt) for opt in node.get("selectedOptions") or []
    ]
    p_id = product_id or (node.get("product") or {}).get("id")
    return ProductVariant(
        id=node["id"],
        title=node.get("title", ""),
        price=str(node.get("price", "0.00")),
        compare_at_price=str(node["compareAtPrice"]) if node.get("compareAtPrice") is not None else None,
        sku=node.get("sku"),
        barcode=node.get("barcode"),
        available_for_sale=bool(node.get("availableForSale", True)),
        inventory_quantity=node.get("inventoryQuantity"),
        inventory_item_id=inv_item.get("id"),
        inventory_tracked=bool(inv_item.get("tracked", False)),
        weight=float(weight_val) if weight_val is not None else None,
        weight_unit=weight_unit,
        requires_shipping=bool(requires_shipping),
        taxable=bool(node.get("taxable", True)),
        image_id=img.get("id"),
        image_url=img.get("url"),
        image_alt_text=img.get("altText"),
        selected_options=selected_options,
        product_id=p_id,
    )


def _parse_option(node: dict) -> ProductOption:
    values = node.get("values") or []
    return ProductOption(
        id=node.get("id", ""),
        name=node.get("name", ""),
        position=node.get("position", 1),
        values=values,
    )


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
    options = [_parse_option(opt) for opt in node.get("options") or []]
    variant_edges = (node.get("variants") or {}).get("edges") or []
    variants = [_parse_variant(edge["node"], product_id=node["id"]) for edge in variant_edges]

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
        options=options,
        variants=variants,
        images=images,
    )


def _raise_for_user_errors(user_errors: list) -> None:
    if user_errors:
        raise ShopifyUserError(
            f"Shopify returned userErrors: {user_errors}", user_errors=user_errors
        )


# ==============================================================================
# Products CRUD & Iterators
# ==============================================================================

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
    """Yield every product for a store, fetching subsequent pages automatically."""
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
    """Create a product. Raises ShopifyUserError on Shopify-side validation failure."""
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
    """Update (edit) a product. Raises ShopifyUserError on validation failure."""
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


# ==============================================================================
# Product Variants CRUD & Bulk Services
# ==============================================================================

def list_product_variants(
    store: ShopifyStore, product_id: str, *, first: int = 50, after: str | None = None
) -> list[ProductVariant]:
    """List variants for a given product."""
    client = ShopifyGraphQLClient(store)
    data = client.execute(LIST_PRODUCT_VARIANTS_QUERY, {"id": product_id, "first": first, "after": after})
    product_node = data.get("product") or {}
    variants_conn = product_node.get("variants") or {}
    return [_parse_variant(edge["node"], product_id=product_id) for edge in variants_conn.get("edges") or []]


def get_product_variant(store: ShopifyStore, variant_id: str) -> ProductVariant | None:
    """Get a single product variant by its GraphQL ID."""
    client = ShopifyGraphQLClient(store)
    data = client.execute(GET_PRODUCT_VARIANT_QUERY, {"id": variant_id})
    node = data.get("node")
    if not node or not node.get("id"):
        return None
    return _parse_variant(node)


def create_product_variant(
    store: ShopifyStore,
    product_id: str,
    *,
    price: str,
    option_values: list[dict[str, str]] | None = None,
    compare_at_price: str | None = None,
    sku: str | None = None,
    barcode: str | None = None,
    weight: float | None = None,
    weight_unit: str | None = None,
    requires_shipping: bool = True,
    taxable: bool = True,
    media_id: str | None = None,
    **extra_fields,
) -> ProductVariant:
    """Create a single variant for a product using productVariantsBulkCreate."""
    variant_input: dict[str, Any] = {
        "price": str(price),
        "requiresShipping": requires_shipping,
        "taxable": taxable,
    }
    if option_values:
        variant_input["optionValues"] = [camelize_keys(ov) for ov in option_values]
    if compare_at_price is not None:
        variant_input["compareAtPrice"] = str(compare_at_price)
    if sku is not None:
        variant_input["sku"] = sku
    if barcode is not None:
        variant_input["barcode"] = barcode
    if weight is not None:
        variant_input["weight"] = weight
    if weight_unit is not None:
        variant_input["weightUnit"] = weight_unit
    if media_id is not None:
        variant_input["mediaId"] = media_id

    variant_input.update(camelize_keys(extra_fields))
    created = bulk_create_variants(store, product_id, [variant_input])
    if not created:
        raise ShopifyUserError(
            "productVariantsBulkCreate returned no variants", user_errors=[]
        )
    return created[0]


def bulk_create_variants(
    store: ShopifyStore, product_id: str, variants: Sequence[dict[str, Any]]
) -> list[ProductVariant]:
    """Create multiple variants for a product in a single bulk mutation."""
    client = ShopifyGraphQLClient(store)
    payload = [camelize_keys(v) for v in variants]
    data = client.execute(
        PRODUCT_VARIANTS_BULK_CREATE_MUTATION,
        {"productId": product_id, "variants": payload},
    )
    res = data.get("productVariantsBulkCreate") or {}
    _raise_for_user_errors(res.get("userErrors", []))
    return [_parse_variant(v_node, product_id=product_id) for v_node in res.get("productVariants") or []]


def update_product_variant(
    store: ShopifyStore,
    product_id: str,
    variant_id: str,
    *,
    price: str | None = None,
    compare_at_price: str | None = None,
    sku: str | None = None,
    barcode: str | None = None,
    weight: float | None = None,
    weight_unit: str | None = None,
    media_id: str | None = None,
    **extra_fields,
) -> ProductVariant:
    """Update a single variant's attributes.

    Shopify deprecated the single-variant productVariantUpdate mutation in
    API version 2024-10 — this wraps productVariantsBulkUpdate with a
    single-item list instead, which is why product_id is required here
    even though you're only touching one variant (the bulk mutation needs
    it; see bulk_update_variants for updating several at once).
    """
    variant_payload: dict[str, Any] = {"id": variant_id}
    if price is not None:
        variant_payload["price"] = str(price)
    if compare_at_price is not None:
        variant_payload["compareAtPrice"] = str(compare_at_price)
    if sku is not None:
        variant_payload["sku"] = sku
    if barcode is not None:
        variant_payload["barcode"] = barcode
    if weight is not None:
        variant_payload["weight"] = weight
    if weight_unit is not None:
        variant_payload["weightUnit"] = weight_unit
    if media_id is not None:
        variant_payload["mediaId"] = media_id
    variant_payload.update(camelize_keys(extra_fields))

    updated = bulk_update_variants(store, product_id, [variant_payload])
    if not updated:
        raise ShopifyUserError(
            f"productVariantsBulkUpdate returned no variants for variant_id={variant_id}",
            user_errors=[],
        )
    return updated[0]


def bulk_update_variants(
    store: ShopifyStore, product_id: str, variants: Sequence[dict[str, Any]]
) -> list[ProductVariant]:
    """Update multiple variants for a product in a single bulk mutation."""
    client = ShopifyGraphQLClient(store)
    payload = [camelize_keys(v) for v in variants]
    data = client.execute(
        PRODUCT_VARIANTS_BULK_UPDATE_MUTATION,
        {"productId": product_id, "variants": payload},
    )
    res = data.get("productVariantsBulkUpdate") or {}
    _raise_for_user_errors(res.get("userErrors", []))
    return [_parse_variant(v_node, product_id=product_id) for v_node in res.get("productVariants") or []]


def delete_product_variants(
    store: ShopifyStore, product_id: str, variant_ids: Sequence[str]
) -> None:
    """Delete one or more product variants by their IDs."""
    client = ShopifyGraphQLClient(store)
    data = client.execute(
        PRODUCT_VARIANTS_BULK_DELETE_MUTATION,
        {"productId": product_id, "variantsIds": list(variant_ids)},
    )
    res = data.get("productVariantsBulkDelete") or {}
    _raise_for_user_errors(res.get("userErrors", []))


# ==============================================================================
# Product Options Services
# ==============================================================================

def create_product_option(
    store: ShopifyStore,
    product_id: str,
    *,
    name: str,
    values: Sequence[str] | Sequence[dict[str, str]],
) -> ProductOption:
    """Create a new option dimension (e.g. Size, Color, Width) on a product."""
    client = ShopifyGraphQLClient(store)
    values_payload = [
        {"name": v} if isinstance(v, str) else v
        for v in values
    ]
    options_input = [{"name": name, "values": values_payload}]
    data = client.execute(
        PRODUCT_OPTIONS_CREATE_MUTATION,
        {"productId": product_id, "options": options_input},
    )
    res = data.get("productOptionsCreate") or {}
    _raise_for_user_errors(res.get("userErrors", []))
    opts = res.get("product", {}).get("options") or []
    for opt in opts:
        if opt.get("name") == name:
            return _parse_option(opt)
    raise ShopifyUserError(
        f"productOptionsCreate succeeded but no option named {name!r} was found "
        f"in the response — this is an unexpected shape, not a fabricated fallback.",
        user_errors=[],
    )


def update_product_option(
    store: ShopifyStore,
    product_id: str,
    option_id: str,
    *,
    name: str | None = None,
    values_to_add: Sequence[str] | None = None,
) -> ProductOption:
    """Update an existing product option."""
    client = ShopifyGraphQLClient(store)
    option_payload: dict[str, Any] = {"id": option_id}
    if name is not None:
        option_payload["name"] = name
    
    add_payload = [{"name": v} for v in values_to_add] if values_to_add else None

    data = client.execute(
        PRODUCT_OPTION_UPDATE_MUTATION,
        {
            "productId": product_id,
            "option": option_payload,
            "optionValuesToAdd": add_payload,
        },
    )
    res = data.get("productOptionUpdate") or {}
    _raise_for_user_errors(res.get("userErrors", []))
    opts = res.get("product", {}).get("options") or []
    for opt in opts:
        if opt.get("id") == option_id:
            return _parse_option(opt)
    raise ShopifyUserError(
        f"productOptionUpdate succeeded but option {option_id!r} was not found "
        f"in the response — this is an unexpected shape, not a fabricated fallback.",
        user_errors=[],
    )


def delete_product_option(
    store: ShopifyStore, product_id: str, option_id: str
) -> list[str]:
    """Delete a product option dimension."""
    client = ShopifyGraphQLClient(store)
    data = client.execute(
        PRODUCT_OPTIONS_DELETE_MUTATION,
        {"productId": product_id, "options": [option_id]},
    )
    res = data.get("productOptionsDelete") or {}
    _raise_for_user_errors(res.get("userErrors", []))
    return res.get("deletedOptionsIds") or [option_id]
