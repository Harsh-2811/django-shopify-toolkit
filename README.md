# django-shopify-toolkit

[![PyPI Version](https://img.shields.io/pypi/v/django-shopify-toolkit.svg)](https://pypi.org/project/django-shopify-toolkit/)
[![Python Versions](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12-blue)](https://python.org)
[![Django Versions](https://img.shields.io/badge/django-4.2%20%7C%205.x-green)](https://djangoproject.com)
[![License: MIT](https://img.shields.io/badge/license-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A reusable, installable Django app that gives any Django project Shopify
Admin GraphQL integration out of the box — working tables, an
admin-registered `ShopifyStore` model, and a Python API (plus optional REST
endpoints) for products, product images, product variants and options,
orders, customers, webhooks, and bulk data exports.

The package is multi-tenant: one Django install can manage many Shopify
stores, each with its own encrypted credentials. Every function takes an
explicit `ShopifyStore` — there's no global/default store.

## Requirements

* Python 3.10, 3.11, or 3.12
* Django 4.2 or 5.x

## Installation

```bash
pip install django-shopify-toolkit

# with the optional DRF serializers/viewsets
pip install django-shopify-toolkit[drf]

# with test helpers for your own test suite
pip install django-shopify-toolkit[testing]
```

Add it to `INSTALLED_APPS`:

```python
INSTALLED_APPS = [
    ...,
    "shopify_toolkit",
]
```

Run migrations — the app ships its own, so this just works:

```bash
python manage.py migrate
```

## Quick start

```python
from shopify_toolkit.models import ShopifyStore
from shopify_toolkit.products import services as products

store = ShopifyStore.objects.get(shop_domain="my-shop.myshopify.com")

page = products.list_products(store, first=10)
for product in page.products:
    print(product.title, product.status)
```

Every function takes a `ShopifyStore` and returns a plain dataclass or
raises a typed exception — never a raw GraphQL response.

## Settings

```python
# required
FIELD_ENCRYPTION_KEY = "..."                 # for encrypted token storage — see
                                              # django-encrypted-model-fields docs
                                              # (cryptography.fernet.Fernet.generate_key())
SHOPIFY_TOOLKIT_API_SECRET = "..."           # your app's API secret, for HMAC webhook verification

# optional, with defaults
SHOPIFY_TOOLKIT_API_VERSION = "2026-07"      # default Shopify Admin API version
SHOPIFY_TOOLKIT_MAX_RETRIES = 3              # retries for transient network errors
SHOPIFY_TOOLKIT_RATE_LIMIT_BUFFER = 100      # pause outgoing requests once the
                                              # cost throttle bucket drops below this
SHOPIFY_TOOLKIT_MAX_BACKOFF_SECONDS = 10     # cap on the rate-limit backoff sleep
SHOPIFY_TOOLKIT_REQUEST_TIMEOUT = 30         # per-request timeout (seconds)
SHOPIFY_TOOLKIT_MAX_POOLED_SESSIONS = 500    # max distinct stores kept in the
                                              # connection pool at once (LRU-evicted)
```

`SHOPIFY_TOOLKIT_API_SECRET` is only validated the first time it's actually
needed (e.g. verifying a webhook) — you'll get a clear `ImproperlyConfigured`
the moment you do, not at import time.

Shopify supports each Admin API version for about 12 months. Bump
`SHOPIFY_TOOLKIT_API_VERSION`/`ShopifyStore.api_version` periodically as
versions retire.

## Authenticating a store

Which fields you set on `ShopifyStore` depends on when your Shopify app was
created:

```python
from shopify_toolkit.models import ShopifyStore

# Custom app created before Jan 2026 — a static token from Settings → Apps
# → Develop apps → API credentials. Never expires.
ShopifyStore.objects.create(
    shop_domain="my-shop.myshopify.com",
    access_token="shpat_...",
)

# Dev Dashboard app (2026+) — no static token shown in the UI, only a
# Client ID/Secret (Dev Dashboard → your app → Settings). Leave
# access_token blank.
ShopifyStore.objects.create(
    shop_domain="my-shop.myshopify.com",
    client_id="...",
    client_secret="...",
)
```

For a Client ID/Secret store, the first API call transparently exchanges
those for an access token (valid ~24h) and caches it on the store row,
refreshing automatically before it expires — every function below resolves
this for you.

`ShopifyStore` fields: `shop_domain`, `access_token` (encrypted), `client_id`
(encrypted), `client_secret` (encrypted), `access_token_expires_at`
(set automatically once a Client ID/Secret store's first token is
exchanged), `api_version` (default `"2026-07"`), `scopes`, `is_active`
(default `True` — the webhook receiver rejects webhooks for inactive
stores), `created_at`, `updated_at`.

Required Admin API scopes, by area: `read_products`/`write_products`
(products, images, variants, options), `read_orders`/`write_orders`
(orders, including fulfilling), `read_customers`/`write_customers`
(customers). Webhooks don't have their own scope — subscribing to a topic
needs the scope of the resource it covers (e.g. `ORDERS_CREATE` needs
`read_orders`).

**Client Credentials Grant token refresh needs Postgres or MySQL.**
Concurrent requests to an expired-token store serialize on a database row
lock (`SELECT ... FOR UPDATE`) so only one of them actually calls Shopify's
OAuth endpoint. SQLite has no real row-locking for that statement, so
multiple requests can race and even error under write contention. SQLite is
fine for everything else this package does — static-token stores, webhook
ingestion — just not this one path in production under real concurrent
traffic.

## Usage

### Products

```python
from shopify_toolkit.products import services as products

# List products, paginated — returns ProductPage(products, has_next_page, end_cursor)
page = products.list_products(store, first=20)
if page.has_next_page:
    products.list_products(store, first=20, after=page.end_cursor)

# Or iterate every product without manual pagination
for product in products.iter_all_products(store):
    ...

# Get a single product — returns Product | None
product = products.get_product(store, "gid://shopify/Product/123")

# Create / update / delete
product = products.create_product(store, title="Cosmic Mug", vendor="Acme", tags=["new"])
product = products.update_product(store, product_id=product.id, title="Cosmic Mug v2")
products.delete_product(store, product.id)
```

`create_product`/`update_product` accept any `ProductInput` field, in
either snake_case or Shopify's native camelCase — snake_case is converted
automatically. `status=` is typed `Literal["ACTIVE", "ARCHIVED", "DRAFT"]`.

`Product` fields: `id`, `title`, `handle`, `description`, `status`,
`vendor`, `product_type`, `tags`, `created_at`, `updated_at`, `images`,
`options`, `variants`.

### Product images

```python
from shopify_toolkit.images import services as images

image_list = images.list_product_images(store, product.id)
image = images.add_product_image(store, product.id, src="https://example.com/mug.png", alt_text="Front view")
images.remove_product_image(store, product.id, image.id)
images.reorder_product_images(store, product.id, [img.id for img in image_list])

# Upload a local file directly (path, Django UploadedFile, or any
# file-like object) instead of requiring a public URL
image = images.upload_product_image_file(store, product.id, "/path/to/photo.png", alt_text="Studio shot")
```

`ProductImage` fields: `id`, `url` (`str | None` — briefly null while
Shopify processes the upload), `alt_text`.

### Product variants and options

```python
from shopify_toolkit.products import services as products

# Options (e.g. Size, Color)
option = products.create_product_option(store, product.id, name="Size", values=["S", "M", "L"])
products.update_product_option(store, product.id, option.id, name="Size", values_to_add=["XL"])
products.delete_product_option(store, product.id, option.id)

# Variants
variant = products.create_product_variant(
    store, product.id, price="29.99", sku="MUG-S", option_values=[{"optionId": option.id, "name": "S"}]
)
products.update_product_variant(store, product.id, variant.id, price="24.99")
products.bulk_create_variants(store, product.id, [{"price": "19.99"}, {"price": "24.99"}])
products.bulk_update_variants(store, product.id, [{"id": variant.id, "sku": "MUG-S-NEW"}])
products.delete_product_variants(store, product.id, [variant.id])

variants = products.list_product_variants(store, product.id)
single = products.get_product_variant(store, variant.id)
```

Built on `productVariantsBulkCreate`/`productVariantsBulkUpdate`/
`productVariantsBulkDelete` throughout — including for single-variant
updates — since Shopify removed the singular `productVariantCreate`/
`productVariantUpdate`/`productVariantDelete` mutations.

`ProductVariant` fields: `id`, `title`, `price`, `compare_at_price`, `sku`,
`barcode`, `available_for_sale`, `inventory_quantity`, `inventory_item_id`,
`inventory_tracked`, `weight`, `weight_unit`, `requires_shipping`,
`taxable`, `image_id`, `image_url`, `image_alt_text`, `selected_options`,
`product_id`. `ProductOption` fields: `id`, `name`, `position`, `values`.

### Orders

```python
from shopify_toolkit.orders import services as orders

page = orders.list_orders(store, first=20)
order = orders.get_order(store, "gid://shopify/Order/123")
orders.update_order(store, order_id=order.id, tags=["priority"])

# fulfillment_order_id is a FulfillmentOrder GraphQL ID, not the Order ID
orders.update_fulfillment_status(store, fulfillment_order_id="gid://shopify/FulfillmentOrder/1", tracking_number="1Z999")

for order in orders.iter_all_orders(store):
    ...
```

`Order` fields: `id`, `name`, `email`, `financial_status`,
`fulfillment_status`, `total_price`, `currency_code`, `created_at`,
`updated_at`.

### Customers

```python
from shopify_toolkit.customers import services as customers

page = customers.list_customers(store, first=20)
customer = customers.get_customer(store, "gid://shopify/Customer/123")
customer = customers.create_customer(store, email="ada@example.com", first_name="Ada", last_name="Lovelace")
customers.update_customer(store, customer_id=customer.id, last_name="King")

for customer in customers.iter_all_customers(store):
    ...
```

`Customer` fields: `id`, `first_name`, `last_name`, `email`, `phone`,
`tags`, `created_at`, `updated_at`.

### Webhooks

```python
# your project's urls.py — exposes POST /shopify/webhooks/receive/
from django.urls import include, path
urlpatterns = [..., path("shopify/webhooks/", include("shopify_toolkit.webhooks.urls"))]
```

The receiver verifies `X-Shopify-Hmac-Sha256` against
`SHOPIFY_TOOLKIT_API_SECRET`, resolves the `ShopifyStore` from the
`X-Shopify-Shop-Domain` header, and saves a `WebhookEvent` row — `401` for
a bad/missing signature, `404` for an unknown/inactive store.

```python
from shopify_toolkit.webhooks import registry
from shopify_toolkit.webhooks.verify import verify_webhook

registry.register_webhook(store, topic="ORDERS_CREATE", callback_url="https://my-app.example.com/shopify/webhooks/receive/")
registry.list_webhooks(store)
verify_webhook(raw_request_body_bytes, request.headers.get("X-Shopify-Hmac-Sha256"))
```

`WebhookSubscription` fields: `id`, `topic`, `callback_url`, `created_at`.

The receiver only saves each incoming webhook as a `WebhookEvent`
(`store`, `topic`, `payload`, `received_at`, `processed`,
`processing_error`) — processing it is on you:

```python
from shopify_toolkit.models import WebhookEvent

for event in WebhookEvent.objects.filter(store=store, processed=False):
    try:
        handle(event.topic, event.payload)
        event.processed = True
        event.save(update_fields=["processed"])
    except Exception as exc:
        event.processing_error = str(exc)
        event.save(update_fields=["processing_error"])
```

A `webhook_received` signal is also dispatched after each verified webhook
is saved, so you can react from anywhere in your project:

```python
from django.dispatch import receiver
from shopify_toolkit.signals import webhook_received

@receiver(webhook_received)
def handle_webhook(sender, store, topic, payload, event, **kwargs):
    if topic == "orders/create":
        ...
```

### Bulk operations

For datasets too large for paginated GraphQL — Shopify runs your query as
an async job and hands back a JSONL file when it's done:

```python
from shopify_toolkit.bulk_operations import services as bulk

operation = bulk.run_bulk_query(store, "{ products { edges { node { id title } } } }")
operation = bulk.wait_for_bulk_operation(store, poll_interval=2.0, timeout=300.0)
rows = bulk.download_bulk_operation_result(operation)
current = bulk.get_current_bulk_operation(store)
```

`BulkOperation` fields: `id`, `status`, `error_code`, `object_count`,
`file_size`, `url`, `partial_data_url`.

### The underlying GraphQL client

Every function above is a thin wrapper around `ShopifyGraphQLClient` — the
store-scoped client with retry, rate-limit backoff, and connection pooling
built in. You normally never touch it directly; it's there if you need a
raw query/mutation outside the surface this package provides:

```python
from shopify_toolkit.client import ShopifyGraphQLClient

client = ShopifyGraphQLClient(store)
data = client.execute("query { shop { name } }")
```

### Errors

Every function above raises a typed exception from
`shopify_toolkit.exceptions` instead of a raw `requests`/GraphQL error:
`ShopifyGraphQLError` (transport-level GraphQL errors), `ShopifyUserError`
(mutation validation failures), `ShopifyRateLimitError` (throttled),
`ShopifyRequestError` (network failure or bad token exchange),
`ShopifyStoreNotConfigured` (a store with neither `access_token` nor
`client_id`/`client_secret` set).

### Optional: DRF API layer

If `djangorestframework` is installed, wire up store-scoped REST endpoints
wrapping the same services:

```python
# your project's urls.py
urlpatterns = [..., path("api/shopify/", include("shopify_toolkit.api.urls"))]
```

All scoped under `/api/shopify/stores/<store_pk>/`:

* `products/` — `GET` (list), `POST` (create)
* `products/<product_id>/` — `GET`, `PUT`/`PATCH`, `DELETE`
* `orders/` — `GET` (list)
* `orders/<order_id>/` — `GET`
* `orders/<fulfillment_order_id>/fulfill/` — `POST`
* `customers/` — `GET` (list), `POST` (create)
* `customers/<customer_id>/` — `GET`, `PUT`/`PATCH`

These endpoints ship with no authentication/permission classes of their
own — add `permission_classes`/`DEFAULT_PERMISSION_CLASSES` in your own
project before exposing them.

### Testing your own code

Install with `pip install django-shopify-toolkit[testing]`:

```python
from shopify_toolkit.testing import mock_shopify_api, mock_shopify_error

def test_something(shopify_store):
    with mock_shopify_api(shopify_store, {"data": {"shop": {"name": "Test"}}}):
        ...  # code under test that calls shopify_toolkit

@mock_shopify_api(shopify_store, {"data": {"shop": {"name": "Test"}}})
def test_something_else():
    ...

@mock_shopify_error(shopify_store, "field not found")
def test_error_handling():
    ...  # raises ShopifyGraphQLError in the code under test
```

Both default to an empty success response (`{"data": {}}`) if you just need
to stub a call without asserting on its shape.

## License

MIT
