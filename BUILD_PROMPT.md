# BUILD_PROMPT.md — task-by-task prompts for Claude Code

Two ways to use this file:

- **Full run (Prompt X)** — one long prompt that takes Claude Code through
  the entire build in a single session, stage by stage, self-checking as it
  goes. Use this if you want to let it run end to end.
- **Step by step (Prompts 0–10)** — the same work broken into individual
  prompts, useful if you'd rather review and approve after each stage.

Both assume `CLAUDE.md` is present in the repo root (Claude Code auto-loads
it as context).

---

## Prompt X — Full end-to-end build (single session)

```
Read CLAUDE.md in this repo fully before writing anything, including the
"Scope lock" section — do not implement any Shopify GraphQL query or
mutation outside the exact list in that table (products, product images,
orders, customers, webhooks — nothing else, no collections/discounts/
inventory/metafields/draft orders).

Build the entire django-shopify-toolkit package end to end in this session,
following the "Build order" section of CLAUDE.md stage by stage, in order:

1. Scaffold the full folder structure, pyproject.toml, apps.py, LICENSE,
   .gitignore.
2. models.py (ShopifyStore, WebhookEvent exactly as specified), the initial
   migration, admin.py, conf.py.
3. client.py — the store-scoped GraphQL client with retry + rate-limit
   backoff, plus exceptions.py.
4. Products + images modules (list, get single, create, edit/update,
   delete, image add/remove/reorder) — queries, mutations, services.
5. Orders module (list, get single, update status/fulfillment) — reusing
   client.py.
6. Customers module (list, get, create, update).
7. Webhooks module — HMAC verification, receiver view, registration/list
   service, urls.py.
8. Optional DRF layer under api/ (serializers, viewsets, urls) that only
   imports from the services modules and degrades cleanly if DRF isn't
   installed.

For every module, write the tests specified in "Testing requirements per
module" in CLAUDE.md (mocked success, mocked GraphQL error, store-isolation
test) using the responses library — do not move to the next stage until
that stage's tests are written and passing.

After stage 8, do the packaging verification yourself:
- pytest --cov=shopify_toolkit --cov-report=term-missing
- python -m build
- twine check dist/*
- install the built wheel into a fresh venv and confirm import
  shopify_toolkit works

Then write .github/workflows/test.yml and .github/workflows/publish.yml
(trusted publisher OIDC, triggered on GitHub Release, id-token: write scoped
to the publish job only) and a test-publish.yml targeting TestPyPI.

Finally write the full README.md (install steps, all settings, a complete
products usage example, a complete webhook registration + verification
example).

As you finish each numbered stage, give me a short status line (what's
done, what's tested, what's not yet covered) before moving to the next
stage — don't wait for my confirmation to continue, just keep going through
all 8 stages plus packaging, CI, and README in this same session unless
something in CLAUDE.md is ambiguous enough that continuing would risk
wrong architecture — in that case stop and ask.

At the very end, go through the "Definition of done" checklist in
CLAUDE.md item by item and tell me honestly which boxes are checked and
which aren't.
```

---

## Prompt 0 — Scaffold

```
Read CLAUDE.md in this repo. Scaffold the full folder structure described
under "Package layout" — empty files are fine for now except:
- pyproject.toml, fully filled in (hatchling backend, package name
  django-shopify-toolkit, Python 3.10+, Django 4.2+ as a dependency,
  optional [drf] extra for djangorestframework, dev extras for
  pytest/pytest-django/responses)
- src/shopify_toolkit/__init__.py with __version__ = "0.1.0"
- src/shopify_toolkit/apps.py with a proper AppConfig
- .gitignore for a Python/Django project
- LICENSE (MIT)
- an empty README.md with just the project title for now

After scaffolding, show me the pyproject.toml and apps.py so I can confirm
before you continue.
```

---

## Prompt 1 — Models + migration + admin

```
Implement models.py exactly as specified in CLAUDE.md under "Data models":
ShopifyStore and WebhookEvent. Use EncryptedCharField from
django-encrypted-model-fields for access_token. Generate the initial
migration by hand (0001_initial.py) matching these models exactly — don't
rely on makemigrations since there's no Django project here yet.

Register both models in admin.py. For ShopifyStore, exclude access_token
from list_display and make it read-only in the detail view so raw tokens
are never shown in a list.

Then write conf.py implementing the settings-reading pattern from CLAUDE.md
("Required settings" section) — including raising
django.core.exceptions.ImproperlyConfigured if SHOPIFY_TOOLKIT_API_SECRET
is missing when it's actually needed (not at import time, at first use).

After this, tell me the exact steps to spin up a throwaway Django test
project, install this package with pip install -e ., add it to
INSTALLED_APPS, and run migrate to confirm the tables get created. I want
to run that verification myself before you continue to the next prompt.
```

---

## Prompt 2 — GraphQL client core

