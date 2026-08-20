from shopify_toolkit._utils import camelize_keys, to_camel_case


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
