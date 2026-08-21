import pytest
import responses
from django.db import connection
from rest_framework.test import APIRequestFactory

from shopify_toolkit.api.viewsets import ProductViewSet

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
def test_product_retrieve_view_unknown_store_raises_does_not_exist():
    view = ProductViewSet.as_view({"get": "retrieve"})

    unknown_pk = "ffffffffffffffffffffff99" if connection.vendor == "mongodb" else 999

    request = factory.get(f"/api/stores/{unknown_pk}/products/gid://shopify/Product/1/")

    from shopify_toolkit.models import ShopifyStore

    with pytest.raises(ShopifyStore.DoesNotExist):
        view(request, pk="gid://shopify/Product/1", store_pk=unknown_pk)
