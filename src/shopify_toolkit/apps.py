from django.apps import AppConfig


class ShopifyToolkitConfig(AppConfig):
    

    name = "shopify_toolkit"
    label = "shopify_toolkit"
    verbose_name = "Shopify Toolkit"

    @property
    def default_auto_field(self) -> str:

        from .conf import get_default_auto_field

        return get_default_auto_field()
