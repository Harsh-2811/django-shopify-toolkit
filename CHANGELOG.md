# Changelog

All notable changes to this project are documented in this file.

## [Unreleased]

### Added
- `query=` filter on `list_products`/`list_orders`/`list_customers` and
  their `iter_all_*` counterparts, passed through as Shopify's search syntax
  (e.g. `query="tag:vip"`). Also exposed as `?query=` on the REST list
  endpoints. Defaults to `None` (no filtering), so existing calls are
  unchanged.
- `delete_customer(store, customer_id)` and
  `DELETE /api/stores/<store_pk>/customers/<pk>/`.

## [1.1.0] - Unreleased

### Added
- `shopify_toolkit.signals.webhook_received` — dispatched after a webhook
  is verified and saved, so consumers can react with `@receiver(...)`
  anywhere in their project instead of polling `WebhookEvent`.
- `iter_all_products`/`iter_all_orders`/`iter_all_customers` — generators
  that fetch subsequent pages automatically, for consumers who don't want
  to manage `has_next_page`/`end_cursor` by hand.
- `shopify_toolkit.testing` (new `[testing]` extra) — `mock_shopify_api`/
  `mock_shopify_error` helpers for consumers' own test suites, usable as
  either a context manager or a decorator.
- `shopify_toolkit.bulk_operations` — `run_bulk_query`/
  `get_current_bulk_operation`/`wait_for_bulk_operation`/
  `download_bulk_operation_result`, wrapping Shopify's async bulk query API
  for datasets too large for paginated GraphQL. Added to CLAUDE.md's scope
  lock with explicit sign-off — read-only bulk queries, not bulk mutations.
- Product variants and options: `Product.options`/`Product.variants` now
  parse automatically; `list_product_variants`/`get_product_variant`/
  `create_product_variant`/`update_product_variant`/`bulk_create_variants`/
  `bulk_update_variants`/`delete_product_variants`/`create_product_option`/
  `update_product_option`/`delete_product_option`. Built on
  `productVariantsBulkCreate`/`productVariantsBulkUpdate`/
  `productVariantsBulkDelete` throughout — including for single-variant
  updates — since Shopify deprecated the singular `productVariantCreate`/
  `productVariantUpdate`/`productVariantDelete` mutations in API version
  2024-10, which is itself no longer a supported version.
- `upload_product_image_file` — uploads a local file (path, Django
  `UploadedFile`, or any file-like object) directly to Shopify via the
  Staged Uploads API, instead of requiring a public URL like
  `add_product_image`.
- `Literal` type hints for `Product`'s `status=` kwarg
  (`create_product`/`update_product`) — IDE autocomplete, works exactly
  like any other field.
- Bounded, LRU-evicted session pool (`SHOPIFY_TOOLKIT_MAX_POOLED_SESSIONS`,
  default 500) — the pool no longer grows unbounded in deployments managing
  thousands of stores; least-recently-used sessions are closed and dropped.

### Fixed
- `SHOPIFY_TOOLKIT_API_VERSION`/`ShopifyStore.api_version` default bumped
  from `2025-01` (already expired — Shopify supports each version for only
  ~12 months) to `2026-07` (current, verified live against a real store).
  Folded into `migrations/0001_initial.py` directly rather than a separate
  migration, since nothing had shipped to real PyPI yet.
- `upload_product_image_file` used `resource: "PRODUCT_IMAGE"` for the
  staged upload target — deprecated, tied to the classic ProductImage API
  this package already moved away from. Fixed to `"IMAGE"`, the current
  value for anything attached via `productCreateMedia`.
- `create_product_option`/`update_product_option` no longer fabricate a
  fake `ProductOption(id="", ...)` when Shopify's response doesn't contain
  a matching option — they raise `ShopifyUserError` instead, consistent
  with how the rest of this package treats unexpected response shapes.

## [1.0.0]

