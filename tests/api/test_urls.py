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
