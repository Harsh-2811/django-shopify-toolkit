import pytest
import responses

from shopify_toolkit.exceptions import ShopifyGraphQLError, ShopifyUserError
from shopify_toolkit.products import services

ENDPOINT = "https://test-store.myshopify.com/admin/api/2025-01/graphql.json"
OTHER_ENDPOINT = "https://other-store.myshopify.com/admin/api/2025-01/graphql.json"

PRODUCT_ID = "gid://shopify/Product/1"
VARIANT_ID = "gid://shopify/ProductVariant/101"
OTHER_VARIANT_ID = "gid://shopify/ProductVariant/102"


def _sample_options():
    return [
        {"id": "opt-1", "name": "Color", "position": 1, "values": ["Black", "White"]},
        {"id": "opt-2", "name": "Size", "position": 2, "values": ["9", "10"]},
        {"id": "opt-3", "name": "Width", "position": 3, "values": ["Regular", "Wide"]},
    ]


def _sample_variant_node(
    variant_id="gid://shopify/ProductVariant/101",
    title="Black / 9 / Regular",
    price="100.00",
    compare_at_price="120.00",
    sku="SH-BLK-09-R",
    barcode="123456789012",
    inventory_qty=25,
    selected_options=None,
    weight=0.85,
    weight_unit="KILOGRAMS",
):
    if selected_options is None:
        selected_options = [
            {"name": "Color", "value": "Black"},
            {"name": "Size", "value": "9"},
            {"name": "Width", "value": "Regular"},
        ]
    return {
        "id": variant_id,
        "title": title,
        "price": price,
        "compareAtPrice": compare_at_price,
        "sku": sku,
        "barcode": barcode,
        "availableForSale": True,
        "inventoryQuantity": inventory_qty,
        "inventoryItem": {
            "id": "gid://shopify/InventoryItem/501",
            "tracked": True,
            "requiresShipping": True,
            "measurement": {
                "weight": {
                    "value": weight,
                    "unit": weight_unit,
                }
            },
        },
        "selectedOptions": selected_options,
        "image": {"id": "gid://shopify/MediaImage/901", "url": "https://cdn.example/black_shoe.png", "altText": "Black Shoe"},
        "taxable": True,
    }


def _sample_product_node(**overrides):
    node = {
        "id": PRODUCT_ID,
        "title": "Pro Running Shoe",
        "handle": "pro-running-shoe",
        "description": "High performance running shoe",
        "status": "ACTIVE",
        "vendor": "Acme Athletics",
        "productType": "Footwear",
        "tags": ["running", "shoes", "sports"],
        "createdAt": "2026-08-20T10:00:00Z",
        "updatedAt": "2026-08-20T10:00:00Z",
        "options": _sample_options(),
        "variants": {
            "edges": [
                {"cursor": "c1", "node": _sample_variant_node(
                    variant_id="gid://shopify/ProductVariant/101",
                    title="Black / 9 / Regular",
                    price="100.00",
                    sku="SH-BLK-09-R",
                    selected_options=[{"name": "Color", "value": "Black"}, {"name": "Size", "value": "9"}, {"name": "Width", "value": "Regular"}],
                )},
                {"cursor": "c2", "node": _sample_variant_node(
                    variant_id="gid://shopify/ProductVariant/102",
                    title="Black / 9 / Wide",
                    price="110.00",
                    sku="SH-BLK-09-W",
                    selected_options=[{"name": "Color", "value": "Black"}, {"name": "Size", "value": "9"}, {"name": "Width", "value": "Wide"}],
                )},
                {"cursor": "c3", "node": _sample_variant_node(
                    variant_id="gid://shopify/ProductVariant/103",
                    title="White / 10 / Regular",
                    price="105.00",
                    sku="SH-WHT-10-R",
                    selected_options=[{"name": "Color", "value": "White"}, {"name": "Size", "value": "10"}, {"name": "Width", "value": "Regular"}],
                )},
            ]
        },
        "images": {"edges": []},
    }
    node.update(overrides)
    return node


# ==============================================================================
# Product & Options/Variants Inspection Tests
# ==============================================================================

