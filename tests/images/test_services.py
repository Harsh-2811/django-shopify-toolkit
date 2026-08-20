import io
import pytest
import responses

from shopify_toolkit.exceptions import ShopifyGraphQLError, ShopifyUserError
from shopify_toolkit.images import services

ENDPOINT = "https://test-store.myshopify.com/admin/api/2025-01/graphql.json"
OTHER_ENDPOINT = "https://other-store.myshopify.com/admin/api/2025-01/graphql.json"
UPLOAD_URL = "https://shopify-staged-uploads.storage.googleapis.com"

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
        json={
            "data": {
                "product": {
                    "media": {
                        "edges": [
                            {"node": _media_image_node(id="img-1", alt="front")},
                            {"node": _media_image_node(id="img-2", alt="back")},
                        ]
                    }
                }
            }
        },
        status=200,
    )
    imgs = services.list_product_images(shopify_store, PRODUCT_ID)
    assert len(imgs) == 2
    assert imgs[0].id == "img-1"
    assert imgs[0].alt_text == "front"
    assert imgs[0].url == "https://cdn.example/img.png"


@responses.activate
@pytest.mark.django_db
def test_list_product_images_filters_out_non_image_media(shopify_store):
    responses.add(
        responses.POST,
        ENDPOINT,
        json={
            "data": {
                "product": {
                    "media": {
                        "edges": [
                            {"node": _media_image_node(id="img-1")},
                            {"node": {"id": "video-1", "alt": None}},
                        ]
                    }
                }
            }
        },
        status=200,
    )
    imgs = services.list_product_images(shopify_store, PRODUCT_ID)
    assert len(imgs) == 1
    assert imgs[0].id == "img-1"


@responses.activate
@pytest.mark.django_db
def test_list_product_images_graphql_error_raises(shopify_store):
    responses.add(
        responses.POST,
        ENDPOINT,
        json={"errors": [{"message": "bad query"}]},
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
                    "media": [_media_image_node(id="new-img", alt="hero")],
                    "mediaUserErrors": [],
                }
            }
        },
        status=200,
    )
    img = services.add_product_image(
        shopify_store, PRODUCT_ID, src="https://example.com/hero.png", alt_text="hero"
    )
    assert img.id == "new-img"
    assert img.alt_text == "hero"


@responses.activate
@pytest.mark.django_db
def test_add_product_image_url_may_be_none_while_processing(shopify_store):
    responses.add(
        responses.POST,
        ENDPOINT,
        json={
            "data": {
                "productCreateMedia": {
                    "media": [{"id": "pending-img", "alt": None, "image": None}],
                    "mediaUserErrors": [],
                }
            }
        },
        status=200,
    )
    img = services.add_product_image(shopify_store, PRODUCT_ID, src="https://example.com/p.png")
    assert img.id == "pending-img"
    assert img.url is None


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
                    "mediaUserErrors": [{"field": ["src"], "message": "invalid url"}],
                }
            }
        },
        status=200,
    )
    with pytest.raises(ShopifyUserError):
        services.add_product_image(shopify_store, PRODUCT_ID, src="bad")


@responses.activate
@pytest.mark.django_db
def test_remove_product_image_success(shopify_store):
    responses.add(
        responses.POST,
        ENDPOINT,
        json={
            "data": {
                "productDeleteMedia": {
                    "deletedMediaIds": ["deleted-id"],
                    "mediaUserErrors": [],
                }
            }
        },
        status=200,
    )
    res = services.remove_product_image(shopify_store, PRODUCT_ID, "target-id")
    assert res == "deleted-id"


@responses.activate
@pytest.mark.django_db
def test_reorder_product_images_sends_positions(shopify_store):
    responses.add(
        responses.POST,
        ENDPOINT,
        json={
            "data": {
                "productReorderMedia": {
                    "job": {"id": "gid://shopify/Job/1"},
                    "mediaUserErrors": [],
                }
            }
        },
        status=200,
    )
    services.reorder_product_images(shopify_store, PRODUCT_ID, ["img-2", "img-1"])
    call = responses.calls[0]
    moves = call.request.body.decode()
    assert '"id": "img-2", "newPosition": "0"' in moves or '"id":"img-2","newPosition":"0"' in moves


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


