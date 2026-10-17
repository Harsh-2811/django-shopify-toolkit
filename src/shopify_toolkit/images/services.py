"""Python-facing service functions for the Product Images area.

Built on Shopify's Media API — see queries.py's docstring for why, and
mutations.py for the exact mutations used.
"""
from __future__ import annotations

import mimetypes
import os
from dataclasses import dataclass
from typing import BinaryIO

import requests

from .._utils import raise_for_user_errors
from ..client import ShopifyGraphQLClient
from ..conf import get_request_timeout
from ..exceptions import ShopifyUserError
from ..models import ShopifyStore
from .mutations import (
    ADD_PRODUCT_IMAGE_MUTATION,
    REMOVE_PRODUCT_IMAGE_MUTATION,
    REORDER_PRODUCT_IMAGES_MUTATION,
    STAGED_UPLOADS_CREATE_MUTATION,
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
    raise_for_user_errors(result["mediaUserErrors"], kind="mediaUserErrors")
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
    raise_for_user_errors(result["mediaUserErrors"], kind="mediaUserErrors")
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
    raise_for_user_errors(result["mediaUserErrors"], kind="mediaUserErrors")


def upload_product_image_file(
    store: ShopifyStore,
    product_id: str,
    file_source: str | BinaryIO,
    *,
    filename: str | None = None,
    alt_text: str | None = None,
    content_type: str | None = None,
) -> ProductImage:
    """Upload a local binary image file directly to Shopify (no public URL
    needed) using the Staged Uploads API, then attach it to a product.

    Supports a file path (str), a Django UploadedFile, or any other
    file-like object (e.g. io.BytesIO).
    """
    client = ShopifyGraphQLClient(store)

    if isinstance(file_source, str):
        if not os.path.exists(file_source):
            raise FileNotFoundError(f"Image file not found: {file_source}")
        fname = filename or os.path.basename(file_source)
        file_size = os.path.getsize(file_source)
        mime = content_type or mimetypes.guess_type(fname)[0] or "application/octet-stream"
        with open(file_source, "rb") as f:
            file_bytes = f.read()
    else:
        fname = filename or getattr(file_source, "name", "image.jpg")
        file_bytes = file_source.read()
        file_size = len(file_bytes)
        mime = (
            content_type
            or getattr(file_source, "content_type", None)
            or mimetypes.guess_type(fname)[0]
            or "application/octet-stream"
        )

    # 1. Request a staged upload target from Shopify.
    # resource="IMAGE", not "PRODUCT_IMAGE" — the latter is a deprecated
    # value tied to the classic ProductImage API this module already moved
    # away from (see queries.py's docstring). "IMAGE" is the current value
    # for anything you'll attach via productCreateMedia — verified against
    # shopify.dev's StagedUploadTargetGenerateUploadResource enum reference.
    staged_input = {
        "resource": "IMAGE",
        "filename": fname,
        "mimeType": mime,
        "fileSize": str(file_size),
        "httpMethod": "POST",
    }
    data = client.execute(STAGED_UPLOADS_CREATE_MUTATION, {"input": [staged_input]})
    target_data = data.get("stagedUploadsCreate") or {}
    raise_for_user_errors(target_data.get("userErrors", []))

    targets = target_data.get("stagedTargets") or []
    if not targets:
        raise ShopifyUserError("stagedUploadsCreate returned no stagedTargets", user_errors=[])

    target = targets[0]
    upload_url = target["url"]
    resource_url = target["resourceUrl"]
    params = target.get("parameters", [])

    # 2. POST the raw bytes directly to Shopify's temporary storage target
    # (Google Cloud Storage) — not a Shopify Admin API call, so it doesn't
    # go through ShopifyGraphQLClient.
    form_data = {p["name"]: p["value"] for p in params}
    files = {"file": (fname, file_bytes, mime)}
    response = requests.post(upload_url, data=form_data, files=files, timeout=get_request_timeout())
    response.raise_for_status()

    # 3. Attach the uploaded file to the product via the same Media API
    # path as add_product_image().
    return add_product_image(store, product_id, src=resource_url, alt_text=alt_text)