Published to TestPyPI directly (outside this session's tracked work), so
this entry is a placeholder rather than a full itemized list — see the
1.1.0 entry above for everything added since.

## [0.1.0]

Initial release — published to TestPyPI.

### Added
- `ShopifyStore` and `WebhookEvent` models, with encrypted token fields and
  an initial migration shipped inside the package. `ShopifyStore` supports
  two auth modes: a static `access_token` (pre-2026 custom apps), or
  `client_id`/`client_secret` (Dev Dashboard apps, 2026+) exchanged and
  cached transparently via the Client Credentials Grant — see `auth.py`.
- `ShopifyGraphQLClient` — a store-scoped Shopify Admin GraphQL client with
  typed exceptions, retry with exponential backoff, and cost-based
  rate-limit backoff.
- Products module: list, get, create, update, delete.
- Product images module: list, add, remove, reorder — built on Shopify's
  Media API (`productCreateMedia`/`productDeleteMedia`/`productReorderMedia`,
  `Product.media`/`MediaImage`), not the classic `productImage*`/
  `Product.images` API, which has been removed from the Admin GraphQL
  schema.
- Orders module: list, get, update, fulfillment status update.
- Customers module: list, get, create, update.
- Webhooks module: HMAC-SHA256 verification, a receiver view, and
  registration/listing of webhook subscriptions.
- Optional DRF layer (`shopify_toolkit.api`) with serializers, viewsets, and
  urls wrapping the above services — only active if `djangorestframework`
  is installed.
- `create_product`/`update_product`, `create_customer`/`update_customer`,
  and `update_order` now accept snake_case keyword arguments
  (`first_name=...`) in addition to Shopify's native camelCase
  (`firstName=...`) — snake_case is converted automatically before being
  sent as the GraphQL mutation input (see `_utils.camelize_keys`).
- Row-level locking (`SELECT ... FOR UPDATE`) around Client Credentials
  Grant token exchange, so concurrent requests for the same store serialize
  on one real exchange instead of each independently hitting Shopify's
  OAuth endpoint. Requires Postgres/MySQL to actually lock (verified: 80
  concurrent requests -> 1 exchange); SQLite has no real row-locking, so
  don't run a Client Credentials Grant store on SQLite in production under
  concurrent traffic. Also added: per-store pooled `requests.Session`
  (fewer TLS handshakes under load), and `SHOPIFY_TOOLKIT_MAX_BACKOFF_SECONDS`/
  `SHOPIFY_TOOLKIT_REQUEST_TIMEOUT` settings to bound worst-case blocking
  time per call. See README's "Concurrency & performance" section.

### Changed
- CI/CD restructured to a branch-based staging/production pipeline instead
  of GitHub-Release-triggered publishing: pushing to `staging` runs the
  full test suite and publishes to TestPyPI; pushing to `main` (i.e.
  merging staging into main) runs the full test suite and publishes to
  real PyPI, then tags the commit `vX.Y.Z`. Both skip the publish step
  (without failing) if that exact version is already published, so
  pushing without a version bump is a safe no-op. Replaces the old
  `publish.yml` (release-triggered) and `test-publish.yml` (manual-only)
  workflows with `staging.yml` and `production.yml`.
- `test.yml`'s "Run pytest" step now uses `python -m pytest` instead of the
  bare `pytest` console script — the module form adds the repo root to
  `sys.path` early enough for pytest-django to import
  `DJANGO_SETTINGS_MODULE` ("tests.settings"); the bare command failed in CI
  with `ImportError: No module named 'tests'` despite working locally.
- Test suite switched from SQLite to a real Postgres service container —
  `tests/settings.py` now connects to Postgres (configurable via
  `POSTGRES_*` env vars), and `test.yml`'s matrixed `test` job runs a
  `postgres:16-alpine` service alongside every Python/Django combination.
  SQLite's `SELECT ... FOR UPDATE` is a documented no-op, so it could never
  exercise the Client Credentials Grant row-locking (`auth.py`) as a real
  regression check — previously that was only verified by manually
  spinning up Postgres. `psycopg2-binary` is now a `dev` extra.
