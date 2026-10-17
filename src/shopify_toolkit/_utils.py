"""Internal helpers shared across service modules. Not part of the public API."""
from __future__ import annotations

from typing import Any, Callable, Iterable, Iterator, TypeVar

from .exceptions import ShopifyToolkitError, ShopifyUserError

T = TypeVar("T")
P = TypeVar("P")


def to_camel_case(field_name: str) -> str:
    """Convert a snake_case string to camelCase.

    Already-camelCase input (no underscores) passes through unchanged, so
    callers who already pass Shopify's native camelCase field names (e.g.
    productType, firstName) keep working exactly as before.
    """
    if "_" not in field_name:
        return field_name
    first, *rest = field_name.split("_")
    return first + "".join(word.capitalize() for word in rest if word)


def camelize_keys(fields: dict) -> dict:
    """Convert all top-level keys of a dict from snake_case to camelCase.

    Used to build Shopify GraphQL mutation input payloads from **kwargs, so
    callers can write Pythonic snake_case (first_name=...) and it's mapped
    onto Shopify's actual camelCase input fields (firstName) automatically.
    Only top-level keys are converted — values (including nested dicts) are
    passed through untouched, since Shopify's own nested input object
    shapes are the caller's responsibility.
    """
    return {to_camel_case(key): value for key, value in fields.items()}


def raise_for_user_errors(user_errors: list | None, *, kind: str = "userErrors") -> None:
    """Raise ShopifyUserError if a mutation payload reported any field-level errors.

    `kind` only changes the message — e.g. "mediaUserErrors" for productCreateMedia, which
    reports its validation failures under a differently named field.
    """
    if user_errors:
        raise ShopifyUserError(f"Shopify returned {kind}: {user_errors}", user_errors=user_errors)


def parse_page_info(connection: dict[str, Any]) -> tuple[bool, str | None]:
    """(has_next_page, end_cursor) from a GraphQL connection's pageInfo."""
    page_info = connection["pageInfo"]
    return page_info["hasNextPage"], page_info.get("endCursor")


def iter_pages(
    fetch_page: Callable[[str | None], P], items: Callable[[P], Iterable[T]]
) -> Iterator[T]:
    """Yield every item across a cursor-paginated listing.

    `fetch_page(after)` returns one page (anything with has_next_page/end_cursor, e.g.
    ProductPage); `items(page)` picks that page's items out of it. Raises
    ShopifyToolkitError rather than looping forever if Shopify ever reports another page
    without a usable cursor to reach it — missing, or one already visited (including a
    longer cycle like A -> B -> A, not just the same cursor twice in a row).
    """
    after = None
    seen: set[str] = set()
    while True:
        page = fetch_page(after)
        yield from items(page)
        if not page.has_next_page:
            return
        if not page.end_cursor or page.end_cursor in seen:
            raise ShopifyToolkitError(
                f"Shopify reported hasNextPage=true but endCursor={page.end_cursor!r} is "
                "missing or already visited; stopping instead of looping forever"
            )
        seen.add(page.end_cursor)
        after = page.end_cursor
