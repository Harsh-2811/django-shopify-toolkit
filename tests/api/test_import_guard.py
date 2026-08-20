import importlib
import sys

import pytest


def test_api_package_raises_clear_import_error_without_drf(monkeypatch):
    # Simulate djangorestframework not being installed: setting a sys.modules
    # entry to None makes `import rest_framework` raise ImportError.
    monkeypatch.setitem(sys.modules, "rest_framework", None)
    sys.modules.pop("shopify_toolkit.api", None)

    with pytest.raises(ImportError, match=r"django-shopify-toolkit\[drf\]"):
        importlib.import_module("shopify_toolkit.api")


def test_core_services_import_fine_without_drf(monkeypatch):
    monkeypatch.setitem(sys.modules, "rest_framework", None)
    # Only reload the leaf module under test — reloading shopify_toolkit.models
    # itself would re-register Django models and trigger warnings.
    sys.modules.pop("shopify_toolkit.products.services", None)

    # This should not require rest_framework to be installed.
    products_services = importlib.import_module("shopify_toolkit.products.services")
    assert hasattr(products_services, "list_products")
