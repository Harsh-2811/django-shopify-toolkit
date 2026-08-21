"""GraphQL query strings for the Product Images area.

Covers: list images for a product.

Uses Shopify's Media API (Product.media / MediaImage) rather than the
classic Product.images/ProductImage API. Confirmed against a live store
(API version 2026-07) that the classic mutations are gone from the schema
— productImageCreate raised "doesn't exist on type 'Mutation'" — so both
reads and writes here use Media consistently. Product.media returns every
attached media type (images, videos, 3D models); the `... on MediaImage`
fragment restricts what we select to image fields, and services.py filters
out non-image nodes.
"""

LIST_PRODUCT_IMAGES_QUERY = """
query ListProductImages($id: ID!, $first: Int!) {
    product(id: $id) {
        media(first: $first) {
            edges {
                node {
                    id
                    alt
                    ... on MediaImage {
                        image {
                            url
                        }
                    }
                }
            }
        }
    }
}
"""
