import pytest

from shopify_toolkit.client import ShopifyGraphQLClient
from shopify_toolkit.exceptions import ShopifyGraphQLError
from shopify_toolkit.testing import mock_shopify_api, mock_shopify_error


@pytest.mark.django_db
def test_mock_shopify_api_as_context_manager(shopify_store):
    with mock_shopify_api(shopify_store, {"data": {"shop": {"name": "CtxMgr"}}}):
        data = ShopifyGraphQLClient(shopify_store).execute("query { shop { name } }")
    assert data == {"shop": {"name": "CtxMgr"}}


@pytest.mark.django_db
def test_mock_shopify_api_as_decorator(shopify_store):
    @mock_shopify_api(shopify_store, {"data": {"shop": {"name": "Decorator"}}})
    def call():
        return ShopifyGraphQLClient(shopify_store).execute("query { shop { name } }")

    assert call() == {"shop": {"name": "Decorator"}}


@pytest.mark.django_db
def test_mock_shopify_api_default_response_is_empty_success(shopify_store):
    with mock_shopify_api(shopify_store):
        data = ShopifyGraphQLClient(shopify_store).execute("query { shop { name } }")
    assert data == {}


@pytest.mark.django_db
def test_mock_shopify_error_raises_graphql_error(shopify_store):
    @mock_shopify_error(shopify_store, "boom")
    def call():
        return ShopifyGraphQLClient(shopify_store).execute("query { shop { name } }")

    with pytest.raises(ShopifyGraphQLError, match="boom"):
        call()


def test_testing_module_raises_clear_import_error_without_responses(monkeypatch):
    import importlib
    import sys

    monkeypatch.setitem(sys.modules, "responses", None)
    sys.modules.pop("shopify_toolkit.testing", None)

    with pytest.raises(ImportError, match=r"django-shopify-toolkit\[testing\]"):
        importlib.import_module("shopify_toolkit.testing")
