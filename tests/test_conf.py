from shopify_toolkit.conf import get_max_backoff_seconds, get_request_timeout


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