@responses.activate
@pytest.mark.django_db
def test_list_products_with_options_and_variants(shopify_store):
    responses.add(
        responses.POST,
        ENDPOINT,
        json={"data": {"products": {"edges": [{"cursor": "c1", "node": _sample_product_node()}], "pageInfo": {"hasNextPage": False, "endCursor": None}}}},
        status=200,
    )
    page = services.list_products(shopify_store)
    assert len(page.products) == 1
    prod = page.products[0]

    # Verify Options
    assert len(prod.options) == 3
    assert prod.options[0].name == "Color"
    assert prod.options[0].values == ["Black", "White"]
    assert prod.options[1].name == "Size"
    assert prod.options[2].name == "Width"

    # Verify Variants
    assert len(prod.variants) == 3
    v1, v2, v3 = prod.variants

    # Verify Composite Options and Same Color/Size with Different Width
    assert v1.title == "Black / 9 / Regular"
    assert v1.price == "100.00"
    assert v1.sku == "SH-BLK-09-R"
    assert v1.compare_at_price == "120.00"
    assert v1.inventory_quantity == 25
    assert v1.inventory_tracked is True
    assert v1.weight == 0.85
    assert len(v1.selected_options) == 3
    assert v1.selected_options[0].name == "Color" and v1.selected_options[0].value == "Black"
    assert v1.selected_options[2].name == "Width" and v1.selected_options[2].value == "Regular"

    # Second variant has SAME Color and Size but DIFFERENT Width and DIFFERENT Price
    assert v2.title == "Black / 9 / Wide"
    assert v2.price == "110.00"
    assert v2.sku == "SH-BLK-09-W"
    assert v2.selected_options[2].name == "Width" and v2.selected_options[2].value == "Wide"


@responses.activate
@pytest.mark.django_db
def test_get_product_variant_success(shopify_store):
    v_node = _sample_variant_node()
    v_node["product"] = {"id": PRODUCT_ID}
    responses.add(
        responses.POST,
        ENDPOINT,
        json={"data": {"node": v_node}},
        status=200,
    )
    variant = services.get_product_variant(shopify_store, VARIANT_ID)
    assert variant is not None
    assert variant.id == VARIANT_ID
    assert variant.price == "100.00"
    assert variant.sku == "SH-BLK-09-R"
    assert variant.barcode == "123456789012"
    assert variant.product_id == PRODUCT_ID


@responses.activate
@pytest.mark.django_db
def test_list_product_variants_success(shopify_store):
    responses.add(
        responses.POST,
        ENDPOINT,
        json={
            "data": {
                "product": {
                    "variants": {
                        "edges": [
                            {"cursor": "c1", "node": _sample_variant_node(variant_id=VARIANT_ID, price="100.00")},
                            {"cursor": "c2", "node": _sample_variant_node(variant_id=OTHER_VARIANT_ID, price="115.00")},
                        ],
                        "pageInfo": {"hasNextPage": False, "endCursor": None},
                    }
                }
            }
        },
        status=200,
    )
    variants = services.list_product_variants(shopify_store, PRODUCT_ID)
    assert len(variants) == 2
    assert variants[0].price == "100.00"
    assert variants[1].price == "115.00"


@responses.activate
@pytest.mark.django_db
def test_create_product_variant_success(shopify_store):
    v_node = _sample_variant_node(price="105.00", sku="SH-RED-10")
    responses.add(
        responses.POST,
        ENDPOINT,
        json={"data": {"productVariantsBulkCreate": {"productVariants": [v_node], "userErrors": []}}},
        status=200,
    )
    variant = services.create_product_variant(
        shopify_store,
        PRODUCT_ID,
        price="105.00",
        sku="SH-RED-10",
        option_values=[{"option_name": "Color", "name": "Red"}, {"option_name": "Size", "name": "10"}],
        barcode="987654321098",
        weight=0.9,
    )
    assert variant.price == "105.00"
    assert variant.sku == "SH-RED-10"


