"""Core models for django-shopify-toolkit.

Don't add extra fields here without a matching migration.

ShopifyStore.client_id/client_secret/access_token_expires_at support Shopify's
Client Credentials Grant: custom apps created via the Dev Dashboard from
Jan 1, 2026 onward no longer expose a static access token in the admin UI —
only a Client ID/Secret, which must be exchanged for a token that expires
after ~24 hours. See shopify_toolkit/auth.py. Apps created before that date
keep using a static access_token as before; nothing changes for them.
"""
from django.db import models
from encrypted_model_fields.fields import EncryptedCharField

from .conf import get_qualified_table_name


class ShopifyStore(models.Model):
    """One Shopify store this Django install is authorized to talk to.

    A single deployment can hold many of these (multi-tenant) — every
    Shopify API call in this package takes an explicit ShopifyStore
    instance rather than assuming a single global store.

    Two ways to authenticate a store — set whichever applies:
      - access_token alone: a static token from a pre-2026 custom app.
        Used as-is, forever.
      - client_id + client_secret: a Dev Dashboard app (2026+). auth.py
        exchanges these for a token via the Client Credentials Grant and
        caches the result in access_token/access_token_expires_at,
        transparently refreshing it once it's close to expiring. This is
        per-store persisted state, not module-level shared state, so it
        stays safe for multi-tenant use.
    """

    shop_domain = models.CharField(max_length=255, unique=True)
    access_token = EncryptedCharField(max_length=255, blank=True, default="")
    access_token_expires_at = models.DateTimeField(null=True, blank=True)
    client_id = EncryptedCharField(max_length=255, blank=True, default="")
    client_secret = EncryptedCharField(max_length=255, blank=True, default="")
    api_version = models.CharField(max_length=10, default="2026-07")
    scopes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Shopify store"
        verbose_name_plural = "Shopify stores"
        if _qualified := get_qualified_table_name("shopify_toolkit_shopifystore"):
            db_table = _qualified

    def __str__(self) -> str:
        return self.shop_domain


class WebhookEvent(models.Model):
    """A single received Shopify webhook payload, tied to the store it came from."""

    store = models.ForeignKey(
        ShopifyStore, on_delete=models.CASCADE, related_name="webhook_events"
    )
    topic = models.CharField(max_length=100)
    payload = models.JSONField()
    received_at = models.DateTimeField(auto_now_add=True)
    processed = models.BooleanField(default=False)
    processing_error = models.TextField(blank=True)

    class Meta:
        ordering = ["-received_at"]
        if _qualified := get_qualified_table_name("shopify_toolkit_webhookevent"):
            db_table = _qualified

    def __str__(self) -> str:
        return f"{self.topic} ({self.store.shop_domain})"
