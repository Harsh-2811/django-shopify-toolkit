# django-shopify-toolkit

A reusable, installable Django app that gives any Django project Shopify Admin
GraphQL integration out of the box — working tables, an admin-registered
`ShopifyStore` model, and a Python API (plus optional REST endpoints) for
**products**, **product images**, **orders**, **customers**, **webhooks**, and
**bulk data exports**.

The package is **multi-tenant**: one Django install can manage many Shopify
stores, each with its own encrypted credentials. Every function takes an
explicit `ShopifyStore` — there's no global/default store.

Requires **Python 3.10+** and **Django 4.2+ / 5.x**.

## Quick look

```python
from shopify_toolkit.models import ShopifyStore
from shopify_toolkit.products import services as products

store = ShopifyStore.objects.get(shop_domain="my-shop.myshopify.com")

page = products.list_products(store, first=10)
for product in page.products:
    print(product.title, product.status)
```

That's the shape of every module below — pass a `ShopifyStore`, get back a
plain dataclass or typed exception, never a raw GraphQL response. Full setup
and every function in every module follow.

---

## Install

```bash
pip install django-shopify-toolkit
# or, if you want the optional DRF serializers/viewsets too:
pip install django-shopify-toolkit[drf]
```

```python
INSTALLED_APPS = [
    ...,
    "shopify_toolkit",
]
```

```bash
python manage.py migrate
```

---

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
                                              # (see "Concurrency & performance")
SHOPIFY_TOOLKIT_REQUEST_TIMEOUT = 30         # per-request timeout (seconds) for
                                              # GraphQL calls and token exchanges
SHOPIFY_TOOLKIT_MAX_POOLED_SESSIONS = 500    # max distinct stores kept in the
                                              # connection pool at once (LRU-evicted)
```

`SHOPIFY_TOOLKIT_API_SECRET` is only validated the first time it's actually
needed (e.g. verifying a webhook) — you'll get a clear `ImproperlyConfigured`
the moment you do, not at import time.

**Supported Shopify API versions:** Shopify supports each stable version for
12 months. As of this writing the actively supported versions are `2025-10`
(oldest, deprecating soon), `2026-01`, `2026-04`, and `2026-07` (latest,
recommended — the default here). `SHOPIFY_TOOLKIT_API_VERSION`/`ShopifyStore.api_version`
must be bumped periodically as versions retire — this package targets
whatever version you configure, but its GraphQL field names track Shopify's
*current* schema shape (e.g. the Media API, not the classic `ProductImage`
API it replaced), so very old versions aren't guaranteed to work.

---

## Authenticating a store

Which fields you set on `ShopifyStore` depends on when your Shopify app was
created:

```python
from shopify_toolkit.models import ShopifyStore

# Pre-2026 custom app — a static token from Settings → Apps → Develop apps
# → API credentials. Never expires.
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
refreshing automatically before it expires. You never call this yourself —
every function below resolves it for you.

Required Admin API scopes, by module: `read_products`/`write_products`
(products, images), `read_orders`/`write_orders` (orders — including
fulfilling), `read_customers`/`write_customers` (customers). Webhooks don't
have their own scope — subscribing to a topic needs the scope of the
resource it covers (e.g. `ORDERS_CREATE` needs `read_orders`).

---

## Products

```python
from shopify_toolkit.models import ShopifyStore
from shopify_toolkit.products import services as products

store = ShopifyStore.objects.get(shop_domain="my-shop.myshopify.com")

# List products, paginated — returns ProductPage(products, has_next_page, end_cursor)
page = products.list_products(store, first=20)
for product in page.products:
    print(product.title, product.status)
if page.has_next_page:
    products.list_products(store, first=20, after=page.end_cursor)

# Get a single product by its GraphQL ID — returns Product | None
product = products.get_product(store, "gid://shopify/Product/123")

# Create a product — returns the new Product
product = products.create_product(
    store, title="Cosmic Mug", vendor="Acme", product_type="Mug", tags=["new"]
)

# Update (edit) a product — returns the updated Product
product = products.update_product(store, product_id=product.id, title="Cosmic Mug v2")

# Delete a product — returns the deleted product's GraphQL ID
products.delete_product(store, product.id)

# Iterate every product without manual pagination — fetches subsequent
# pages automatically as you consume the generator
for product in products.iter_all_products(store):
    ...
```