@responses.activate
@pytest.mark.django_db
def test_bulk_create_variants_success(shopify_store):
    v1 = _sample_variant_node(variant_id="v-1", price="90.00")
    v2 = _sample_variant_node(variant_id="v-2", price="95.00")
    responses.add(
        responses.POST,
        ENDPOINT,
        json={"data": {"productVariantsBulkCreate": {"productVariants": [v1, v2], "userErrors": []}}},
        status=200,
    )
    res = services.bulk_create_variants(
        shopify_store,
        PRODUCT_ID,
        variants=[
            {"price": "90.00", "option_values": [{"option_name": "Size", "name": "8"}]},
            {"price": "95.00", "option_values": [{"option_name": "Size", "name": "9"}]},
        ],
    )
    assert len(res) == 2
    assert res[0].price == "90.00"
    assert res[1].price == "95.00"


@responses.activate
@pytest.mark.django_db
def test_update_product_variant_success(shopify_store):
    # Shopify deprecated the single-variant productVariantUpdate mutation
    # in API version 2024-10 — update_product_variant() now wraps
    # productVariantsBulkUpdate with a single-item list, so that's what
    # this mocks (not the old productVariantUpdate response shape).
    updated_v = _sample_variant_node(price="129.99", sku="SH-BLK-09-PRO")
    responses.add(
        responses.POST,
        ENDPOINT,
        json={"data": {"productVariantsBulkUpdate": {"productVariants": [updated_v], "userErrors": []}}},
        status=200,
    )
    variant = services.update_product_variant(
        shopify_store,
        PRODUCT_ID,
        VARIANT_ID,
        price="129.99",
        sku="SH-BLK-09-PRO",
    )
    assert variant.price == "129.99"
    assert variant.sku == "SH-BLK-09-PRO"

    import json

    sent_body = json.loads(responses.calls[0].request.body)
    assert sent_body["variables"]["productId"] == PRODUCT_ID
    assert sent_body["variables"]["variants"] == [{"id": VARIANT_ID, "price": "129.99", "inventoryItem": {"sku": "SH-BLK-09-PRO"}}]


@responses.activate
@pytest.mark.django_db
def test_delete_product_variants_success(shopify_store):
    responses.add(
        responses.POST,
        ENDPOINT,
        json={"data": {"productVariantsBulkDelete": {"userErrors": []}}},
        status=200,
    )
    services.delete_product_variants(shopify_store, PRODUCT_ID, [VARIANT_ID, OTHER_VARIANT_ID])
    assert len(responses.calls) == 1


# ==============================================================================
# Product Options CRUD Tests
# ==============================================================================

@responses.activate
@pytest.mark.django_db
def test_create_product_option_success(shopify_store):
    responses.add(
        responses.POST,
        ENDPOINT,
        json={
            "data": {
                "productOptionsCreate": {
                    "product": {
                        "id": PRODUCT_ID,
                        "options": [
                            {"id": "opt-material", "name": "Material", "position": 4, "values": ["Leather", "Mesh"]}
                        ],
                    },
                    "userErrors": [],
                }
            }
        },
        status=200,
    )
    option = services.create_product_option(
        shopify_store,
        PRODUCT_ID,
        name="Material",
        values=["Leather", "Mesh"],
    )
    assert option.id == "opt-material"
    assert option.name == "Material"
    assert option.values == ["Leather", "Mesh"]


@responses.activate
@pytest.mark.django_db
def test_update_product_option_success(shopify_store):
    responses.add(
        responses.POST,
        ENDPOINT,
        json={
            "data": {
                "productOptionUpdate": {
                    "product": {
                        "id": PRODUCT_ID,
                        "options": [
                            {"id": "opt-1", "name": "Shoe Color", "position": 1, "values": ["Black", "White", "Red"]}
                        ],
                    },
                    "userErrors": [],
                }
            }
        },
        status=200,
    )
    option = services.update_product_option(
        shopify_store,
        PRODUCT_ID,
        option_id="opt-1",
        name="Shoe Color",
        values_to_add=["Red"],
    )
    assert option.name == "Shoe Color"
    assert "Red" in option.values


@responses.activate
@pytest.mark.django_db
def test_create_product_option_not_found_in_response_raises(shopify_store):
    # Response succeeded but doesn't contain an option matching the name we
    # just created — must raise, not fabricate a fake ProductOption(id="").
    responses.add(
        responses.POST,
        ENDPOINT,
        json={
            "data": {
                "productOptionsCreate": {
                    "product": {"id": PRODUCT_ID, "options": []},
                    "userErrors": [],
                }
            }
        },
        status=200,
    )
    with pytest.raises(ShopifyUserError):
        services.create_product_option(shopify_store, PRODUCT_ID, name="Material", values=["Leather"])


