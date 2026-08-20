import pytest
import responses

from shopify_toolkit.customers import services
from shopify_toolkit.exceptions import ShopifyGraphQLError, ShopifyUserError

ENDPOINT = "https://test-store.myshopify.com/admin/api/2025-01/graphql.json"
OTHER_ENDPOINT = "https://other-store.myshopify.com/admin/api/2025-01/graphql.json"

CUSTOMER_ID = "gid://shopify/Customer/1"


def _customer_node(**overrides):
    node = {
        "id": CUSTOMER_ID,
        "firstName": "Ada",
        "lastName": "Lovelace",
        "email": "ada@example.com",
        "phone": None,
        "tags": [],
        "createdAt": "2026-01-01T00:00:00Z",
        "updatedAt": "2026-01-01T00:00:00Z",
    }
    node.update(overrides)
    return node


@responses.activate
@pytest.mark.django_db
def test_list_customers_success(shopify_store):
    responses.add(
        responses.POST,
        ENDPOINT,
        json={
            "data": {
                "customers": {
                    "edges": [{"cursor": "c1", "node": _customer_node()}],
                    "pageInfo": {"hasNextPage": False, "endCursor": "c1"},
                }
            }
        },
        status=200,
    )
    page = services.list_customers(shopify_store)
    assert len(page.customers) == 1
    assert page.customers[0].email == "ada@example.com"


@responses.activate
@pytest.mark.django_db
def test_list_customers_graphql_error_raises(shopify_store):
    responses.add(responses.POST, ENDPOINT, json={"errors": [{"message": "boom"}]}, status=200)
    with pytest.raises(ShopifyGraphQLError):
        services.list_customers(shopify_store)


@responses.activate
@pytest.mark.django_db
def test_get_customer_success(shopify_store):
    responses.add(responses.POST, ENDPOINT, json={"data": {"customer": _customer_node()}}, status=200)
    customer = services.get_customer(shopify_store, CUSTOMER_ID)
    assert customer.first_name == "Ada"


@responses.activate
@pytest.mark.django_db
def test_get_customer_not_found_returns_none(shopify_store):
    responses.add(responses.POST, ENDPOINT, json={"data": {"customer": None}}, status=200)
    assert services.get_customer(shopify_store, "gid://shopify/Customer/999") is None


@responses.activate
@pytest.mark.django_db
def test_create_customer_success(shopify_store):
    responses.add(
        responses.POST,
        ENDPOINT,
        json={"data": {"customerCreate": {"customer": _customer_node(), "userErrors": []}}},
        status=200,
    )
    customer = services.create_customer(shopify_store, email="ada@example.com", firstName="Ada")
    assert customer.email == "ada@example.com"


@responses.activate
@pytest.mark.django_db
def test_create_customer_accepts_snake_case_kwargs(shopify_store):
    responses.add(
        responses.POST,
        ENDPOINT,
        json={"data": {"customerCreate": {"customer": _customer_node(), "userErrors": []}}},
        status=200,
    )
    services.create_customer(shopify_store, email="ada@example.com", first_name="Ada", last_name="Lovelace")

    import json

    sent_body = json.loads(responses.calls[0].request.body)
    assert sent_body["variables"]["input"] == {
        "email": "ada@example.com",
        "firstName": "Ada",
        "lastName": "Lovelace",
    }


@responses.activate
@pytest.mark.django_db
def test_create_customer_user_error_raises(shopify_store):
    responses.add(
        responses.POST,
        ENDPOINT,
        json={
            "data": {
                "customerCreate": {
                    "customer": None,
                    "userErrors": [{"field": ["email"], "message": "is invalid"}],
                }
            }
        },
        status=200,
    )
    with pytest.raises(ShopifyUserError):
        services.create_customer(shopify_store, email="not-an-email")


@responses.activate
@pytest.mark.django_db
def test_update_customer_success(shopify_store):
    responses.add(
        responses.POST,
        ENDPOINT,
        json={
            "data": {
                "customerUpdate": {
                    "customer": _customer_node(lastName="King"),
                    "userErrors": [],
                }
            }
        },
        status=200,
    )
    customer = services.update_customer(shopify_store, customer_id=CUSTOMER_ID, lastName="King")
    assert customer.last_name == "King"


@responses.activate
@pytest.mark.django_db
def test_store_isolation_list_customers(shopify_store, other_shopify_store):
    empty_page = {
        "data": {"customers": {"edges": [], "pageInfo": {"hasNextPage": False, "endCursor": None}}}
    }
    responses.add(responses.POST, ENDPOINT, json=empty_page, status=200)
    responses.add(responses.POST, OTHER_ENDPOINT, json=empty_page, status=200)

    services.list_customers(shopify_store)
    services.list_customers(other_shopify_store)

    call_a, call_b = responses.calls[0], responses.calls[1]
    assert call_a.request.headers["X-Shopify-Access-Token"] == "shpat_test_token_1"
    assert call_b.request.headers["X-Shopify-Access-Token"] == "shpat_test_token_2"