`create_product`/`update_product` accept any `ProductInput` field, in either
snake_case (`product_type=`) or Shopify's native camelCase (`productType=`)
— snake_case is converted automatically. `status=` is typed as
`Literal["ACTIVE", "ARCHIVED", "DRAFT"]` for IDE autocomplete, but works
exactly like any other field.

**`Product`** fields: `id`, `title`, `handle`, `description`, `status`,
`vendor`, `product_type`, `tags` (`list[str]`), `created_at`, `updated_at`,
`images` (`list[ProductImage]`).
**`ProductPage`**: `products`, `has_next_page`, `end_cursor`.

---

## Product images

```python
from shopify_toolkit.images import services as images

# List images on a product — returns list[ProductImage]
image_list = images.list_product_images(store, product.id)

# Add an image from a URL — returns the new ProductImage
# (image.url can briefly be None — Shopify processes media asynchronously)
image = images.add_product_image(store, product.id, src="https://example.com/mug.png", alt_text="Front view")

# Remove an image — returns the deleted image's GraphQL ID
images.remove_product_image(store, product.id, image.id)

# Reorder images to match this exact order (first to last)
images.reorder_product_images(store, product.id, [img.id for img in image_list])
```

**`ProductImage`** (this module's version) fields: `id`, `url` (`str | None`
— null while Shopify is still processing it), `alt_text`.

---

## Orders

```python
from shopify_toolkit.orders import services as orders

# List orders, paginated — returns OrderPage(orders, has_next_page, end_cursor)
page = orders.list_orders(store, first=20)

# Get a single order by its GraphQL ID — returns Order | None
order = orders.get_order(store, "gid://shopify/Order/123")

# Update order-level fields (tags, note, email, ...) — returns the updated Order
orders.update_order(store, order_id=order.id, tags=["priority"])

# Fulfill an order (mark it fulfilled, optionally with tracking info) — returns the updated Order
# fulfillment_order_id is a FulfillmentOrder GraphQL ID, not the Order ID.
orders.update_fulfillment_status(
    store, fulfillment_order_id="gid://shopify/FulfillmentOrder/1", tracking_number="1Z999"
)

# Iterate every order without manual pagination
for order in orders.iter_all_orders(store):
    ...
```

**`Order`** fields: `id`, `name`, `email` (`str | None`), `financial_status`,
`fulfillment_status`, `total_price` (`str | None`), `currency_code`
(`str | None`), `created_at`, `updated_at`.
**`OrderPage`**: `orders`, `has_next_page`, `end_cursor`.

---

## Customers

```python
from shopify_toolkit.customers import services as customers

# List customers, paginated — returns CustomerPage(customers, has_next_page, end_cursor)
page = customers.list_customers(store, first=20)

# Get a single customer by its GraphQL ID — returns Customer | None
customer = customers.get_customer(store, "gid://shopify/Customer/123")

# Create a customer — returns the new Customer
customer = customers.create_customer(store, email="ada@example.com", first_name="Ada", last_name="Lovelace")

# Update a customer — returns the updated Customer
customers.update_customer(store, customer_id=customer.id, last_name="King")

# Iterate every customer without manual pagination
for customer in customers.iter_all_customers(store):
    ...
```

**`Customer`** fields: `id`, `first_name` (`str | None`), `last_name`
(`str | None`), `email` (`str | None`), `phone` (`str | None`), `tags`
(`list[str]`), `created_at`, `updated_at`.
**`CustomerPage`**: `customers`, `has_next_page`, `end_cursor`.

---

## Webhooks

