# django-shopify-toolkit

[![PyPI Version](https://img.shields.io/pypi/v/django-shopify-toolkit?color=blue&label=pypi)](https://pypi.org/project/django-shopify-toolkit/)
[![Python Versions](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12-blue)](https://python.org)
[![Django Versions](https://img.shields.io/badge/django-4.2%20%7C%205.x-green)](https://djangoproject.com)
[![License: MIT](https://img.shields.io/badge/license-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A reusable, installable Django app that gives any Django project Shopify Admin GraphQL integration out of the box — working database tables, an admin-registered `ShopifyStore` model with encrypted credentials, and a Python API (plus optional REST endpoints) for products, staged image uploads, product variants and options, orders, customers, webhooks, and bulk data exports.

The package is multi-tenant: one Django install can manage many Shopify stores, each with its own encrypted credentials. Every service function takes an explicit `ShopifyStore` — there is no global or default store.

---

## Key Features

* **Modern GraphQL (2024-07 through 2026-07+)**: Full compatibility with Shopify's latest GraphQL APIs (`productVariantsBulkCreate`, `stagedUploadsCreate`, `fulfillmentCreateV2`).
* **Multi-Tenant & Encrypted**: Stores encrypted access tokens and API secrets per tenant using `django-encrypted-model-fields`.
* **Fail-Safe Sanitization**: Automatically handles currency symbols (`$`, `€`), comma decimals, non-numeric strings, and weight unit normalizations (`kg`, `lbs`, `oz`, `grams`).
* **Staged Image Uploads**: Direct binary file uploads to Shopify CDN via Staged Uploads.
* **Webhook Receiver & Signal Dispatcher**: Built-in HMAC SHA-256 verification and `webhook_received` Django signals.
* **Asynchronous Bulk Operations**: Query hundreds of thousands of records via Shopify's JSONL bulk export pipeline.
* **Typed Exceptions**: Catch clean typed exceptions (`ShopifyGraphQLError`, `ShopifyUserError`, `ShopifyRateLimitError`, `ShopifyStoreNotConfigured`) instead of raw HTTP errors.
* **Multi-Database**: PostgreSQL/MySQL/SQLite by default (Postgres is what this package's own CI runs against); MongoDB and a dedicated PostgreSQL schema are both supported as opt-in extras — see "Database support" below.

---

## Requirements

* Python 3.10, 3.11, or 3.12
* Django 4.2 or 5.x

---

## Database support

This package works against a normal relational database out of the box — nothing below is
required reading unless you need one of these specifically:

| Backend / setup | What it needs | Status |
|---|---|---|
| PostgreSQL | Nothing — the default. | Fully tested; this package's own CI runs against it. |
| MySQL | Nothing — the default. | Expected to work (same relational path as Postgres); not independently verified in this package's own CI. |
| SQLite | Nothing — the default. | Works, but Client Credentials Grant token exchange loses its concurrency-safety guarantee (`SELECT ... FOR UPDATE` is a no-op) — fine for local dev, not recommended for production under real concurrent load. |
| MongoDB | `pip install django-shopify-toolkit[mongodb]` + two settings | Supported, verified end-to-end against a real MongoDB instance. Same Client Credentials Grant caveat as SQLite. See "Running on MongoDB" below. |
| Dedicated PostgreSQL schema for this package's own tables | One setting, fresh installs only | Supported, verified end-to-end against real Postgres. See "Using a dedicated PostgreSQL schema" below. |
| Schema-*per-tenant* (e.g. via [`django-tenants`](https://pypi.org/project/django-tenants/)) | Not this package's own feature | This package's models are schema-agnostic by design and should work as a `TENANT_APPS` entry unmodified, but that specific path hasn't had its own end-to-end verification yet — see `MULTI_DB_SUPPORT_PLAN.md` in this repo. |

---

## Installation

```bash
pip install django-shopify-toolkit

# With optional Django REST Framework serializers and viewsets
pip install django-shopify-toolkit[drf]

# With test helpers for your own test suite
pip install django-shopify-toolkit[testing]
```

---

## Quick Start

### 1. Environment Variables (`.env`)

Two secrets are process-wide and must never live in the database or in source control — keep
them in your `.env`/secrets manager. Nothing else needs to come from env; per-store credentials
(access token, client ID/secret, API version, scopes) live on the `ShopifyStore` model instead
— see "Connecting a Shopify store" and "Multiple stores" below for why.

```env
# Required: encrypts ShopifyStore's access_token/client_id/client_secret columns at rest.
# Keeping this OUTSIDE the database is the actual security boundary — a DB-only leak (backup,
# SQL injection) then only exposes ciphertext, not usable tokens.
FIELD_ENCRYPTION_KEY="your-32-byte-base64-encryption-key"

# Only required if you use the webhook receiver (nothing reads this otherwise, checked lazily
# on the first incoming webhook — not required just to install the package). Verifies the
# X-Shopify-Hmac-Sha256 header. One value for the whole app, not per-store — that's how Shopify
# webhook signing actually works for a single app's subscriptions.
SHOPIFY_TOOLKIT_API_SECRET="your_app_webhook_secret"
```

> **Tip: Generate a valid 32-byte key in 1 command:**
> ```bash
> python -c "import os, base64; print(base64.b64encode(os.urandom(32)).decode())"
> ```

**Set `FIELD_ENCRYPTION_KEY` correctly before creating your first `ShopifyStore` row.** Changing
or losing it afterward — without rotating via the list form (see "Key rotation" below) — makes
every already-encrypted value permanently undecryptable. There is no recovery path once that
happens; this is inherent to how Fernet encryption works, not something this package can guard
against after the fact.

---

### 2. Configure `settings.py`

Add `shopify_toolkit` to `INSTALLED_APPS` and wire up the env var(s) above. Every
`SHOPIFY_TOOLKIT_*` setting is a flat top-level Django setting, not a nested dict — see the
"Settings reference" section below for the complete list.

```python
import os

INSTALLED_APPS = [
    ...,
    "shopify_toolkit",
]

# os.environ[...], not .get(..., "") — fail at startup with a clear error pointing at the
# missing var, rather than a less obvious error several layers down inside the encryption
# library (which does still fail on an empty key, just less legibly).
FIELD_ENCRYPTION_KEY = os.environ["FIELD_ENCRYPTION_KEY"]
SHOPIFY_TOOLKIT_API_SECRET = os.environ.get("SHOPIFY_TOOLKIT_API_SECRET", "")  # only if using webhooks
```

**Key rotation:** `FIELD_ENCRYPTION_KEY` also accepts a list — `django-encrypted-model-fields`
wraps it in `cryptography.fernet.MultiFernet`, which tries every key when *decrypting* (so
already-encrypted rows keep working) but always uses the *first* key when *encrypting* (so new
writes move to the new key immediately):
```python
FIELD_ENCRYPTION_KEY = [
    "new-key-goes-first",   # used for all new writes from now on
    "old-key-goes-second",  # kept only so existing rows still decrypt
]
```
Existing rows aren't automatically rewritten under the new key — that only happens the next time
each row is saved. Set this key correctly before the first `ShopifyStore` is ever created:
losing it, or replacing it outright instead of rotating, makes every row encrypted under the old
key permanently undecryptable.

---

### 3. Run Migrations

```bash
python manage.py migrate
```

---

## Settings Reference

All of these are optional except `SHOPIFY_TOOLKIT_API_SECRET` (only required if you use the
webhook receiver). Every one is read in exactly one place (`shopify_toolkit/conf.py`) — nothing
in this package reads `django.conf.settings` directly anywhere else.

| Setting | Default | What it controls |
|---|---|---|
| `SHOPIFY_TOOLKIT_API_SECRET` | *(none — required for webhooks)* | HMAC secret used to verify incoming webhook signatures. |
| `SHOPIFY_TOOLKIT_API_VERSION` | `"2026-07"` | Default Shopify Admin API version for stores that don't set their own `api_version`. Shopify supports each version ~12 months — check this isn't stale. |
| `SHOPIFY_TOOLKIT_MAX_RETRIES` | `3` | Retry attempts for transient network errors in `ShopifyGraphQLClient`. |
| `SHOPIFY_TOOLKIT_RATE_LIMIT_BUFFER` | `100` | Pause outgoing requests once Shopify's cost-throttle bucket drops below this. |
| `SHOPIFY_TOOLKIT_MAX_BACKOFF_SECONDS` | `10` | Cap on any single blocking sleep (retry or rate-limit backoff), so a slow Shopify can't tie up a sync worker indefinitely. |
| `SHOPIFY_TOOLKIT_REQUEST_TIMEOUT` | `30` | Per-request timeout (seconds) for GraphQL calls and token exchanges. |
| `SHOPIFY_TOOLKIT_MAX_POOLED_SESSIONS` | `500` | Max distinct store domains kept in the HTTP session pool at once; least-recently-used sessions are evicted and closed beyond this. |
| `SHOPIFY_TOOLKIT_DEFAULT_AUTO_FIELD` | `"django.db.models.BigAutoField"` | Primary-key field class for `ShopifyStore`/`WebhookEvent`. Only override this on MongoDB — see "Running on MongoDB" below. |

---

## Usage Guide

### 1. Connecting a Shopify Store

Two ways to authenticate a store — set whichever applies to that store, not both:

**Static token** (pre-2026 custom apps — a token shown once in the Shopify admin, never expires):
```python
from shopify_toolkit.models import ShopifyStore

store, created = ShopifyStore.objects.update_or_create(
    shop_domain="your-store.myshopify.com",
    defaults={
        "access_token": "shpat_xxxxxxxxxxxxxxxxxxxxx",
        "api_version": "2026-07",
        "is_active": True,
    }
)
```

**Client ID/Secret** (Dev Dashboard apps, 2026+ — no static token is shown at all; the package
exchanges these for a real access token on first use and refreshes it automatically roughly
every 24 hours, caching the result on this same row):
```python
store, created = ShopifyStore.objects.update_or_create(
    shop_domain="your-store.myshopify.com",
    defaults={
        "client_id": "your_app_client_id",
        "client_secret": "your_app_client_secret",
        "api_version": "2026-07",
        "is_active": True,
    }
)
```

`update_or_create`, not `get_or_create` — deliberately. `get_or_create` only applies `defaults`
when creating a *new* row; if `shop_domain` already exists it just returns that row untouched,
silently ignoring any updated credentials you passed. That's the wrong behavior for onboarding
code that might run more than once (a re-run install flow, a retried signup) with rotated or
corrected credentials — `update_or_create` applies `defaults` on match too, so re-running this
safely refreshes the row instead of either crashing (bare `.create()`, which would hit
`shop_domain`'s unique constraint) or silently doing nothing (`get_or_create`).

`access_token`, `client_id`, and `client_secret` are all encrypted at rest (see the
`FIELD_ENCRYPTION_KEY` note above) — verified by reading the raw stored values directly; the
ORM decrypts transparently, so nothing about reading `store.access_token` in your own code
changes.

---

### 1a. Multiple stores

There's no per-store configuration in settings.py and no `SHOPIFY_STORES` list — multi-tenancy
is just "more than one `ShopifyStore` row," since every function in this package takes an
explicit `store` argument (there is no global/default store, see the intro above). Two examples
already built into the package show the pattern — **resolve which store a request is for, then
pass that instance down**:

* The webhook receiver resolves the store from the `X-Shopify-Shop-Domain` header automatically
  (see "Webhooks" below) — nothing to do for this one.
* The optional DRF layer resolves the store from the URL: every endpoint is nested under
  `/stores/<store_pk>/...` (see "Optional: DRF API layer" below).

For your own code (management commands, views, scheduled jobs), do the same — resolve the store
from whatever your app already knows, then call any service function with it:

```python
# e.g. a nightly sync across every active store
for store in ShopifyStore.objects.filter(is_active=True):
    for product in products.iter_all_products(store):
        ...
```

---

### 2. Products & Staged Image Uploads

```python
from shopify_toolkit.products import services as products
from shopify_toolkit.images import services as images

# Create a Product
product = products.create_product(
    store,
    title="Nimbus Running Shoes",
    vendor="Apex Athletics",
    status="ACTIVE",
    description_html="<p>Lightweight high-performance running shoes.</p>"
)

# Upload a Local Image File directly to Shopify CDN
with open("shoe_photo.jpg", "rb") as file_obj:
    media = images.upload_product_image_file(
        store,
        product_id=product.id,
        file_source=file_obj,
        filename="shoe_photo.jpg",
        alt_text="Nimbus Running Shoes - Side View"
    )

# Or attach an image from a public URL
image = images.add_product_image(
    store,
    product_id=product.id,
    src="https://images.unsplash.com/photo-1542291026-7eec264c27ff",
    alt_text="Nimbus Red"
)

# List Products (paginated)
page = products.list_products(store, first=20)
for prod in page.products:
    print(prod.title, len(prod.variants), len(prod.images))
```

---

### 3. Product Options & Variants

```python
# 1. Create Options (e.g. Size, Color)
option = products.create_product_option(
    store,
    product_id=product.id,
    name="Size",
    values=["US 9", "US 10", "US 11"]
)

# 2. Create Variant with Price, SKU, Weight, and Image attachment
variant = products.create_product_variant(
    store,
    product_id=product.id,
    price="139.99",
    compare_at_price="179.99",
    sku="NIMBUS-RED-10",
    weight=0.75,
    weight_unit="lbs",
    media_id=media.id,
    option_values=[{"optionName": "Size", "name": "US 10"}]
)

# 3. Update Variant
products.update_product_variant(
    store,
    product_id=product.id,
    variant_id=variant.id,
    price="129.99",
    sku="NIMBUS-RED-10-SALE"
)

# 4. List Variants
variants = products.list_product_variants(store, product.id)
```

---

### 4. Orders & Fulfillments

```python
from shopify_toolkit.orders import services as orders

# List Orders
orders_page = orders.list_orders(store, first=25)

# Get Single Order
order = orders.get_order(store, "gid://shopify/Order/123456789")

# Fulfill an Order via FulfillmentOrder
orders.update_fulfillment_status(
    store,
    fulfillment_order_id="gid://shopify/FulfillmentOrder/987654321",
    tracking_number="1Z9999999999999999",
    tracking_company="UPS",
    notify_customer=True
)

# Iterate over all orders across pages
for order in orders.iter_all_orders(store):
    print(order.name, order.total_price, order.fulfillment_status)
```

---

### 5. Customers

```python
from shopify_toolkit.customers import services as customers

# Create Customer
customer = customers.create_customer(
    store,
    first_name="Ada",
    last_name="Lovelace",
    email="ada@example.com",
    phone="+1234567890"
)

# List Customers
cust_page = customers.list_customers(store, first=30)

# Filter with Shopify's search syntax (https://shopify.dev/docs/api/usage/search-syntax).
# Every list_* and iter_all_* function (products, orders, customers) accepts query=.
vips = customers.list_customers(store, query="tag:vip")
for order in orders.iter_all_orders(store, query="financial_status:paid created_at:>=2026-01-01"):
    ...

# Delete Customers (Shopify refuses customers with orders -> ShopifyUserError)
customers.delete_customer(store, "gid://shopify/Customer/123")
```

---

### 6. Webhooks & Signal Handling

```python
# urls.py - exposes POST /shopify/webhooks/receive/
from django.urls import include, path

urlpatterns = [
    ...,
    path("shopify/webhooks/", include("shopify_toolkit.webhooks.urls")),
]
```

Incoming webhooks are automatically verified using HMAC SHA-256 and saved as `WebhookEvent` models. You can also react to webhooks anywhere in your project using Django signals:

```python
from django.dispatch import receiver
from shopify_toolkit.signals import webhook_received

@receiver(webhook_received)
def on_order_created(sender, store, topic, payload, event, **kwargs):
    if topic == "orders/create":
        order_id = payload.get("id")
        print(f"New order received for {store.shop_domain}: {order_id}")
```

---

### 7. Asynchronous Bulk Operations

For datasets with tens of thousands of records, run Shopify Bulk Operations:

```python
from shopify_toolkit.bulk_operations import services as bulk

# Run asynchronous bulk query
operation = bulk.run_bulk_query(
    store,
    query="{ products { edges { node { id title variants { edges { node { id sku price } } } } } } }"
)

# Wait for Shopify to complete the job and download JSONL results
completed_op = bulk.wait_for_bulk_operation(store, poll_interval=2.0, timeout=300.0)
records = bulk.download_bulk_operation_result(completed_op)
```

---

### 8. Testing Your Code

```python
from shopify_toolkit.testing import mock_shopify_api, mock_shopify_error

def test_product_query(shopify_store):
    with mock_shopify_api(shopify_store, {"data": {"products": {"edges": []}}}):
        # Code under test
        ...

def test_api_error_handling(shopify_store):
    with mock_shopify_error(shopify_store, "Shopify API Throttled"):
        # Code under test raises ShopifyGraphQLError
        ...
```

---

### 9. Running on MongoDB (optional)

By default this package targets a relational database (Postgres/MySQL/SQLite) with an
integer `BigAutoField` primary key on `ShopifyStore`/`WebhookEvent`. MongoDB doesn't support
`AutoField`/`BigAutoField` as a primary key at all, so running this app on Mongo needs two
extra steps beyond a normal install — see `MULTI_DB_SUPPORT_PLAN.md` in this repo for the full
research and rationale behind this.

```bash
pip install django-shopify-toolkit[mongodb]
```

```python
# settings.py

# 1. Point this app's primary key at MongoDB's ObjectId type instead of the relational default.
#    This only affects shopify_toolkit's own models — it does not touch Django's project-wide
#    DEFAULT_AUTO_FIELD, so the rest of your project can stay on a different backend/PK type.
SHOPIFY_TOOLKIT_DEFAULT_AUTO_FIELD = "django_mongodb_backend.fields.ObjectIdAutoField"

# 2. Point this app at a separate migration history built for that PK type — the normal
#    migrations/ history is frozen with BigAutoField and can't be replayed against Mongo.
MIGRATION_MODULES = {
    "shopify_toolkit": "shopify_toolkit.migrations_mongodb",
}
```

**Known limitation:** the row-level locking that protects Client Credentials Grant token
exchange from concurrent duplicate requests (`SELECT ... FOR UPDATE`) only runs on backends that
support it — currently Postgres and MySQL. On MongoDB (same as SQLite) it's skipped entirely;
the code still re-checks for an already-refreshed token before exchanging, so this doesn't cause
incorrect behavior, just a small chance of two near-simultaneous requests each independently
hitting Shopify's OAuth endpoint under heavy concurrent load. If you're running Client
Credentials Grant stores on MongoDB under real concurrent traffic, be aware of this — it is not
the same guarantee Postgres/MySQL get.

This path is less exercised than the Postgres path this package's own CI runs against —
verify it against a real MongoDB instance before relying on it in production.

---

### 10. Using a dedicated PostgreSQL schema (optional)

By default `ShopifyStore`/`WebhookEvent` land in whatever schema your database connection
resolves unqualified table names to (`public`, almost always). If you'd rather keep this
package's tables in their own schema — separate from the rest of your project's tables, for
cleaner management — set `SHOPIFY_TOOLKIT_DB_SCHEMA`:

```python
# settings.py
SHOPIFY_TOOLKIT_DB_SCHEMA = "shopify_data"
```

The schema itself is created automatically (`CREATE SCHEMA IF NOT EXISTS`) as part of running
`migrate` — nothing to do there.

**Fresh installs only — set this before the very first `migrate` on a new project.** This isn't
just an unverified caveat: tested directly, including trying to make an upgrade path work, and
it genuinely doesn't. Setting `SHOPIFY_TOOLKIT_DB_SCHEMA` on a project that has already run
`migrate` and then running `migrate` again does nothing — Django only knows "this migration is
already applied," not what it would do differently now, so it's skipped. Forcing it via
`manage.py migrate shopify_toolkit 0001` (unapply) and then `migrate` again to reapply doesn't
work either — the *reverse* operation also reads the migration file's *current* (now
schema-set) content and errors trying to move tables out of a schema they were never actually
in. If you have an existing install and want to move into a dedicated schema, do it directly and
manually — a one-time `CREATE SCHEMA IF NOT EXISTS shopify_data;` followed by
`ALTER TABLE shopify_toolkit_shopifystore SET SCHEMA shopify_data;` (and the same for
`shopify_toolkit_webhookevent`) — not by flipping this setting.

**PostgreSQL only** — MySQL has no equivalent namespace-within-a-database concept, and SQLite
has nothing like it either; don't set this on those backends.

This is different from *schema-per-tenant* multi-tenancy (one schema per client, e.g. via
[`django-tenants`](https://pypi.org/project/django-tenants/)) — this setting gives the whole
package **one** dedicated schema, host-wide, not one schema per `ShopifyStore`. If you need
true per-tenant schema isolation, `django-tenants` is the right tool for that — this package's
models are schema-agnostic (no raw SQL, no hardcoded table/schema names) and were designed to
work as a `TENANT_APPS` entry unmodified, though that specific path is still pending its own
end-to-end verification — see `MULTI_DB_SUPPORT_PLAN.md`.

---

### 11. Optional: DRF API layer

`pip install django-shopify-toolkit[drf]` gets you REST endpoints wrapping the products/orders/
customers services above, active only if `djangorestframework` is installed. Every endpoint is
nested under a store, matching the multi-store pattern above:

```python
# urls.py
from django.urls import include, path

urlpatterns = [
    ...,
    path("api/", include("shopify_toolkit.api.urls")),
]
```

```
GET/POST   /api/stores/<store_pk>/products/
GET/PUT/PATCH/DELETE  /api/stores/<store_pk>/products/<pk>/
GET        /api/stores/<store_pk>/orders/
GET        /api/stores/<store_pk>/orders/<pk>/
POST       /api/stores/<store_pk>/orders/<pk>/fulfill/
GET/POST   /api/stores/<store_pk>/customers/
GET/PUT/PATCH/DELETE  /api/stores/<store_pk>/customers/<pk>/
```

Every list endpoint accepts `?first=`, `?after=` (cursor), and `?query=` (Shopify search syntax,
e.g. `/api/stores/1/orders/?query=financial_status:paid`).

**These viewsets ship with no `authentication_classes`/`permission_classes` set — they inherit
whatever `DEFAULT_AUTHENTICATION_CLASSES`/`DEFAULT_PERMISSION_CLASSES` your project's own
`REST_FRAMEWORK` setting defines, or DRF's own defaults (`AllowAny`) if you haven't set any.**
That means these endpoints are open by default — set your project's `REST_FRAMEWORK` permission
classes (or add authentication/permission classes to a subclass of these viewsets) before
exposing them publicly.

---

## License

MIT License.
