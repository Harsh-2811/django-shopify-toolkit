# django-shopify-toolkit

A reusable, installable Django app that gives any Django project Shopify Admin
GraphQL integration out of the box — working tables, an admin-registered
`ShopifyStore` model, and a Python API (plus optional REST endpoints) for
**products**, **product images**, **orders**, **customers**, and **webhooks**.

The package is **multi-tenant**: one Django install can manage many Shopify
stores, each with its own encrypted credentials. Every function takes an
explicit `ShopifyStore` — there's no global/default store.

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
SHOPIFY_TOOLKIT_API_VERSION = "2025-01"      # default Shopify Admin API version
SHOPIFY_TOOLKIT_MAX_RETRIES = 3              # retries for transient network errors
SHOPIFY_TOOLKIT_RATE_LIMIT_BUFFER = 100      # pause outgoing requests once the
                                              # cost throttle bucket drops below this
```

`SHOPIFY_TOOLKIT_API_SECRET` is only validated the first time it's actually
needed (e.g. verifying a webhook) — you'll get a clear `ImproperlyConfigured`
the moment you do, not at import time.

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
```

`create_product`/`update_product` accept any `ProductInput` field, in either
snake_case (`product_type=`) or Shopify's native camelCase (`productType=`)
— snake_case is converted automatically.

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
```

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
```

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

---

## Errors

Every function above raises a typed exception from `shopify_toolkit.exceptions`
instead of a raw `requests`/GraphQL error — `ShopifyGraphQLError` (transport-level
GraphQL errors), `ShopifyUserError` (mutation validation failures), `ShopifyRateLimitError`
(throttled), `ShopifyRequestError` (network failure or bad token exchange), `ShopifyStoreNotConfigured`
(a store with neither `access_token` nor `client_id`/`client_secret` set).

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

Verified with real concurrent load (Python threads, real Postgres, mocked
Shopify transport — not just unit tests):

- **Multi-tenant isolation holds under concurrency.** 200 concurrent calls
  across 10 stores: 0 errors, 0 cross-store header/token leakage.
- **Per-store connection pooling.** Each `ShopifyStore` gets one reused
  `requests.Session` (keyed by shop domain), not a fresh session per call —
  confirmed distinct per store, shared across calls to the same store.
- **Client Credentials Grant token refresh is race-safe — on a real
  database.** When a store's token expires, concurrent requests serialize
  on a row lock (`SELECT ... FOR UPDATE`) instead of each independently
  hitting Shopify's OAuth endpoint. Verified at 50–80 concurrent requests
  racing one store's expired token: **exactly 1 real exchange, 0 errors**
  on Postgres.
  **This requires Postgres or MySQL.** SQLite has no real row-locking
  (`SELECT ... FOR UPDATE` is a documented no-op there), so the same test
  on SQLite showed the herd *not* collapsing (dozens of redundant
  exchanges) and intermittent `OperationalError: database is locked`
  failures under the write contention — a SQLite limitation, not a bug in
  this package. **Don't run a Client Credentials Grant store on SQLite in
  production under real concurrent traffic.** SQLite is fine for
  everything else this package does (including moderate concurrent
  webhook ingestion and static-token stores), just not this one lock path.
- **Webhook receiver handles concurrent inbound load correctly.** 80
  concurrent webhook POSTs: 0 errors, 0 dropped or duplicated
  `WebhookEvent` rows.
- **No connection leaks** across sustained concurrent runs.
- Backoff sleeps (`SHOPIFY_TOOLKIT_MAX_BACKOFF_SECONDS`, default 10s) are
  blocking (`time.sleep`) on the calling thread by design — under a sync
  WSGI worker that ties up a worker process for the sleep duration. This
  package doesn't ship an async client; if you need one, wrap calls in
  your own background task (Celery, etc.) rather than expecting this
  client to not block.

---

## License

MIT — see [LICENSE](LICENSE).
