import pytest

from shopify_toolkit.models import ShopifyStore


@pytest.fixture
def shopify_store(db):
    """A store fixture used across module test suites."""
    return ShopifyStore.objects.create(
        shop_domain="test-store.myshopify.com",
        access_token="shpat_test_token_1",
        api_version="2025-01",
    )


@pytest.fixture
def other_shopify_store(db):
    """A second, distinct store — used for store-isolation tests."""
    return ShopifyStore.objects.create(
        shop_domain="other-store.myshopify.com",
        access_token="shpat_test_token_2",
        api_version="2025-01",
    )
