# Changelog

All notable changes to this project are documented in this file.

## [0.1.0] - Unreleased

Initial release.

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
