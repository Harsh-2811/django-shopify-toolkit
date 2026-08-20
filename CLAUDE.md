# django-shopify-toolkit — Project Instructions

## What this is

A reusable, installable Django app that gives any Django project Shopify Admin
GraphQL integration out of the box — the same way `djangorestframework-simplejwt`
gives you JWT auth. A consumer project does:

```bash
pip install django-shopify-toolkit
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

...and gets working tables, an admin-registered `ShopifyStore` model, and a
Python API + REST endpoints for products, product images, orders, customers,
and webhooks. No other wiring required beyond settings variables documented in
the README.

This package is **multi-tenant**: one Django install can manage many Shopify
stores, each with its own encrypted access token. Never assume a single global
store or a single global token anywhere in the codebase.

---

## Core principles — follow these on every file you write

1. **Reusability first.** This is a library, not an app. Never hardcode a
   project-specific setting, model, or URL. Every configurable value goes
   through Django settings with a `SHOPIFY_TOOLKIT_` prefix and a sane default.
2. **No global state.** Every Shopify API call takes an explicit `ShopifyStore`
   instance and builds a request scoped to that store. Never cache a token or
   client at module level — that's how store A's data leaks into store B's
   request in a multi-tenant system.
3. **Fail loud on missing config**, fail quiet on expected API states. Missing
   `SHOPIFY_TOOLKIT_API_SECRET` should raise `ImproperlyConfigured` at startup,
   not fail silently later. A 404 from Shopify should return a clean typed
   exception, not a raw `requests` traceback.
4. **Migrations ship inside the package.** `shopify_toolkit/migrations/` is
   part of the installed package so `manage.py migrate` "just works" the
   moment the app is added to `INSTALLED_APPS`. Never ask the consumer to run
   `makemigrations` for this app's own models.
5. **Secrets are encrypted at rest.** Shopify access tokens are stored via
   `django-encrypted-model-fields`, never as plain `CharField`. Document the
   required `FIELD_ENCRYPTION_KEY` setting clearly.
6. **Webhook payloads are verified before they're trusted.** Every webhook view
   verifies the `X-Shopify-Hmac-Sha256` header via HMAC-SHA256 against
   `SHOPIFY_TOOLKIT_API_SECRET` before touching the payload. No exceptions.
7. **Rate-limit aware.** Shopify GraphQL uses cost-based throttling. The
   client reads `extensions.cost.throttleStatus` from every response and
   backs off / retries when `currentlyAvailable` gets low. Don't let this be
   an afterthought bolted on later — build it into `client.py` from the start.
8. **Typed, tested, documented.** Every public function has a docstring and a
   type hint. Every module (products, orders, customers, webhooks) has its own
   test file. No module is "done" without tests that mock the Shopify GraphQL
   response and assert on the parsed result.
9. **DRF is optional, not required.** Core logic (`client.py`, `models.py`,
   `products/services.py`, etc.) must work as a plain Python/Django library
   even if the consumer never touches DRF. DRF serializers/viewsets are an
   additive layer in `shopify_toolkit/api/`, not a dependency baked into core.
10. **Version discipline.** `pyproject.toml` version, `__version__` in
    `__init__.py`, and the git tag must always match exactly before any
    release — verify this in CI.

---

## Scope lock — GraphQL coverage (do not exceed this)

This package implements Shopify Admin GraphQL coverage for **exactly** these
areas — nothing else. Do not add collections, discounts, inventory,
fulfillment services, metafields, draft orders, or any other Shopify object
"while you're at it." If a future need shows up, it gets added in a separate
task, not bundled in here.

| Area | Operations to implement |
|---|---|
| Products | list products, get single product, create product, update/edit product, delete product |
| Product images | add image, remove image, reorder images, list images for a product |
| Orders | list orders, get single order, update order/fulfillment status |
| Customers | list customers, get single customer, create customer, update customer |
| Webhooks | register webhook subscription, list webhook subscriptions, receive + verify incoming webhook |

Every GraphQL query/mutation string written in `products/queries.py`,
`products/mutations.py`, `images/*`, `orders/*`, `customers/*`, and
`webhooks/registry.py` must map to one of the rows above. If Claude Code
finds itself writing a query for anything not in this table, it should stop
and ask rather than add it silently.

---

## Tech stack

- Django 4.2+ / 5.x, Python 3.10+
- `requests` for GraphQL calls (raw HTTP, no heavy Shopify SDK dependency)
- `djangorestframework` — optional extra (`pip install django-shopify-toolkit[drf]`)
- `django-encrypted-model-fields` for token encryption
- `pytest` + `pytest-django` + `responses` (mock HTTP) for tests
- `hatchling` as the build backend

---

## Package layout

```
django-shopify-toolkit/
├── pyproject.toml
├── README.md
├── LICENSE
├── CHANGELOG.md
├── .github/workflows/
│   ├── test.yml              # runs on every push/PR
│   └── publish.yml           # runs on GitHub Release
├── src/
│   └── shopify_toolkit/
│       ├── __init__.py       # __version__ lives here
│       ├── apps.py
│       ├── conf.py           # reads SHOPIFY_TOOLKIT_* settings, validates
│       ├── exceptions.py
│       ├── models.py         # ShopifyStore, WebhookEvent
│       ├── admin.py
│       ├── client.py         # ShopifyGraphQLClient — core, store-scoped
│       ├── migrations/
│       │   ├── __init__.py
│       │   └── 0001_initial.py
│       ├── products/
│       │   ├── __init__.py
│       │   ├── queries.py      # GraphQL query strings
│       │   ├── mutations.py    # GraphQL mutation strings
│       │   └── services.py     # Python functions consumers call
│       ├── images/
│       │   ├── queries.py
│       │   ├── mutations.py
│       │   └── services.py
│       ├── orders/
│       │   ├── queries.py
│       │   └── services.py
│       ├── customers/
│       │   ├── queries.py
│       │   └── services.py
│       ├── webhooks/
│       │   ├── verify.py       # HMAC verification
│       │   ├── views.py        # receiver endpoint
│       │   ├── registry.py     # register/list webhooks via GraphQL
│       │   └── urls.py
│       └── api/                 # optional DRF layer
│           ├── serializers.py
│           ├── viewsets.py
│           └── urls.py
└── tests/
    ├── conftest.py
    ├── test_client.py
    ├── test_models.py
    ├── products/test_services.py
    ├── orders/test_services.py
    ├── customers/test_services.py
    └── webhooks/test_verify.py
```

---

## Data models (exact fields to implement)

```python
class ShopifyStore(models.Model):
    shop_domain = models.CharField(max_length=255, unique=True)   # e.g. store.myshopify.com
    access_token = EncryptedCharField(max_length=255)
    api_version = models.CharField(max_length=10, default="2025-01")
    scopes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

class WebhookEvent(models.Model):
    store = models.ForeignKey(ShopifyStore, on_delete=models.CASCADE, related_name="webhook_events")
    topic = models.CharField(max_length=100)
    payload = models.JSONField()
    received_at = models.DateTimeField(auto_now_add=True)
    processed = models.BooleanField(default=False)
    processing_error = models.TextField(blank=True)
```

Both registered in `admin.py` with sensible `list_display` and `readonly_fields`
on tokens (never show the raw token in the admin list view).

> **Amendment (added after initial build, verified against shopify.dev):**
> Shopify custom apps created via the Dev Dashboard from **Jan 1, 2026**
> onward no longer expose a static `access_token` in the admin UI — only a
> Client ID/Secret, exchanged for a token that expires roughly every 24
> hours (apps created before that date are unaffected and keep working with
> a static token as originally specified above). `ShopifyStore` gained three
> fields to support this: `access_token_expires_at` (nullable datetime),
> `client_id` and `client_secret` (both `EncryptedCharField`, blank-able),
> and `access_token` itself became blank-able. A new `shopify_toolkit/auth.py`
> module resolves/exchanges/caches the right token per store — see its
> docstring. (Folded directly into `migrations/0001_initial.py` rather than
> a separate migration, since this was caught before any release — there
> are no consumers with 0001 already applied to migrate forward from.)
> Treat this amendment as part of the schema, not a deviation from it.

---

## Required settings (document all of these in README)

```python
# required
FIELD_ENCRYPTION_KEY = "..."                 # for encrypted token storage
SHOPIFY_TOOLKIT_API_SECRET = "..."           # app's API secret, for HMAC webhook verification

# optional, with defaults
SHOPIFY_TOOLKIT_API_VERSION = "2025-01"
SHOPIFY_TOOLKIT_MAX_RETRIES = 3
SHOPIFY_TOOLKIT_RATE_LIMIT_BUFFER = 100      # pause if throttle bucket below this
```

`conf.py` centralizes reading these with `getattr(settings, "...", default)` —
never read `django.conf.settings` directly from inside product/order/webhook
modules; always go through `conf.py`.

---

## Build order (do not skip ahead)

1. **Scaffold** — folder structure, `apps.py`, `pyproject.toml`, empty
   `__init__.py` with `__version__ = "0.1.0"`.
2. **Models + migration** — `ShopifyStore`, `WebhookEvent`, `0001_initial.py`,
   register in `admin.py`. Verify: spin up a throwaway Django test project,
   `pip install -e .`, add to `INSTALLED_APPS`, run `migrate`, confirm tables
   exist.
3. **`client.py`** — `ShopifyGraphQLClient`, constructed from a `ShopifyStore`
   instance. Handles auth header, POST to the versioned GraphQL endpoint,
   error parsing, and throttle-aware retry/backoff. Write `test_client.py`
   with `responses`-mocked HTTP before moving on.
4. **Products module** — list, get single product, create, update (edit),
   delete. Then **images** — add/remove/reorder product images. This is the
   largest module; get it fully tested before touching orders.
5. **Orders module** — list, get single order, update status/fulfillment as
   needed. Reuses `client.py` — no new HTTP logic.
6. **Customers module** — list, get, create/update.
7. **Webhooks module** — HMAC verification (`verify.py`), the receiving view
   (`views.py`), and a `registry.py` helper to register webhook subscriptions
   via GraphQL mutation. Test HMAC verification with a known payload + secret
   fixture. This module needs a public URL to test live delivery — use ngrok
   or similar, do this only after 1–6 are solid.
8. **Optional DRF layer** (`api/`) — serializers + viewsets wrapping the
   services from steps 4–6. Keep this decoupled: it imports from
   `products/services.py` etc., never the other way around.
9. **Tests pass, coverage checked** — `pytest --cov=shopify_toolkit`.
10. **Local packaging test** — `python -m build`, fresh venv, install the
    wheel, confirm `import shopify_toolkit` and a migrate-in-a-throwaway-project
    smoke test both pass.
11. **TestPyPI dry run**, then real PyPI release via the GitHub Actions flow
    in `.github/workflows/publish.yml` (trusted publisher / OIDC, triggered on
    GitHub Release).

Do not jump to step 7 or 8 before 4–6 are tested and working — webhooks and
the DRF layer are both add-ons over a proven core.

---

## Testing requirements per module

Every module needs, at minimum:
- One test that mocks a successful Shopify GraphQL response and asserts the
  service function returns correctly parsed data.
- One test that mocks a Shopify GraphQL **error** response (`errors` array)
  and asserts the correct typed exception is raised.
- One test asserting the store's token is used and no other store's data leaks
  in (construct two `ShopifyStore` fixtures, confirm requests are scoped).

`webhooks/test_verify.py` specifically needs:
- A valid HMAC signature → `verify_webhook()` returns `True`.
- A tampered payload with the original signature → returns `False`.

---

## Definition of done for the whole package

- [ ] `pip install -e .` in a fresh venv, add to `INSTALLED_APPS`, `migrate`
      creates `shopify_toolkit_shopifystore` and `shopify_toolkit_webhookevent`
      tables with no errors.
- [ ] All modules (products, images, orders, customers, webhooks) have
      services + tests, all green under `pytest`.
- [ ] `twine check dist/*` passes with no warnings after `python -m build`.
- [ ] Fresh venv, install from the built wheel (not editable), import and
      basic smoke test succeed.
- [ ] README documents: install steps, required settings, a full usage
      example for products, and how to register/verify a webhook.
- [ ] TestPyPI install works end to end before the real release.

Refer to `BUILD_PROMPT.md` in this repo for the exact task-by-task prompt
sequence to give Claude Code when starting a session.
