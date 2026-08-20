"""Internal helpers shared across service modules. Not part of the public API."""
from __future__ import annotations


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