@responses.activate
@pytest.mark.django_db
def test_update_product_option_not_found_in_response_raises(shopify_store):
    responses.add(
        responses.POST,
        ENDPOINT,
        json={
            "data": {
                "productOptionUpdate": {
                    "product": {"id": PRODUCT_ID, "options": []},
                    "userErrors": [],
                }
            }
        },
        status=200,
    )
    with pytest.raises(ShopifyUserError):
        services.update_product_option(shopify_store, PRODUCT_ID, option_id="opt-1", name="X")


@responses.activate
@pytest.mark.django_db
def test_delete_product_option_success(shopify_store):
    responses.add(
        responses.POST,
        ENDPOINT,
        json={"data": {"productOptionsDelete": {"deletedOptionsIds": ["opt-1"], "userErrors": []}}},
        status=200,
    )
    deleted_ids = services.delete_product_option(shopify_store, PRODUCT_ID, "opt-1")
    assert deleted_ids == ["opt-1"]


# ==============================================================================
# Existing Product CRUD Tests
# ==============================================================================

@responses.activate
@pytest.mark.django_db
def test_list_products_success(shopify_store):
    responses.add(
        responses.POST,
        ENDPOINT,
        json={"data": {"products": {"edges": [{"cursor": "c1", "node": _sample_product_node()}], "pageInfo": {"hasNextPage": False, "endCursor": None}}}},
        status=200,
    )
    page = services.list_products(shopify_store)
    assert len(page.products) == 1
    assert page.products[0].id == PRODUCT_ID


@responses.activate
@pytest.mark.django_db
def test_get_product_success(shopify_store):
    responses.add(
        responses.POST,
        ENDPOINT,
        json={"data": {"product": _sample_product_node()}},
        status=200,
    )
    p = services.get_product(shopify_store, PRODUCT_ID)
    assert p is not None
    assert p.id == PRODUCT_ID
    assert p.title == "Pro Running Shoe"


@responses.activate
@pytest.mark.django_db
def test_create_product_success(shopify_store):
    responses.add(
        responses.POST,
        ENDPOINT,
        json={"data": {"productCreate": {"product": _sample_product_node(title="Created Shoe"), "userErrors": []}}},
        status=200,
    )
    p = services.create_product(shopify_store, title="Created Shoe", vendor="Nike")
    assert p.title == "Created Shoe"


@responses.activate
@pytest.mark.django_db
def test_update_product_success(shopify_store):
    responses.add(
        responses.POST,
        ENDPOINT,
        json={"data": {"productUpdate": {"product": _sample_product_node(title="Updated Title"), "userErrors": []}}},
        status=200,
    )
    p = services.update_product(shopify_store, product_id=PRODUCT_ID, title="Updated Title")
    assert p.title == "Updated Title"


@responses.activate
@pytest.mark.django_db
def test_delete_product_success(shopify_store):
    responses.add(
        responses.POST,
        ENDPOINT,
        json={"data": {"productDelete": {"deletedProductId": PRODUCT_ID, "userErrors": []}}},
        status=200,
    )
    deleted_id = services.delete_product(shopify_store, PRODUCT_ID)
    assert deleted_id == PRODUCT_ID


def test_parse_variant_legacy_fallback_fields():
    legacy_node = {
        "id": "gid://shopify/ProductVariant/999",
        "title": "Legacy Item",
        "price": "50.00",
        "availableForSale": True,
        "inventoryQuantity": 10,
        "inventoryItem": {"id": "gid://shopify/InventoryItem/999", "tracked": True},
        "selectedOptions": [],
        "weight": 2.5,
        "weightUnit": "POUNDS",
        "requiresShipping": False,
        "taxable": True,
    }
    variant = services._parse_variant(legacy_node)
    assert variant.weight == 2.5
    assert variant.weight_unit == "POUNDS"
    assert variant.requires_shipping is False