```python
# your project's urls.py — exposes POST /shopify/webhooks/receive/
from django.urls import include, path
urlpatterns = [..., path("shopify/webhooks/", include("shopify_toolkit.webhooks.urls"))]
```

The receiver verifies `X-Shopify-Hmac-Sha256` against
`SHOPIFY_TOOLKIT_API_SECRET`, resolves the `ShopifyStore` from the
`X-Shopify-Shop-Domain` header, and saves a `WebhookEvent` row — `401` for a
bad/missing signature, `404` for an unknown/inactive store.

```python
from shopify_toolkit.webhooks import registry
from shopify_toolkit.webhooks.verify import verify_webhook

# Register a subscription — returns the new WebhookSubscription
registry.register_webhook(
    store, topic="ORDERS_CREATE", callback_url="https://my-app.example.com/shopify/webhooks/receive/"
)

# List existing subscriptions — returns list[WebhookSubscription]
registry.list_webhooks(store)

# Verify a signature manually — returns bool, never raises for a bad signature
verify_webhook(raw_request_body_bytes, request.headers.get("X-Shopify-Hmac-Sha256"))
```

**`WebhookSubscription`** fields: `id`, `topic`, `callback_url`, `created_at`.

### Processing received webhooks

The receiver only *saves* each incoming webhook as a `WebhookEvent` row —
it's on you to process them (e.g. from a periodic task or Celery worker).
`WebhookEvent` fields: `store` (FK to `ShopifyStore`), `topic`, `payload`
(the raw JSON body, as a dict), `received_at`, `processed` (bool, default
`False`), `processing_error` (blank by default).

```python
from shopify_toolkit.models import WebhookEvent

for event in WebhookEvent.objects.filter(store=store, processed=False):
    try:
        handle(event.topic, event.payload)  # your own logic
        event.processed = True
        event.save(update_fields=["processed"])
    except Exception as exc:
        event.processing_error = str(exc)
        event.save(update_fields=["processing_error"])
```

### Reacting to webhooks with a signal

Every successfully verified webhook also dispatches `webhook_received` —
listen for it from anywhere in your project instead of polling `WebhookEvent`:

```python
from django.dispatch import receiver
from shopify_toolkit.signals import webhook_received

@receiver(webhook_received)
def handle_webhook(sender, store, topic, payload, event, **kwargs):
    if topic == "orders/create":
        ...
```

---

## Bulk operations

For datasets too large for paginated GraphQL (100k+ records) — Shopify runs
your query as an async job and hands back a JSONL file when it's done:

```python
from shopify_toolkit.bulk_operations import services as bulk

# Start a bulk query — a raw GraphQL query string, no $variables. Only one
# bulk operation can run per store at a time.
operation = bulk.run_bulk_query(
    store, "{ products { edges { node { id title } } } }"
)

# Block until it finishes (call from a background task/worker, not a
# request/response cycle — this can take a while for large exports)
operation = bulk.wait_for_bulk_operation(store, poll_interval=2.0, timeout=300.0)

# Download and parse the JSONL result — a plain HTTPS GET to Shopify's
# temporary storage, not a GraphQL call. The url expires 7 days after completion.
rows = bulk.download_bulk_operation_result(operation)

# Or just check status without blocking
current = bulk.get_current_bulk_operation(store)
```

**`BulkOperation`** fields: `id`, `status` (`CREATED`/`RUNNING`/`CANCELING`/
`COMPLETED`/`FAILED`/`CANCELED`/`EXPIRED`), `error_code`, `object_count`,
`file_size`, `url`, `partial_data_url`.

---

## Testing your own code

Install with `pip install django-shopify-toolkit[testing]` for mock helpers
that save you from hand-rolling `responses` mocks for every test:

