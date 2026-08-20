import pytest
import responses

from shopify_toolkit.exceptions import ShopifyGraphQLError, ShopifyUserError
from shopify_toolkit.products import services

ENDPOINT = "https://test-store.myshopify.com/admin/api/2025-01/graphql.json"
OTHER_ENDPOINT = "https://other-store.myshopify.com/admin/api/2025-01/graphql.json"


def _product_node(**overrides):
    node = {
        "id": "gid://shopify/Product/1",
        "title": "Test Product",
        "handle": "test-product",
        "description": "A product",
        "status": "ACTIVE",
        "vendor": "Acme",
        "productType": "Widget",
        "tags": ["a", "b"],
        "createdAt": "2026-01-01T00:00:00Z",
        "updatedAt": "2026-01-01T00:00:00Z",
        "images": {"edges": []},
    }
    node.update(overrides)
    return node


@responses.activate
@pytest.mark.django_db
def test_list_products_success(shopify_store):
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
    page = services.list_products(shopify_store, first=10)
    assert len(page.products) == 1
    assert page.products[0].title == "Test Product"
    assert page.has_next_page is False


@responses.activate
@pytest.mark.django_db
def test_list_products_graphql_error_raises(shopify_store):
    responses.add(
        responses.POST,
        ENDPOINT,
        json={"errors": [{"message": "Something broke"}]},
        status=200,
    )
    with pytest.raises(ShopifyGraphQLError):
        services.list_products(shopify_store)


@responses.activate
@pytest.mark.django_db
def test_get_product_success(shopify_store):
    responses.add(
        responses.POST,
        ENDPOINT,
        json={"data": {"product": _product_node(title="Fetched")}},
        status=200,
    )
    product = services.get_product(shopify_store, "gid://shopify/Product/1")
    assert product.title == "Fetched"


@responses.activate
@pytest.mark.django_db
def test_get_product_not_found_returns_none(shopify_store):
    responses.add(responses.POST, ENDPOINT, json={"data": {"product": None}}, status=200)
    assert services.get_product(shopify_store, "gid://shopify/Product/999") is None


@responses.activate
@pytest.mark.django_db
def test_create_product_success(shopify_store):
    responses.add(
        responses.POST,
        ENDPOINT,
        json={
            "data": {
                "productCreate": {
                    "product": _product_node(title="New Product"),
                    "userErrors": [],
                }
            }
        },
        status=200,
    )
    product = services.create_product(shopify_store, title="New Product")
    assert product.title == "New Product"


@responses.activate
@pytest.mark.django_db
def test_create_product_accepts_snake_case_kwargs(shopify_store):
    responses.add(
        responses.POST,
        ENDPOINT,
        json={"data": {"productCreate": {"product": _product_node(), "userErrors": []}}},
        status=200,
    )
    services.create_product(shopify_store, title="New Product", product_type="Mug")

    import json

    sent_body = json.loads(responses.calls[0].request.body)
    assert sent_body["variables"]["input"] == {"title": "New Product", "productType": "Mug"}


@responses.activate
@pytest.mark.django_db
def test_create_product_user_error_raises(shopify_store):
    responses.add(
        responses.POST,
        ENDPOINT,
        json={
            "data": {
                "productCreate": {
                    "product": None,
                    "userErrors": [{"field": ["title"], "message": "can't be blank"}],
                }
            }
        },
        status=200,
    )
    with pytest.raises(ShopifyUserError):
        services.create_product(shopify_store, title="")


@responses.activate
@pytest.mark.django_db
def test_update_product_success(shopify_store):
    responses.add(
        responses.POST,
        ENDPOINT,
        json={
            "data": {
                "productUpdate": {
                    "product": _product_node(title="Updated"),
                    "userErrors": [],
                }
            }
        },
        status=200,
    )
    product = services.update_product(
        shopify_store, product_id="gid://shopify/Product/1", title="Updated"
    )
    assert product.title == "Updated"


@responses.activate
@pytest.mark.django_db
def test_delete_product_success(shopify_store):
    responses.add(
        responses.POST,
        ENDPOINT,
        json={
            "data": {
                "productDelete": {
                    "deletedProductId": "gid://shopify/Product/1",
                    "userErrors": [],
                }
            }
        },
        status=200,
    )
    deleted_id = services.delete_product(shopify_store, "gid://shopify/Product/1")
    assert deleted_id == "gid://shopify/Product/1"


@responses.activate
@pytest.mark.django_db
def test_store_isolation_list_products(shopify_store, other_shopify_store):
    responses.add(
        responses.POST,
        ENDPOINT,
        json={"data": {"products": {"edges": [], "pageInfo": {"hasNextPage": False, "endCursor": None}}}},
        status=200,
    )
    responses.add(
        responses.POST,
        OTHER_ENDPOINT,
        json={"data": {"products": {"edges": [], "pageInfo": {"hasNextPage": False, "endCursor": None}}}},
        status=200,
    )

    services.list_products(shopify_store)
    services.list_products(other_shopify_store)

    call_a, call_b = responses.calls[0], responses.calls[1]
    assert call_a.request.url == ENDPOINT
    assert call_b.request.url == OTHER_ENDPOINT
    assert call_a.request.headers["X-Shopify-Access-Token"] == "shpat_test_token_1"
    assert call_b.request.headers["X-Shopify-Access-Token"] == "shpat_test_token_2"
