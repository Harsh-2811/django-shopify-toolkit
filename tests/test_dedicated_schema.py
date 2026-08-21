"""Verifies migrations/0002_dedicated_schema.py's actual database effect, not just the
get_qualified_table_name() string logic already covered in test_conf.py.

Runs meaningfully under both settings modules — asserts "public" when SHOPIFY_TOOLKIT_DB_SCHEMA
is unset (tests.settings, the normal CI job) and the configured schema when it's set
(tests.settings_dedicated_schema) — so this same file proves both that the default behavior is
unaffected and that the feature actually does what it claims, without a skip-based split.

Postgres-only, same as the feature itself: skipped on other vendors (`connection.cursor()` /
information_schema.tables don't apply the same way — verified elsewhere in this suite that raw
cursor access is broken on django-mongodb-backend).
"""
import pytest
from django.db import connection

from shopify_toolkit.conf import get_db_schema
from shopify_toolkit.models import ShopifyStore, WebhookEvent

pytestmark = pytest.mark.skipif(
    connection.vendor != "postgresql",
    reason="dedicated-schema support is Postgres-only",
)


@pytest.mark.django_db
def test_tables_land_in_the_configured_schema():
    expected_schema = get_db_schema() or "public"
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT table_schema, table_name FROM information_schema.tables "
            "WHERE table_name IN ('shopify_toolkit_shopifystore', 'shopify_toolkit_webhookevent') "
            "ORDER BY table_name"
        )
        rows = cursor.fetchall()
    assert rows == [
        (expected_schema, "shopify_toolkit_shopifystore"),
        (expected_schema, "shopify_toolkit_webhookevent"),
    ]


@pytest.mark.django_db
def test_orm_round_trip_against_configured_table():
    store = ShopifyStore.objects.create(
        shop_domain="dedicated-schema-test.myshopify.com", access_token="shpat_test"
    )
    assert ShopifyStore.objects.get(pk=store.pk).shop_domain == "dedicated-schema-test.myshopify.com"

    event = WebhookEvent.objects.create(store=store, topic="orders/create", payload={})
    assert WebhookEvent.objects.filter(store=store).first() == event
