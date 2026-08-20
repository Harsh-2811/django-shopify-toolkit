import pytest
import responses

from shopify_toolkit.exceptions import ShopifyGraphQLError, ShopifyUserError
from shopify_toolkit.images import services

ENDPOINT = "https://test-store.myshopify.com/admin/api/2025-01/graphql.json"
OTHER_ENDPOINT = "https://other-store.myshopify.com/admin/api/2025-01/graphql.json"

PRODUCT_ID = "gid://shopify/Product/1"


def _media_image_node(**overrides):
    node = {
        "id": "gid://shopify/MediaImage/1",
        "alt": None,
        "image": {"url": "https://cdn.example/img.png"},
    }
    node.update(overrides)
    return node


@responses.activate
@pytest.mark.django_db
def test_list_product_images_success(shopify_store):
    responses.add(
        responses.POST,
        ENDPOINT,
        json={"data": {"product": {"media": {"edges": [{"node": _media_image_node()}]}}}},
        status=200,
    )
    images = services.list_product_images(shopify_store, PRODUCT_ID)
    assert len(images) == 1
    assert images[0].url == "https://cdn.example/img.png"


@responses.activate
@pytest.mark.django_db
def test_list_product_images_filters_out_non_image_media(shopify_store):
    # A video node matches the query but not the `... on MediaImage`
    # fragment, so it has no "image" key at all in the response.
    video_node = {"id": "gid://shopify/Video/1", "alt": "a video"}
    responses.add(
        responses.POST,
        ENDPOINT,
        json={
            "data": {
                "product": {
                    "media": {"edges": [{"node": video_node}, {"node": _media_image_node()}]}
                }
            }
        },
        status=200,
    )
    images = services.list_product_images(shopify_store, PRODUCT_ID)
    assert len(images) == 1
    assert images[0].id == "gid://shopify/MediaImage/1"


@responses.activate
@pytest.mark.django_db
def test_list_product_images_graphql_error_raises(shopify_store):
    responses.add(
        responses.POST,
        ENDPOINT,
        json={"errors": [{"message": "boom"}]},
        status=200,
    )
    with pytest.raises(ShopifyGraphQLError):
        services.list_product_images(shopify_store, PRODUCT_ID)


@responses.activate
@pytest.mark.django_db
def test_add_product_image_success(shopify_store):
    responses.add(
        responses.POST,
        ENDPOINT,
        json={
            "data": {
                "productCreateMedia": {
                    "media": [_media_image_node(alt="Alt text")],
                    "mediaUserErrors": [],
                }
            }
        },
        status=200,
    )
    image = services.add_product_image(
        shopify_store, PRODUCT_ID, src="https://cdn.example/new.png", alt_text="Alt text"
    )
    assert image.alt_text == "Alt text"

    import json

    sent_body = json.loads(responses.calls[0].request.body)
    assert sent_body["variables"]["media"] == [
        {"originalSource": "https://cdn.example/new.png", "mediaContentType": "IMAGE", "alt": "Alt text"}
    ]


@responses.activate
@pytest.mark.django_db
def test_add_product_image_url_may_be_none_while_processing(shopify_store):
    # Shopify processes media asynchronously — url can be null immediately
    # after creation, before status becomes READY.
    responses.add(
        responses.POST,
        ENDPOINT,
        json={
            "data": {
                "productCreateMedia": {
                    "media": [{"id": "gid://shopify/MediaImage/2", "alt": None, "image": None}],
                    "mediaUserErrors": [],
                }
            }
        },
        status=200,
    )
    image = services.add_product_image(shopify_store, PRODUCT_ID, src="https://cdn.example/new.png")
    assert image.url is None


@responses.activate
@pytest.mark.django_db
def test_add_product_image_user_error_raises(shopify_store):
    responses.add(
        responses.POST,
        ENDPOINT,
        json={
            "data": {
                "productCreateMedia": {
                    "media": [],
                    "mediaUserErrors": [{"field": ["media", "originalSource"], "message": "invalid URL"}],
                }
            }
        },
        status=200,
    )
    with pytest.raises(ShopifyUserError):
        services.add_product_image(shopify_store, PRODUCT_ID, src="not-a-url")


@responses.activate
@pytest.mark.django_db
def test_remove_product_image_success(shopify_store):
    responses.add(
        responses.POST,
        ENDPOINT,
        json={
            "data": {
                "productDeleteMedia": {
                    "deletedMediaIds": ["gid://shopify/MediaImage/1"],
                    "mediaUserErrors": [],
                }
            }
        },
        status=200,
    )
    deleted_id = services.remove_product_image(
        shopify_store, PRODUCT_ID, "gid://shopify/MediaImage/1"
    )
    assert deleted_id == "gid://shopify/MediaImage/1"


@responses.activate
@pytest.mark.django_db
def test_reorder_product_images_sends_positions(shopify_store):
    responses.add(
        responses.POST,
        ENDPOINT,
        json={"data": {"productReorderMedia": {"job": {"id": "gid://shopify/Job/1"}, "mediaUserErrors": []}}},
        status=200,
    )
    services.reorder_product_images(shopify_store, PRODUCT_ID, ["img-2", "img-1"])

    import json

    sent_body = json.loads(responses.calls[0].request.body)
    moves = sent_body["variables"]["moves"]
    assert moves == [{"id": "img-2", "newPosition": "0"}, {"id": "img-1", "newPosition": "1"}]


@responses.activate
@pytest.mark.django_db
def test_reorder_product_images_media_user_error_raises(shopify_store):
    responses.add(
        responses.POST,
        ENDPOINT,
        json={
            "data": {
                "productReorderMedia": {
                    "job": None,
                    "mediaUserErrors": [{"field": ["moves"], "message": "invalid position"}],
                }
            }
        },
        status=200,
    )
    with pytest.raises(ShopifyUserError):
        services.reorder_product_images(shopify_store, PRODUCT_ID, ["img-1"])


@responses.activate
@pytest.mark.django_db
def test_store_isolation_list_product_images(shopify_store, other_shopify_store):
    empty = {"data": {"product": {"media": {"edges": []}}}}
    responses.add(responses.POST, ENDPOINT, json=empty, status=200)
    responses.add(responses.POST, OTHER_ENDPOINT, json=empty, status=200)

    services.list_product_images(shopify_store, PRODUCT_ID)
    services.list_product_images(other_shopify_store, PRODUCT_ID)

    call_a, call_b = responses.calls[0], responses.calls[1]
    assert call_a.request.headers["X-Shopify-Access-Token"] == "shpat_test_token_1"
    assert call_b.request.headers["X-Shopify-Access-Token"] == "shpat_test_token_2"
