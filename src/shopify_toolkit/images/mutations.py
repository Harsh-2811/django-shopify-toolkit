"""GraphQL mutation strings for the Product Images area.

Scope-locked per CLAUDE.md: add image, remove image, reorder images. Uses
Shopify's Media API — see queries.py's docstring for why.
"""

ADD_PRODUCT_IMAGE_MUTATION = """
mutation AddProductImage($productId: ID!, $media: [CreateMediaInput!]!) {
    productCreateMedia(productId: $productId, media: $media) {
        media {
            id
            alt
            ... on MediaImage {
                image {
                    url
                }
            }
        }
        mediaUserErrors {
            field
            message
        }
    }
}
"""

REMOVE_PRODUCT_IMAGE_MUTATION = """
mutation RemoveProductImage($productId: ID!, $mediaIds: [ID!]!) {
    productDeleteMedia(productId: $productId, mediaIds: $mediaIds) {
        deletedMediaIds
        mediaUserErrors {
            field
            message
        }
    }
}
"""

# Asynchronous on Shopify's side — returns a Job rather than the reordered
# list directly. We don't poll it (out of scope); callers that need to know
# when reordering has actually landed can query the returned job.id
# themselves via Shopify's Job API.
REORDER_PRODUCT_IMAGES_MUTATION = """
mutation ReorderProductImages($productId: ID!, $moves: [MoveInput!]!) {
    productReorderMedia(id: $productId, moves: $moves) {
        job {
            id
        }
        mediaUserErrors {
            field
            message
        }
    }
}
"""

STAGED_UPLOADS_CREATE_MUTATION = """
mutation StagedUploadsCreate($input: [StagedUploadInput!]!) {
    stagedUploadsCreate(input: $input) {
        stagedTargets {
            url
            resourceUrl
            parameters {
                name
                value
            }
        }
        userErrors {
            field
            message
        }
    }
}
"""

