from shopify_toolkit.conf import (
    get_max_backoff_seconds,
    get_qualified_table_name,
    get_request_timeout,
)


def test_get_max_backoff_seconds_default():
    assert get_max_backoff_seconds() == 10


def test_get_max_backoff_seconds_override(settings):
    settings.SHOPIFY_TOOLKIT_MAX_BACKOFF_SECONDS = 5
    assert get_max_backoff_seconds() == 5


def test_get_request_timeout_default():
    assert get_request_timeout() == 30


def test_get_request_timeout_override(settings):
    settings.SHOPIFY_TOOLKIT_REQUEST_TIMEOUT = 15
    assert get_request_timeout() == 15


def test_get_qualified_table_name_returns_none_when_unset():
    # None, not the unqualified name — db_table must only be set as an attribute at all when
    # this is non-None, or Django's migration autodetector treats it as a change.
    assert get_qualified_table_name("shopify_toolkit_shopifystore") is None


def test_get_qualified_table_name_quotes_schema_and_table_separately(settings):
    settings.SHOPIFY_TOOLKIT_DB_SCHEMA = "shopify_data"
    assert (
        get_qualified_table_name("shopify_toolkit_shopifystore")
        == 'shopify_data"."shopify_toolkit_shopifystore'
    )
