import json

import pytest
import responses

from shopify_toolkit.exceptions import ShopifyGraphQLError, ShopifyUserError
from shopify_toolkit.orders import services

ENDPOINT = "https://test-store.myshopify.com/admin/api/2025-01/graphql.json"
OTHER_ENDPOINT = "https://other-store.myshopify.com/admin/api/2025-01/graphql.json"

ORDER_ID = "gid://shopify/Order/1"


def _order_node(**overrides):
    node = {
        "id": ORDER_ID,
        "name": "#1001",
        "email": "buyer@example.com",
        "displayFinancialStatus": "PAID",
        "displayFulfillmentStatus": "UNFULFILLED",
        "totalPriceSet": {"shopMoney": {"amount": "42.00", "currencyCode": "USD"}},
        "createdAt": "2026-01-01T00:00:00Z",
        "updatedAt": "2026-01-01T00:00:00Z",
    }
    node.update(overrides)
    return node


@responses.activate
@pytest.mark.django_db
def test_list_orders_success(shopify_store):
    responses.add(
        responses.POST,
        ENDPOINT,
        json={
            "data": {
                "orders": {
                    "edges": [{"cursor": "c1", "node": _order_node()}],
                    "pageInfo": {"hasNextPage": False, "endCursor": "c1"},
                }
            }
        },
        status=200,
    )
    page = services.list_orders(shopify_store)
    assert len(page.orders) == 1
    assert page.orders[0].name == "#1001"
    assert page.orders[0].total_price == "42.00"


@responses.activate
@pytest.mark.django_db
def test_list_orders_graphql_error_raises(shopify_store):
    responses.add(responses.POST, ENDPOINT, json={"errors": [{"message": "boom"}]}, status=200)
    with pytest.raises(ShopifyGraphQLError):
        services.list_orders(shopify_store)


@responses.activate
@pytest.mark.django_db
def test_get_order_success(shopify_store):
    responses.add(responses.POST, ENDPOINT, json={"data": {"order": _order_node()}}, status=200)
    order = services.get_order(shopify_store, ORDER_ID)
    assert order.id == ORDER_ID
    assert order.financial_status == "PAID"


@responses.activate
@pytest.mark.django_db
def test_get_order_not_found_returns_none(shopify_store):
    responses.add(responses.POST, ENDPOINT, json={"data": {"order": None}}, status=200)
    assert services.get_order(shopify_store, "gid://shopify/Order/999") is None


@responses.activate
@pytest.mark.django_db
def test_update_order_success(shopify_store):
    responses.add(
        responses.POST,
        ENDPOINT,
        json={"data": {"orderUpdate": {"order": _order_node(email="new@example.com"), "userErrors": []}}},
        status=200,
    )
    order = services.update_order(shopify_store, order_id=ORDER_ID, email="new@example.com")
    assert order.email == "new@example.com"


@responses.activate
@pytest.mark.django_db
def test_update_order_accepts_snake_case_kwargs(shopify_store):
    responses.add(
        responses.POST,
        ENDPOINT,
        json={"data": {"orderUpdate": {"order": _order_node(), "userErrors": []}}},
        status=200,
    )
    services.update_order(shopify_store, order_id=ORDER_ID, po_number="PO-123")

    import json

    sent_body = json.loads(responses.calls[0].request.body)
    assert sent_body["variables"]["input"] == {"id": ORDER_ID, "poNumber": "PO-123"}


@responses.activate
@pytest.mark.django_db
def test_update_order_user_error_raises(shopify_store):
    responses.add(
        responses.POST,
        ENDPOINT,
        json={
            "data": {
                "orderUpdate": {
                    "order": None,
                    "userErrors": [{"field": ["email"], "message": "is invalid"}],
                }
            }
        },
        status=200,
    )
    with pytest.raises(ShopifyUserError):
        services.update_order(shopify_store, order_id=ORDER_ID, email="not-an-email")


@responses.activate
@pytest.mark.django_db
def test_update_fulfillment_status_success(shopify_store):
    responses.add(
        responses.POST,
        ENDPOINT,
        json={
            "data": {
                "fulfillmentCreateV2": {
                    "fulfillment": {
                        "id": "gid://shopify/Fulfillment/1",
                        "status": "SUCCESS",
                        "order": _order_node(displayFulfillmentStatus="FULFILLED"),
                    },
                    "userErrors": [],
                }
            }
        },
        status=200,
    )
    order = services.update_fulfillment_status(
        shopify_store, "gid://shopify/FulfillmentOrder/1", tracking_number="1Z999"
    )
    assert order.fulfillment_status == "FULFILLED"