```
Implement client.py: ShopifyGraphQLClient per the spec in CLAUDE.md
principle #2 and #7 (store-scoped, no global state, rate-limit aware).

Requirements:
- Constructor takes a ShopifyStore instance, builds the versioned GraphQL
  endpoint from store.shop_domain and store.api_version
- execute(query, variables) method: POSTs, raises a typed
  ShopifyGraphQLError (define in exceptions.py) on any "errors" key in the
  response, and a separate ShopifyRateLimitError if throttled
- Reads extensions.cost.throttleStatus from every successful response;
  if currentlyAvailable drops below SHOPIFY_TOOLKIT_RATE_LIMIT_BUFFER,
  sleep before returning (or before the next call — your call on exact
  mechanism, but document it)
- Retries transient network errors up to SHOPIFY_TOOLKIT_MAX_RETRIES times
  with exponential backoff

Also write tests/test_client.py using the responses library to mock HTTP
calls: one test for a clean success, one for a GraphQL errors-array
response, one for a throttled response triggering backoff, and one
confirming two different ShopifyStore instances never share a client or
leak headers into each other's request.

Run pytest and show me the results before continuing.
```

---

## Prompt 3 — Products + images module

```
Implement the products module (queries.py, mutations.py, services.py) and
images module the same way, covering:
- list products (paginated)
- get single product
- create product
- update/edit product
- delete product
- add product image
- remove product image
- reorder product images

services.py functions should take (store: ShopifyStore, ...) and return
plain Python dicts/dataclasses, not raw GraphQL response shapes — parse the
response into something clean for the consumer.

Write tests per module following the "Testing requirements per module"
section of CLAUDE.md — mocked success, mocked GraphQL error, and a
store-isolation test.

Show me pytest output when done.
```

---

## Prompt 4 — Orders module

```
Implement the orders module reusing client.py — no new HTTP logic, only
new queries/services: list orders, get single order, update
fulfillment/status as exposed by Shopify's Admin GraphQL Order object.
Same testing pattern as products. Show me pytest output.
```

---

## Prompt 5 — Customers module

```
Implement the customers module: list, get single, create, update. Same
pattern and same test coverage as products/orders. Show me pytest output.
```

---

## Prompt 6 — Webhooks module

```
Implement webhooks/verify.py (HMAC-SHA256 verification against
SHOPIFY_TOOLKIT_API_SECRET, per CLAUDE.md principle #6), webhooks/views.py
(a Django view that verifies the signature, then saves a WebhookEvent row
tied to the correct store — look up the store by shop domain from the
X-Shopify-Shop-Domain header), and webhooks/registry.py (a service function
to register a webhook subscription via GraphQL mutation, and one to list
existing subscriptions for a store).

Write webhooks/urls.py exposing the receiver view.

Write tests/webhooks/test_verify.py with a real HMAC fixture: one test for
a valid signature, one for a tampered payload with the original signature
attached (must return False, not raise).

Tell me how to test this against a real Shopify store using ngrok before we
move on, but don't wait for me — implement it now and describe the
verification steps afterward.
```

---

## Prompt 7 — Optional DRF layer

```
Implement the optional api/ package: serializers.py and viewsets.py
wrapping the products/orders/customers services, plus api/urls.py. This
must only import from the services modules, never the reverse — if
djangorestframework isn't installed, importing shopify_toolkit (without
shopify_toolkit.api) must still work fine. Guard the api package's __init__
so it fails with a clear ImportError message telling the user to
pip install django-shopify-toolkit[drf] if DRF isn't present.
```

---

## Prompt 8 — Packaging verification

```
Walk me through, step by step, running:
1. pytest --cov=shopify_toolkit --cov-report=term-missing (show me gaps)
2. python -m build
3. twine check dist/*
4. Creating a fresh venv and installing the built wheel (not editable),
   confirming import shopify_toolkit works and a migrate smoke test passes
   in a throwaway Django project

Fix anything that fails at any of these steps before we touch GitHub
Actions or PyPI.
```

---

## Prompt 9 — CI/CD

```
Now write .github/workflows/test.yml (runs pytest on every push/PR across
Django 4.2 and 5.x, Python 3.10-3.12) and .github/workflows/publish.yml
(triggered on GitHub Release, test -> build -> publish to PyPI via trusted
publisher OIDC, permissions: id-token: write on the publish job only).
Also write a test-publish.yml variant targeting TestPyPI for dry runs.
```

> **Amendment (superseded after initial build, at the user's request):**
> The release-triggered `publish.yml`/`test-publish.yml` pair above was
> replaced with a branch-based pipeline: `staging.yml` (push to `staging`
> -> test -> build -> publish to TestPyPI) and `production.yml` (push to
> `main` -> test -> build -> publish to PyPI -> tag `vX.Y.Z`). Both reuse
> `test.yml` as a `workflow_call` job and skip the publish step (without
> failing) if that exact version is already published, so pushing without
> a version bump is a safe no-op rather than a broken pipeline. Trusted
> publisher OIDC and the `id-token: write` scoping are unchanged — only the
> trigger and branch model changed.

---

## Prompt 10 — README + finish

```
Write the full README.md: install instructions, all required/optional
settings with descriptions, a complete usage example for products
(fetch a store, list products, create one, add an image), and a complete
webhook registration + verification example. Then re-check everything
against the "Definition of done" checklist in CLAUDE.md and tell me
honestly which boxes are and aren't checked yet.
```
