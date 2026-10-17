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
