"""Optional DRF layer for django-shopify-toolkit.

Only import from shopify_toolkit.api if djangorestframework is installed —
install it with `pip install django-shopify-toolkit[drf]`. Core
shopify_toolkit functionality (client, models, products/orders/customers/
webhooks services) never depends on this package and must keep working
without it.
"""
try:
    import rest_framework  # noqa: F401
except ImportError as exc:
    raise ImportError(
        "shopify_toolkit.api requires djangorestframework, which isn't "
        "installed. Install it with `pip install django-shopify-toolkit[drf]`."
    ) from exc
