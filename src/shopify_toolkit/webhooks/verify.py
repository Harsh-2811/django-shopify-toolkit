"""HMAC-SHA256 verification for incoming Shopify webhooks.

Every webhook payload is verified against SHOPIFY_TOOLKIT_API_SECRET before it's trusted.
No exceptions.
"""
from __future__ import annotations

import base64
import hashlib
import hmac

from ..conf import get_api_secret


def verify_webhook(raw_body: bytes, hmac_header: str | None) -> bool:
    """Verify a raw webhook body against the X-Shopify-Hmac-Sha256 header.

    Returns False for a missing or tampered signature — it never raises for
    an invalid signature. It does propagate ImproperlyConfigured if
    SHOPIFY_TOOLKIT_API_SECRET isn't set, since that's a deployment error,
    not an expected API state.
    """
    if not hmac_header:
        return False

    secret = get_api_secret()
    computed_digest = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).digest()
    computed_signature = base64.b64encode(computed_digest).decode("utf-8")

    return hmac.compare_digest(computed_signature, hmac_header)
