from shopify_toolkit.api.urls import urlpatterns


def test_expected_routes_are_registered():
    names = {p.name for p in urlpatterns}
    assert names == {
        "product-list",
        "product-detail",
        "order-list",
        "order-detail",
        "order-fulfill",
        "customer-list",
        "customer-detail",
    }


def test_customer_detail_route_supports_delete():
    from django.urls import resolve

    match = resolve("/stores/1/customers/gid://shopify/Customer/1/", urlconf="shopify_toolkit.api.urls")
    assert match.func.actions["delete"] == "destroy"



def test_fulfill_route_is_not_swallowed_by_order_detail():
    """`<path:pk>` matches slashes, so the detail route used to capture pk=".../fulfill"."""
    from django.urls import resolve

    match = resolve("/stores/1/orders/gid://shopify/FulfillmentOrder/1/fulfill/", urlconf="shopify_toolkit.api.urls")
    assert match.url_name == "order-fulfill"
    assert match.kwargs == {"store_pk": 1, "pk": "gid://shopify/FulfillmentOrder/1"}


def test_order_detail_route_still_resolves():
    from django.urls import resolve

    match = resolve("/stores/1/orders/gid://shopify/Order/1/", urlconf="shopify_toolkit.api.urls")
    assert match.url_name == "order-detail"
    assert match.kwargs["pk"] == "gid://shopify/Order/1"
