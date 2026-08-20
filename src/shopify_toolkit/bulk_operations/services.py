"""Python-facing service functions for the Bulk Operations area.

For exporting/querying very large datasets (100k+ records) where paginated
GraphQL (list_products, list_orders, ...) would mean thousands of round
trips. Shopify runs the query asynchronously as a job and hands back a
JSONL file when it's done — this wraps that start/poll/download cycle.

Scope-locked per CLAUDE.md's amended scope table: only the generic bulk
*query* mechanism, not bulk mutations.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass

import requests

from ..client import ShopifyGraphQLClient
from ..conf import get_request_timeout
from ..exceptions import ShopifyToolkitError, ShopifyUserError
from ..models import ShopifyStore
from .mutations import RUN_BULK_QUERY_MUTATION
from .queries import CURRENT_BULK_OPERATION_QUERY

# Terminal states per Shopify's BulkOperationStatus enum — CREATED, RUNNING,
# and CANCELING are all still in progress.
_TERMINAL_STATUSES = frozenset({"COMPLETED", "FAILED", "CANCELED", "EXPIRED"})


@dataclass
class BulkOperation:
    id: str
    status: str
    error_code: str | None
    object_count: int
    file_size: int | None
    url: str | None
    partial_data_url: str | None


def _parse_bulk_operation(node: dict) -> BulkOperation:
    return BulkOperation(
        id=node["id"],
        status=node["status"],
        error_code=node.get("errorCode"),
        object_count=int(node.get("objectCount") or 0),
        file_size=int(node["fileSize"]) if node.get("fileSize") else None,
        url=node.get("url"),
        partial_data_url=node.get("partialDataUrl"),
    )


def run_bulk_query(store: ShopifyStore, query: str) -> BulkOperation:
    """Start a bulk query job.

    `query` is a raw GraphQL query string (Shopify's bulk API doesn't
    support $variables) — e.g. a query over all products with an
    unpaginated connection. Only one bulk operation can run per store at a
    time; Shopify rejects a second while one is already in progress.
    """
    client = ShopifyGraphQLClient(store)
    data = client.execute(RUN_BULK_QUERY_MUTATION, {"query": query})
    result = data["bulkOperationRunQuery"]
    if result["userErrors"]:
        raise ShopifyUserError(
            f"Shopify returned userErrors: {result['userErrors']}",
            user_errors=result["userErrors"],
        )
    return _parse_bulk_operation(result["bulkOperation"])


def get_current_bulk_operation(store: ShopifyStore) -> BulkOperation | None:
    """Get the most recent bulk operation for this store, or None if there
    has never been one."""
    client = ShopifyGraphQLClient(store)
    data = client.execute(CURRENT_BULK_OPERATION_QUERY)
    node = data.get("currentBulkOperation")
    if node is None:
        return None
    return _parse_bulk_operation(node)


def wait_for_bulk_operation(
    store: ShopifyStore, *, poll_interval: float = 2.0, timeout: float = 300.0
) -> BulkOperation:
    """Poll until the current bulk operation reaches a terminal state
    (COMPLETED/FAILED/CANCELED/EXPIRED), or raise ShopifyToolkitError after
    `timeout` seconds. Blocking — call from a background task/worker for
    anything that might take a while, not from a request/response cycle.
    """
    start = time.monotonic()
    while True:
        operation = get_current_bulk_operation(store)
        if operation is None:
            raise ShopifyToolkitError(
                f"No bulk operation found for store '{store.shop_domain}'."
            )
        if operation.status in _TERMINAL_STATUSES:
            return operation
        if time.monotonic() - start > timeout:
            raise ShopifyToolkitError(
                f"Bulk operation {operation.id} did not finish within "
                f"{timeout}s (status={operation.status})"
            )
        time.sleep(poll_interval)


def download_bulk_operation_result(operation: BulkOperation) -> list[dict]:
    """Download and parse a completed bulk operation's JSONL result file.

    Returns [] if there's no url (e.g. zero results, or the operation
    didn't complete successfully). The url is a temporary Shopify-hosted
    link that expires 7 days after completion — this is a plain HTTPS GET
    to that link, not a Shopify Admin GraphQL call.
    """
    if not operation.url:
        return []
    response = requests.get(operation.url, timeout=get_request_timeout())
    response.raise_for_status()
    return [json.loads(line) for line in response.text.splitlines() if line.strip()]