@responses.activate
@pytest.mark.django_db
def test_upload_product_image_file_bytesio_success(shopify_store):
    # 1. Staged Target GraphQL Mock
    responses.add(
        responses.POST,
        ENDPOINT,
        json={
            "data": {
                "stagedUploadsCreate": {
                    "stagedTargets": [
                        {
                            "url": UPLOAD_URL,
                            "resourceUrl": "https://cdn.shopify.com/files/uploaded_temp.png",
                            "parameters": [
                                {"name": "key", "value": "tmp/test.png"},
                                {"name": "policy", "value": "xyz"},
                            ],
                        }
                    ],
                    "userErrors": [],
                }
            }
        },
        status=200,
    )
    # 2. Upload Storage Multipart POST Mock
    responses.add(
        responses.POST,
        UPLOAD_URL,
        status=201,
    )
    # 3. Product Media Creation Mock
    responses.add(
        responses.POST,
        ENDPOINT,
        json={
            "data": {
                "productCreateMedia": {
                    "media": [_media_image_node(id="uploaded-img-id", alt="Upload Alt")],
                    "mediaUserErrors": [],
                }
            }
        },
        status=200,
    )

    fake_file = io.BytesIO(b"fake_image_binary_data")
    img = services.upload_product_image_file(
        shopify_store,
        PRODUCT_ID,
        file_source=fake_file,
        filename="test.png",
        alt_text="Upload Alt",
        content_type="image/png",
    )

    assert img.id == "uploaded-img-id"
    assert img.alt_text == "Upload Alt"
    assert len(responses.calls) == 3

    # Locks in the fix: must be "IMAGE" (current), never "PRODUCT_IMAGE"
    # (deprecated — tied to the classic ProductImage API this module
    # already moved away from).
    import json

    staged_request_body = json.loads(responses.calls[0].request.body)
    assert staged_request_body["variables"]["input"][0]["resource"] == "IMAGE"


@responses.activate
@pytest.mark.django_db
def test_upload_product_image_file_from_path_success(shopify_store, tmp_path):
    responses.add(
        responses.POST,
        ENDPOINT,
        json={
            "data": {
                "stagedUploadsCreate": {
                    "stagedTargets": [
                        {
                            "url": UPLOAD_URL,
                            "resourceUrl": "https://cdn.shopify.com/files/uploaded_temp.jpg",
                            "parameters": [{"name": "key", "value": "tmp/test.jpg"}],
                        }
                    ],
                    "userErrors": [],
                }
            }
        },
        status=200,
    )
    responses.add(responses.POST, UPLOAD_URL, status=201)
    responses.add(
        responses.POST,
        ENDPOINT,
        json={
            "data": {
                "productCreateMedia": {
                    "media": [_media_image_node(id="path-upload-id")],
                    "mediaUserErrors": [],
                }
            }
        },
        status=200,
    )

    local_file = tmp_path / "photo.jpg"
    local_file.write_bytes(b"fake-jpeg-bytes")

    img = services.upload_product_image_file(shopify_store, PRODUCT_ID, str(local_file))

    assert img.id == "path-upload-id"
    assert len(responses.calls) == 3


@responses.activate
@pytest.mark.django_db
def test_upload_product_image_file_from_django_uploaded_file(shopify_store):
    class FakeUploadedFile(io.BytesIO):
        """Stands in for django.core.files.uploadedfile.UploadedFile —
        same duck-typed .name/.content_type/.read() surface."""

        name = "avatar.png"
        content_type = "image/png"

    responses.add(
        responses.POST,
        ENDPOINT,
        json={
            "data": {
                "stagedUploadsCreate": {
                    "stagedTargets": [
                        {
                            "url": UPLOAD_URL,
                            "resourceUrl": "https://cdn.shopify.com/files/avatar.png",
                            "parameters": [{"name": "key", "value": "tmp/avatar.png"}],
                        }
                    ],
                    "userErrors": [],
                }
            }
        },
        status=200,
    )
    responses.add(responses.POST, UPLOAD_URL, status=201)
    responses.add(
        responses.POST,
        ENDPOINT,
        json={
            "data": {
                "productCreateMedia": {
                    "media": [_media_image_node(id="django-upload-id")],
                    "mediaUserErrors": [],
                }
            }
        },
        status=200,
    )

    uploaded = FakeUploadedFile(b"png-bytes")
    img = services.upload_product_image_file(shopify_store, PRODUCT_ID, uploaded)

    assert img.id == "django-upload-id"
    assert len(responses.calls) == 3


@responses.activate
@pytest.mark.django_db
def test_upload_product_image_file_missing_path_raises(shopify_store):
    with pytest.raises(FileNotFoundError):
        services.upload_product_image_file(shopify_store, PRODUCT_ID, "/no/such/file.png")
    assert len(responses.calls) == 0


@responses.activate
@pytest.mark.django_db
def test_upload_product_image_file_staged_upload_user_error_raises(shopify_store):
    responses.add(
        responses.POST,
        ENDPOINT,
        json={
            "data": {
                "stagedUploadsCreate": {
                    "stagedTargets": [],
                    "userErrors": [{"field": ["filename"], "message": "invalid filename"}],
                }
            }
        },
        status=200,
    )
    with pytest.raises(ShopifyUserError):
        services.upload_product_image_file(
            shopify_store, PRODUCT_ID, io.BytesIO(b"data"), filename="bad.png"
        )
