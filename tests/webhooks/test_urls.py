from shopify_toolkit.webhooks.urls import urlpatterns


def test_receive_webhook_url_is_registered():
    names = [p.name for p in urlpatterns]
    assert "receive" in names
