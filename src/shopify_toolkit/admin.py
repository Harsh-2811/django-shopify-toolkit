from django.contrib import admin

from .models import ShopifyStore, WebhookEvent


@admin.register(ShopifyStore)
class ShopifyStoreAdmin(admin.ModelAdmin):
    # access_token/client_secret are deliberately excluded here so raw
    # secrets are never shown in the admin list view.
    list_display = ("shop_domain", "api_version", "is_active", "created_at", "updated_at")
    list_filter = ("is_active", "api_version")
    search_fields = ("shop_domain",)
    readonly_fields = ("access_token_expires_at", "created_at", "updated_at")

    def get_readonly_fields(self, request, obj=None):
        # access_token and client_secret can be entered when a store is
        # first created, but are read-only from then on in the detail view
        # — never re-editable or re-displayed as plain text once set.
        # (access_token is still updated automatically by auth.py's token
        # exchange, which writes via the ORM directly and isn't affected by
        # this admin-only restriction.)
        if obj is not None:
            return self.readonly_fields + ("access_token", "client_secret")
        return self.readonly_fields


@admin.register(WebhookEvent)
class WebhookEventAdmin(admin.ModelAdmin):
    list_display = ("topic", "store", "received_at", "processed")
    list_filter = ("topic", "processed")
    search_fields = ("topic", "store__shop_domain")
    readonly_fields = ("received_at",)
