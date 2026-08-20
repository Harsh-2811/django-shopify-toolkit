import pytest
from django.contrib import admin

from shopify_toolkit.admin import ShopifyStoreAdmin
from shopify_toolkit.models import ShopifyStore


@pytest.fixture
def store_admin():
    return ShopifyStoreAdmin(ShopifyStore, admin.site)


def test_access_token_editable_on_add(store_admin):
    assert "access_token" not in store_admin.get_readonly_fields(request=None, obj=None)


@pytest.mark.django_db
def test_access_token_readonly_on_change(store_admin, shopify_store):
    assert "access_token" in store_admin.get_readonly_fields(request=None, obj=shopify_store)


def test_access_token_excluded_from_list_display(store_admin):
    assert "access_token" not in store_admin.list_display
