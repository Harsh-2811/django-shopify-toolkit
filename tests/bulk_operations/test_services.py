import pytest
import responses

from shopify_toolkit.bulk_operations import services
from shopify_toolkit.exceptions import ShopifyGraphQLError, ShopifyToolkitError, ShopifyUserError

ENDPOINT = "https://test-store.myshopify.com/admin/api/2025-01/graphql.json"
OTHER_ENDPOINT = "https://other-store.myshopify.com/admin/api/2025-01/graphql.json"


def _bulk_op_node(**overrides):
    node = {
        "id": "gid://shopify/BulkOperation/1",
        "status": "CREATED",
        "errorCode": None,
        "createdAt": "2026-01-01T00:00:00Z",
        "completedAt": None,
        "objectCount": "0",
        "fileSize": None,
        "url": None,
        "partialDataUrl": None,
    }
    node.update(overrides)
    return node


@responses.activate
@pytest.mark.django_db
def test_run_bulk_query_success(shopify_store):
    responses.add(
        responses.POST,
        ENDPOINT,
        json={
            "data": {
                "bulkOperationRunQuery": {
                    "bulkOperation": _bulk_op_node(status="CREATED"),
                    "userErrors": [],
                }
            }
        },
        status=200,
    )
    op = services.run_bulk_query(shopify_store, "{ products { edges { node { id } } } }")

    assert op.status == "CREATED"
    assert op.id == "gid://shopify/BulkOperation/1"

    import json

    sent_body = json.loads(responses.calls[0].request.body)
    assert sent_body["variables"]["query"] == "{ products { edges { node { id } } } }"


@responses.activate
@pytest.mark.django_db
def test_run_bulk_query_user_error_raises(shopify_store):
    responses.add(
        responses.POST,
        ENDPOINT,
        json={
            "data": {
                "bulkOperationRunQuery": {
                    "bulkOperation": None,
                    "userErrors": [{"field": ["query"], "message": "invalid query"}],
                }
            }
        },
        status=200,
    )
    with pytest.raises(ShopifyUserError):
        services.run_bulk_query(shopify_store, "not a valid query")


@responses.activate
@pytest.mark.django_db
def test_get_current_bulk_operation_none(shopify_store):
    responses.add(
        responses.POST,
        ENDPOINT,
        json={"data": {"currentBulkOperation": None}},
        status=200,
    )
    assert services.get_current_bulk_operation(shopify_store) is None


@responses.activate
@pytest.mark.django_db
def test_get_current_bulk_operation_graphql_error_raises(shopify_store):
    responses.add(responses.POST, ENDPOINT, json={"errors": [{"message": "boom"}]}, status=200)
    with pytest.raises(ShopifyGraphQLError):
        services.get_current_bulk_operation(shopify_store)


@responses.activate
@pytest.mark.django_db
def test_wait_for_bulk_operation_polls_until_completed(shopify_store, monkeypatch):
    monkeypatch.setattr("shopify_toolkit.bulk_operations.services.time.sleep", lambda s: None)

    responses.add(
        responses.POST,
        ENDPOINT,
        json={"data": {"currentBulkOperation": _bulk_op_node(status="RUNNING")}},
        status=200,
    )
    responses.add(
        responses.POST,
        ENDPOINT,
        json={
            "data": {
                "currentBulkOperation": _bulk_op_node(
                    status="COMPLETED",
                    objectCount="42",
                    fileSize="1024",
                    url="https://cdn.shopify.com/bulk/result.jsonl",
                )
            }
        },
        status=200,
    )

    op = services.wait_for_bulk_operation(shopify_store, poll_interval=0)

    assert op.status == "COMPLETED"
    assert op.object_count == 42
    assert op.url == "https://cdn.shopify.com/bulk/result.jsonl"
    assert len(responses.calls) == 2


@responses.activate
@pytest.mark.django_db
def test_wait_for_bulk_operation_times_out(shopify_store, monkeypatch):
    monkeypatch.setattr("shopify_toolkit.bulk_operations.services.time.sleep", lambda s: None)
    responses.add(
        responses.POST,
        ENDPOINT,
        json={"data": {"currentBulkOperation": _bulk_op_node(status="RUNNING")}},
        status=200,
    )
    with pytest.raises(ShopifyToolkitError, match="did not finish"):
        services.wait_for_bulk_operation(shopify_store, poll_interval=0, timeout=-1)


@responses.activate
@pytest.mark.django_db
def test_wait_for_bulk_operation_none_raises(shopify_store):
    responses.add(
        responses.POST, ENDPOINT, json={"data": {"currentBulkOperation": None}}, status=200
    )
    with pytest.raises(ShopifyToolkitError, match="No bulk operation found"):
        services.wait_for_bulk_operation(shopify_store)


@responses.activate
def test_download_bulk_operation_result_parses_jsonl():
    operation = services.BulkOperation(
        id="gid://shopify/BulkOperation/1",
        status="COMPLETED",
        error_code=None,
        object_count=2,
        file_size=100,
        url="https://cdn.shopify.com/bulk/result.jsonl",
        partial_data_url=None,
    )
    responses.add(
        responses.GET,
        operation.url,
        body='{"id": "gid://shopify/Product/1"}\n{"id": "gid://shopify/Product/2"}\n',
        status=200,
    )

    rows = services.download_bulk_operation_result(operation)

    assert rows == [{"id": "gid://shopify/Product/1"}, {"id": "gid://shopify/Product/2"}]


def test_download_bulk_operation_result_no_url_returns_empty():
    operation = services.BulkOperation(
        id="x", status="COMPLETED", error_code=None, object_count=0,
        file_size=None, url=None, partial_data_url=None,
    )
    assert services.download_bulk_operation_result(operation) == []


@responses.activate
@pytest.mark.django_db
def test_store_isolation_run_bulk_query(shopify_store, other_shopify_store):
    responses.add(
        responses.POST,
        ENDPOINT,
        json={"data": {"bulkOperationRunQuery": {"bulkOperation": _bulk_op_node(), "userErrors": []}}},
        status=200,
    )
    responses.add(
        responses.POST,
        OTHER_ENDPOINT,
        json={"data": {"bulkOperationRunQuery": {"bulkOperation": _bulk_op_node(), "userErrors": []}}},
        status=200,
    )

    services.run_bulk_query(shopify_store, "{ shop { name } }")
    services.run_bulk_query(other_shopify_store, "{ shop { name } }")

    call_a, call_b = responses.calls[0], responses.calls[1]
    assert call_a.request.headers["X-Shopify-Access-Token"] == "shpat_test_token_1"
    assert call_b.request.headers["X-Shopify-Access-Token"] == "shpat_test_token_2"
