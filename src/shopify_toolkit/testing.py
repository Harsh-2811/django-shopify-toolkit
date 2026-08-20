"""Test helpers for consumers of django-shopify-toolkit.

Not imported by anything else in this package — install with
`pip install django-shopify-toolkit[testing]` to use it in your own test
suite. Saves you from hand-rolling `responses` mocks for this package's
GraphQL endpoint every time you want to test code that calls a
shopify_toolkit service function.

Usage:

    from shopify_toolkit.testing import mock_shopify_api

    def test_my_view(shopify_store):
        with mock_shopify_api(shopify_store, {"data": {"shop": {"name": "Test"}}}):
            # any code that calls shopify_toolkit under here hits this
            # canned response instead of the real Shopify API
            ...

    # or as a decorator:
    @mock_shopify_api(shopify_store, {"data": {"shop": {"name": "Test"}}})
    def test_my_view():
        ...
"""
from __future__ import annotations

import functools

try:
    import responses
except ImportError as exc:
    raise ImportError(
        "shopify_toolkit.testing requires the `responses` library. Install "
        "it with `pip install django-shopify-toolkit[testing]`."
    ) from exc

from .models import ShopifyStore


def _graphql_endpoint(store: ShopifyStore) -> str:
    return f"https://{store.shop_domain}/admin/api/{store.api_version}/graphql.json"


class _ShopifyApiMock:
    """Context manager + decorator wrapper around a responses.RequestsMock.

    responses.RequestsMock only supports `with` on its own — it has no
    `__call__`, so it can't be used directly as `@mock_shopify_api(...)`.
    This adds that (verified empirically, not assumed) so mock_shopify_api()
    works both ways, matching how e.g. unittest.mock.patch behaves.
    """

    def __init__(self, mock: "responses.RequestsMock"):
        self._mock = mock

    def __enter__(self):
        return self._mock.__enter__()

    def __exit__(self, *exc_info):
        return self._mock.__exit__(*exc_info)

    def __call__(self, func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            with self:
                return func(*args, **kwargs)

        return wrapper


def mock_shopify_api(
    store: ShopifyStore,
    response: dict | None = None,
    *,
    status: int = 200,
) -> _ShopifyApiMock:
    """Mock every GraphQL call to `store` with a fixed JSON response.

    Usable as both a context manager and a decorator. Defaults to an empty
    success response ({"data": {}}) if you just want to stub out a call
    without asserting on its shape.

    Only handles a single canned response for every matching call — for
    more elaborate sequences (different responses per call, asserting on
    request bodies) use `responses` directly; this is a convenience wrapper
    for the common case, not a replacement.
    """
    if response is None:
        response = {"data": {}}

    mock = responses.RequestsMock(assert_all_requests_are_fired=False)
    mock.add(responses.POST, _graphql_endpoint(store), json=response, status=status)
    return _ShopifyApiMock(mock)


def mock_shopify_error(
    store: ShopifyStore,
    message: str,
    *,
    status: int = 200,
) -> _ShopifyApiMock:
    """Mock every GraphQL call to `store` with a Shopify-shaped errors array
    — triggers ShopifyGraphQLError in the code under test. Same
    context-manager/decorator usage as mock_shopify_api().
    """
    mock = responses.RequestsMock(assert_all_requests_are_fired=False)
    mock.add(
        responses.POST,
        _graphql_endpoint(store),
        json={"errors": [{"message": message}]},
        status=status,
    )
    return _ShopifyApiMock(mock)