@responses.activate
@pytest.mark.django_db
def test_update_fulfillment_status_user_error_raises(shopify_store):
    responses.add(
        responses.POST,
        ENDPOINT,
        json={
            "data": {
                "fulfillmentCreateV2": {
                    "fulfillment": None,
                    "userErrors": [{"field": None, "message": "already fulfilled"}],
                }
            }
        },
        status=200,
    )
    with pytest.raises(ShopifyUserError):
        services.update_fulfillment_status(shopify_store, "gid://shopify/FulfillmentOrder/1")


@responses.activate
@pytest.mark.django_db
def test_store_isolation_list_orders(shopify_store, other_shopify_store):
    empty_page = {"data": {"orders": {"edges": [], "pageInfo": {"hasNextPage": False, "endCursor": None}}}}
    responses.add(responses.POST, ENDPOINT, json=empty_page, status=200)
    responses.add(responses.POST, OTHER_ENDPOINT, json=empty_page, status=200)

    services.list_orders(shopify_store)
    services.list_orders(other_shopify_store)

    call_a, call_b = responses.calls[0], responses.calls[1]
    assert call_a.request.headers["X-Shopify-Access-Token"] == "shpat_test_token_1"
    assert call_b.request.headers["X-Shopify-Access-Token"] == "shpat_test_token_2"


@responses.activate
@pytest.mark.django_db
def test_iter_all_orders_fetches_every_page(shopify_store):
    responses.add(
        responses.POST,
        ENDPOINT,
        json={
            "data": {
                "orders": {
                    "edges": [{"cursor": "c1", "node": _order_node(id="gid://shopify/Order/1")}],
                    "pageInfo": {"hasNextPage": True, "endCursor": "c1"},
                }
            }
        },
        status=200,
    )
    responses.add(
        responses.POST,
        ENDPOINT,
        json={
            "data": {
                "orders": {
                    "edges": [{"cursor": "c2", "node": _order_node(id="gid://shopify/Order/2")}],
                    "pageInfo": {"hasNextPage": False, "endCursor": "c2"},
                }
            }
        },
        status=200,
    )

    ids = [o.id for o in services.iter_all_orders(shopify_store, batch_size=1)]

    assert ids == ["gid://shopify/Order/1", "gid://shopify/Order/2"]
    assert len(responses.calls) == 2


@responses.activate
@pytest.mark.django_db
def test_list_orders_passes_search_query_variable(shopify_store):
    responses.add(
        responses.POST,
        ENDPOINT,
        json={
            "data": {
                "orders": {
                    "edges": [{"cursor": "c1", "node": _order_node()}],
                    "pageInfo": {"hasNextPage": False, "endCursor": "c1"},
                }
            }
        },
        status=200,
    )

    services.list_orders(shopify_store, query="financial_status:paid")

    body = json.loads(responses.calls[0].request.body)
    assert body["variables"]["query"] == "financial_status:paid"
    assert "query: $query" in body["query"]



@responses.activate
@pytest.mark.django_db
def test_iter_all_orders_forwards_query_to_every_page(shopify_store):
    def page(node_id, *, has_next_page, end_cursor):
        return {
            "data": {
                "orders": {
                    "edges": [{"cursor": node_id, "node": _order_node(id=node_id)}],
                    "pageInfo": {"hasNextPage": has_next_page, "endCursor": end_cursor},
                }
            }
        }

    responses.add(responses.POST, ENDPOINT, json=page("gid://shopify/Order/1", has_next_page=True, end_cursor="c1"), status=200)
    responses.add(responses.POST, ENDPOINT, json=page("gid://shopify/Order/2", has_next_page=False, end_cursor=None), status=200)

    ids = [item.id for item in services.iter_all_orders(shopify_store, query="tag:sale")]

    assert ids == ["gid://shopify/Order/1", "gid://shopify/Order/2"]
    variables = [json.loads(call.request.body)["variables"] for call in responses.calls]
    assert [v["query"] for v in variables] == ["tag:sale", "tag:sale"]
    assert [v["after"] for v in variables] == [None, "c1"]
