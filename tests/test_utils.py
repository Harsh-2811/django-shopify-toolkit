from dataclasses import dataclass, field

import pytest

from shopify_toolkit._utils import (
    camelize_keys,
    iter_pages,
    parse_page_info,
    raise_for_user_errors,
    to_camel_case,
)
from shopify_toolkit.exceptions import ShopifyToolkitError, ShopifyUserError


def test_to_camel_case_converts_snake_case():
    assert to_camel_case("first_name") == "firstName"
    assert to_camel_case("product_type") == "productType"
    assert to_camel_case("line_items_by_fulfillment_order") == "lineItemsByFulfillmentOrder"


def test_to_camel_case_leaves_already_camel_case_untouched():
    assert to_camel_case("firstName") == "firstName"
    assert to_camel_case("productType") == "productType"
    assert to_camel_case("tags") == "tags"
    assert to_camel_case("id") == "id"


def test_camelize_keys_converts_top_level_keys_only():
    result = camelize_keys(
        {"first_name": "Ada", "email": "ada@example.com", "nested": {"still_snake": 1}}
    )
    assert result == {
        "firstName": "Ada",
        "email": "ada@example.com",
        "nested": {"still_snake": 1},  # nested dict values untouched
    }


@pytest.mark.parametrize("user_errors", [None, []])
def test_raise_for_user_errors_is_noop_when_empty(user_errors):
    raise_for_user_errors(user_errors)


def test_raise_for_user_errors_raises_with_errors_attached():
    errors = [{"field": ["title"], "message": "Title can't be blank"}]
    with pytest.raises(ShopifyUserError, match="Shopify returned userErrors") as exc_info:
        raise_for_user_errors(errors)
    assert exc_info.value.user_errors == errors


def test_raise_for_user_errors_kind_changes_message():
    with pytest.raises(ShopifyUserError, match="Shopify returned mediaUserErrors"):
        raise_for_user_errors([{"message": "bad image"}], kind="mediaUserErrors")


def test_parse_page_info():
    assert parse_page_info({"pageInfo": {"hasNextPage": True, "endCursor": "c1"}}) == (True, "c1")
    assert parse_page_info({"pageInfo": {"hasNextPage": False}}) == (False, None)


@dataclass
class _Page:
    things: list
    has_next_page: bool
    end_cursor: str | None


@dataclass
class _FakeListing:
    pages: dict
    calls: list = field(default_factory=list)

    def fetch(self, after):
        self.calls.append(after)
        return self.pages[after]


def test_iter_pages_walks_every_page_in_order():
    listing = _FakeListing(
        {
            None: _Page([1, 2], True, "c1"),
            "c1": _Page([3], True, "c2"),
            "c2": _Page([4], False, "c3"),
        }
    )

    assert list(iter_pages(listing.fetch, lambda page: page.things)) == [1, 2, 3, 4]
    assert listing.calls == [None, "c1", "c2"]


def test_iter_pages_is_lazy():
    listing = _FakeListing({None: _Page([1], False, None)})

    iterator = iter_pages(listing.fetch, lambda page: page.things)

    assert listing.calls == []
    assert next(iterator) == 1


@pytest.mark.parametrize("bad_cursor", [None, ""])
def test_iter_pages_raises_instead_of_looping_on_missing_cursor(bad_cursor):
    listing = _FakeListing({None: _Page([1], True, bad_cursor)})

    with pytest.raises(ShopifyToolkitError, match="hasNextPage=true"):
        list(iter_pages(listing.fetch, lambda page: page.things))
    assert listing.calls == [None]


def test_iter_pages_raises_instead_of_looping_on_repeated_cursor():
    listing = _FakeListing(
        {
            None: _Page([1], True, "c1"),
            "c1": _Page([2], True, "c1"),
        }
    )

    with pytest.raises(ShopifyToolkitError):
        list(iter_pages(listing.fetch, lambda page: page.things))
    assert listing.calls == [None, "c1"]
