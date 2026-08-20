import base64
import hashlib
import hmac

from shopify_toolkit.webhooks.verify import verify_webhook

# Matches SHOPIFY_TOOLKIT_API_SECRET in tests/settings.py
SECRET = "test-api-secret"


def _sign(body: bytes) -> str:
    digest = hmac.new(SECRET.encode("utf-8"), body, hashlib.sha256).digest()
    return base64.b64encode(digest).decode("utf-8")


def test_verify_webhook_valid_signature_returns_true():
    body = b'{"id": 123, "topic": "orders/create"}'
    signature = _sign(body)

    assert verify_webhook(body, signature) is True


def test_verify_webhook_tampered_payload_returns_false():
    body = b'{"id": 123, "topic": "orders/create"}'
    signature = _sign(body)  # signature computed for the original body
    tampered_body = b'{"id": 999, "topic": "orders/create"}'

    # tampered payload + the original signature must fail, not raise
    assert verify_webhook(tampered_body, signature) is False


def test_verify_webhook_missing_signature_returns_false():
    body = b'{"id": 123}'

    assert verify_webhook(body, None) is False
