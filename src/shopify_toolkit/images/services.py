"""Python-facing service functions for the Product Images area.

Built on Shopify's Media API — see queries.py's docstring for why, and
mutations.py for the exact mutations used.
"""
from __future__ import annotations

from dataclasses import dataclass

from ..client import ShopifyGraphQLClient
from ..exceptions import ShopifyUserError
from ..models import ShopifyStore
from .mutations import (
    ADD_PRODUCT_IMAGE_MUTATION,
    REMOVE_PRODUCT_IMAGE_MUTATION,
    REORDER_PRODUCT_IMAGES_MUTATION,
)
from .queries import LIST_PRODUCT_IMAGES_QUERY


@dataclass
class ProductImage:
    id: str
    # Shopify processes uploaded media asynchronously — url can briefly be
    # None right after add_product_image() returns, until Shopify finishes
    # processing it (status becomes READY). It's always set for images
    # that have existed for more than a few seconds.
    url: str | None
    alt_text: str | None = None


def _parse_image(node: dict) -> ProductImage:
    image = node.get("image") or {}
    return ProductImage(id=node["id"], url=image.get("url"), alt_text=node.get("alt"))


def _raise_for_media_user_errors(media_user_errors: list) -> None:
    if media_user_errors:
        raise ShopifyUserError(
            f"Shopify returned mediaUserErrors: {media_user_errors}",
            user_errors=media_user_errors,
        )


def list_product_images(store: ShopifyStore, product_id: str, *, first: int = 50) -> list[ProductImage]:
    """List image-type media attached to a product (videos/3D models excluded)."""
    client = ShopifyGraphQLClient(store)
    data = client.execute(LIST_PRODUCT_IMAGES_QUERY, {"id": product_id, "first": first})
    edges = ((data.get("product") or {}).get("media") or {}).get("edges", [])
    # Non-image media nodes don't match the `... on MediaImage` fragment, so
    # they simply have no "image" key in the response — filter those out.
    return [_parse_image(edge["node"]) for edge in edges if "image" in edge["node"]]


def add_product_image(
    store: ShopifyStore, product_id: str, *, src: str, alt_text: str | None = None
) -> ProductImage:
    """Add an image to a product from a source URL."""
    client = ShopifyGraphQLClient(store)
    media_input = {"originalSource": src, "mediaContentType": "IMAGE"}
    if alt_text is not None:
        media_input["alt"] = alt_text
    data = client.execute(
        ADD_PRODUCT_IMAGE_MUTATION, {"productId": product_id, "media": [media_input]}
    )
    result = data["productCreateMedia"]
    _raise_for_media_user_errors(result["mediaUserErrors"])
    media_list = result["media"]
    if not media_list:
        raise ShopifyUserError("productCreateMedia returned no media", user_errors=[])
    return _parse_image(media_list[0])


def remove_product_image(store: ShopifyStore, product_id: str, image_id: str) -> str:
    """Remove an image from a product. Returns the deleted image's GraphQL ID."""
    client = ShopifyGraphQLClient(store)
    data = client.execute(
        REMOVE_PRODUCT_IMAGE_MUTATION, {"productId": product_id, "mediaIds": [image_id]}
    )
    result = data["productDeleteMedia"]
    _raise_for_media_user_errors(result["mediaUserErrors"])
    deleted = result["deletedMediaIds"]
    return deleted[0] if deleted else image_id


def reorder_product_images(store: ShopifyStore, product_id: str, image_ids_in_order: list[str]) -> None:
    """Reorder a product's images to match image_ids_in_order (first to last).

    This is asynchronous on Shopify's side (a Job is queued) — this
    function doesn't wait for it to finish.
    """
    client = ShopifyGraphQLClient(store)
    moves = [
        {"id": image_id, "newPosition": str(position)}
        for position, image_id in enumerate(image_ids_in_order)
    ]
    data = client.execute(
        REORDER_PRODUCT_IMAGES_MUTATION, {"productId": product_id, "moves": moves}
    )
    result = data["productReorderMedia"]
    _raise_for_media_user_errors(result["mediaUserErrors"])
