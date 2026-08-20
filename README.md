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

---

## Requirements

* Python 3.10, 3.11, or 3.12
* Django 4.2 or 5.x

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

Add the following to your project's `.env` file:

```env
# Required: 32-byte base64 key used to encrypt store access tokens in the database
FIELD_ENCRYPTION_KEY="your-32-byte-base64-encryption-key"

# Optional: Default Shopify App credentials
SHOPIFY_API_VERSION="2026-01"
SHOPIFY_CLIENT_ID="your_shopify_client_id"
SHOPIFY_CLIENT_SECRET="your_shopify_client_secret"
```

> **Tip: Generate a valid 32-byte key in 1 command:**
> ```bash
> python -c "import os, base64; print(base64.b64encode(os.urandom(32)).decode())"
> ```

---

### 2. Configure `settings.py`

Add `shopify_toolkit` to `INSTALLED_APPS` and define the configuration dictionary:

```python
import os

INSTALLED_APPS = [
    ...,
    "shopify_toolkit",
]

# Key for encrypting access tokens (reads from .env)
FIELD_ENCRYPTION_KEY = os.environ.get("FIELD_ENCRYPTION_KEY", "")

SHOPIFY_TOOLKIT = {
    "API_VERSION": os.environ.get("SHOPIFY_API_VERSION", "2026-01"),
    "APP_TYPE": "custom",  # "custom" (private app) or "public" (OAuth)
    "CLIENT_ID": os.environ.get("SHOPIFY_CLIENT_ID", ""),
    "CLIENT_SECRET": os.environ.get("SHOPIFY_CLIENT_SECRET", ""),
    "SCOPES": ["read_products", "write_products", "read_orders", "write_orders", "read_customers"],
}
```

---

### 3. Run Migrations

```bash
python manage.py migrate
```

---

## Usage Guide

### 1. Connecting a Shopify Store

```python
from shopify_toolkit.models import ShopifyStore

store, created = ShopifyStore.objects.get_or_create(
    shop_domain="your-store.myshopify.com",
    defaults={
        "access_token": "shpat_xxxxxxxxxxxxxxxxxxxxx",
        "api_version": "2026-01",
        "is_active": True,
    }
)
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

## License

MIT License.
