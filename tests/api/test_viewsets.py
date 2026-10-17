import json

import pytest
import responses
from django.db import connection
from rest_framework.test import APIRequestFactory

from shopify_toolkit.api.viewsets import CustomerViewSet, OrderViewSet, ProductViewSet

ENDPOINT = "https://test-store.myshopify.com/admin/api/2025-01/graphql.json"

factory = APIRequestFactory()


def _product_node(**overrides):
    node = {
        "id": "gid://shopify/Product/1",
        "title": "Test Product",
        "handle": "test-product",
        "description": "",
        "status": "ACTIVE",
        "vendor": "Acme",
        "productType": "Widget",
        "tags": [],
        "createdAt": "2026-01-01T00:00:00Z",
        "updatedAt": "2026-01-01T00:00:00Z",
        "images": {"edges": []},
    }
    node.update(overrides)
    return node


@responses.activate
@pytest.mark.django_db
def test_product_list_view_returns_serialized_products(shopify_store):
    responses.add(
        responses.POST,
        ENDPOINT,
        json={
            "data": {
                "products": {
                    "edges": [{"cursor": "c1", "node": _product_node()}],
                    "pageInfo": {"hasNextPage": False, "endCursor": "c1"},
                }
            }
        },
        status=200,
    )
    view = ProductViewSet.as_view({"get": "list"})
    request = factory.get("/api/stores/1/products/")

    response = view(request, store_pk=shopify_store.pk)

    assert response.status_code == 200
    assert response.data["results"][0]["title"] == "Test Product"


@pytest.mark.django_db
def test_product_create_view_validates_input(shopify_store):
    view = ProductViewSet.as_view({"post": "create"})
    request = factory.post("/api/stores/1/products/", {}, format="json")

    response = view(request, store_pk=shopify_store.pk)

    assert response.status_code == 400
    assert "title" in response.data


@pytest.mark.django_db
def test_product_retrieve_view_unknown_store_returns_404():
    view = ProductViewSet.as_view({"get": "retrieve"})

    unknown_pk = "ffffffffffffffffffffff99" if connection.vendor == "mongodb" else 999

    request = factory.get(f"/api/stores/{unknown_pk}/products/gid://shopify/Product/1/")

    response = view(request, pk="gid://shopify/Product/1", store_pk=unknown_pk)

    assert response.status_code == 404


@pytest.mark.django_db
def test_inactive_store_returns_404(shopify_store):
    shopify_store.is_active = False
    shopify_store.save(update_fields=["is_active"])
    view = CustomerViewSet.as_view({"get": "list"})

    response = view(factory.get("/api/stores/1/customers/"), store_pk=shopify_store.pk)

    assert response.status_code == 404


@responses.activate
@pytest.mark.django_db
def test_list_view_forwards_query_param(shopify_store):
    responses.add(
        responses.POST,
        ENDPOINT,
        json={
            "data": {
                "customers": {
                    "edges": [],
                    "pageInfo": {"hasNextPage": False, "endCursor": None},
                }
            }
        },
        status=200,
    )
    view = CustomerViewSet.as_view({"get": "list"})
    request = factory.get("/api/stores/1/customers/", {"query": "tag:vip"})

    response = view(request, store_pk=shopify_store.pk)

    assert response.status_code == 200
    assert json.loads(responses.calls[0].request.body)["variables"]["query"] == "tag:vip"


@responses.activate
@pytest.mark.django_db
def test_list_view_empty_query_param_means_no_filter(shopify_store):
    responses.add(
        responses.POST,
        ENDPOINT,
        json={"data": {"orders": {"edges": [], "pageInfo": {"hasNextPage": False, "endCursor": None}}}},
        status=200,
    )
    view = OrderViewSet.as_view({"get": "list"})
    request = factory.get("/api/stores/1/orders/", {"query": ""})

    view(request, store_pk=shopify_store.pk)

    assert json.loads(responses.calls[0].request.body)["variables"]["query"] is None


@responses.activate
@pytest.mark.django_db
def test_customer_destroy_view_returns_204(shopify_store):
    customer_id = "gid://shopify/Customer/1"
    responses.add(
        responses.POST,
        ENDPOINT,
        json={"data": {"customerDelete": {"deletedCustomerId": customer_id, "userErrors": []}}},
        status=200,
    )
    view = CustomerViewSet.as_view({"delete": "destroy"})
    request = factory.delete(f"/api/stores/1/customers/{customer_id}/")

    response = view(request, pk=customer_id, store_pk=shopify_store.pk)

    assert response.status_code == 204
    assert json.loads(responses.calls[0].request.body)["variables"] == {"input": {"id": customer_id}}



@pytest.mark.django_db
@pytest.mark.parametrize("first", ["abc", "0", "-5", "251", "1.5"])
def test_list_view_rejects_invalid_first_with_400(shopify_store, first):
    view = ProductViewSet.as_view({"get": "list"})

    response = view(factory.get("/api/stores/1/products/", {"first": first}), store_pk=shopify_store.pk)

    assert response.status_code == 400
    assert "first" in response.data


@responses.activate
@pytest.mark.django_db
def test_list_view_accepts_max_page_size(shopify_store):
    responses.add(
        responses.POST,
        ENDPOINT,
        json={"data": {"products": {"edges": [], "pageInfo": {"hasNextPage": False, "endCursor": None}}}},
        status=200,
    )
    view = ProductViewSet.as_view({"get": "list"})

    response = view(factory.get("/api/stores/1/products/", {"first": "250"}), store_pk=shopify_store.pk)

    assert response.status_code == 200
    assert json.loads(responses.calls[0].request.body)["variables"]["first"] == 250


@responses.activate
@pytest.mark.django_db
def test_shopify_user_error_returns_400_with_user_errors(shopify_store):
    user_errors = [{"field": ["id"], "message": "Customer can't be deleted because they have orders"}]
    responses.add(
        responses.POST,
        ENDPOINT,
        json={"data": {"customerDelete": {"deletedCustomerId": None, "userErrors": user_errors}}},
        status=200,
    )
    view = CustomerViewSet.as_view({"delete": "destroy"})
    customer_id = "gid://shopify/Customer/1"

    response = view(factory.delete(f"/api/stores/1/customers/{customer_id}/"), pk=customer_id, store_pk=shopify_store.pk)

    assert response.status_code == 400
    assert response.data["user_errors"] == user_errors


@responses.activate
@pytest.mark.django_db
def test_graphql_error_is_not_turned_into_400(shopify_store):
    """Only ShopifyUserError (bad input) maps to 400 — a GraphQL/server error must still propagate."""
    from shopify_toolkit.exceptions import ShopifyGraphQLError

    responses.add(responses.POST, ENDPOINT, json={"errors": [{"message": "boom"}]}, status=200)
    view = CustomerViewSet.as_view({"get": "list"})

    with pytest.raises(ShopifyGraphQLError):
        view(factory.get("/api/stores/1/customers/"), store_pk=shopify_store.pk)