```python
from shopify_toolkit.testing import mock_shopify_api, mock_shopify_error

# as a context manager
def test_something(shopify_store):
    with mock_shopify_api(shopify_store, {"data": {"shop": {"name": "Test"}}}):
        ...  # code under test that calls shopify_toolkit

# or as a decorator
@mock_shopify_api(shopify_store, {"data": {"shop": {"name": "Test"}}})
def test_something_else():
    ...

# mock a GraphQL error response (raises ShopifyGraphQLError in the code under test)
@mock_shopify_error(shopify_store, "field not found")
def test_error_handling():
    ...
```

Both default to an empty success response (`{"data": {}}`) if you just need
to stub a call without asserting on its shape. For anything more elaborate
(multiple responses in sequence, asserting on request bodies), use
`responses` directly — these are convenience wrappers, not a replacement.

---

## Errors

Every function above raises a typed exception from `shopify_toolkit.exceptions`
instead of a raw `requests`/GraphQL error — `ShopifyGraphQLError` (transport-level
GraphQL errors), `ShopifyUserError` (mutation validation failures), `ShopifyRateLimitError`
(throttled), `ShopifyRequestError` (network failure or bad token exchange), `ShopifyStoreNotConfigured`
(a store with neither `access_token` nor `client_id`/`client_secret` set).

---

## The underlying GraphQL client

Every function above is a thin wrapper around `ShopifyGraphQLClient` — the
store-scoped GraphQL client with retry, rate-limit backoff, and connection
pooling built in (see "Concurrency & performance" below). You normally never
touch it directly; it's there if you need a raw query/mutation outside the
products/orders/customers/webhooks surface this package provides:

```python
from shopify_toolkit.client import ShopifyGraphQLClient

client = ShopifyGraphQLClient(store)
data = client.execute("query { shop { name } }")  # returns the "data" dict
```

---

## Optional: DRF API layer

If `djangorestframework` is installed, wire up store-scoped REST endpoints
wrapping the same services:

```python
# your project's urls.py
urlpatterns = [..., path("api/shopify/", include("shopify_toolkit.api.urls"))]
```

All scoped under `/api/shopify/stores/<store_pk>/`:

- `products/` — `GET` (list), `POST` (create)
- `products/<product_id>/` — `GET`, `PUT`/`PATCH`, `DELETE`
- `orders/` — `GET` (list)
- `orders/<order_id>/` — `GET`
- `orders/<fulfillment_order_id>/fulfill/` — `POST`
- `customers/` — `GET` (list), `POST` (create)
- `customers/<customer_id>/` — `GET`, `PUT`/`PATCH`

---

## Concurrency & performance

Verified with real concurrent load — Python threads, a real Postgres
database, mocked Shopify transport — not just unit tests:

| Scenario | Result |
|---|---|
| 200 concurrent calls across 10 stores | 0 errors, 0 cross-store leakage |
| Per-store connection pooling (`requests.Session` reused, keyed by shop domain) | Confirmed distinct per store, shared across calls to the same store |
| 50–80 concurrent requests racing one store's expired Client Credentials Grant token | **Exactly 1 real exchange, 0 errors** (Postgres) |
| 80 concurrent inbound webhook POSTs | 0 errors, 0 dropped/duplicated `WebhookEvent` rows |
| Sustained concurrent runs | No connection leaks |

**⚠️ The token-exchange race protection requires Postgres or MySQL.**
`SELECT ... FOR UPDATE` is a documented no-op on SQLite, so the same test
there showed the herd *not* collapsing (dozens of redundant exchanges) plus
intermittent `OperationalError: database is locked` — a SQLite limitation,
not a bug in this package. **Don't run a Client Credentials Grant store on
SQLite in production under real concurrent traffic** — SQLite is fine for
everything else here, including static-token stores and webhook ingestion.

One more thing worth knowing: rate-limit backoff (`SHOPIFY_TOOLKIT_MAX_BACKOFF_SECONDS`,
default 10s) blocks the calling thread (`time.sleep`) by design — under a
sync WSGI worker that ties up a process for the sleep duration. This package
has no async client; if you need one, wrap calls in your own background task
(Celery, etc.).

---

## License

MIT — see [LICENSE](LICENSE).
