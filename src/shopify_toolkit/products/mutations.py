"""GraphQL mutation strings for the Products area.

Scope-locked per CLAUDE.md: create, update/edit, delete a product. Image
mutations live in the images/ package, not here.
"""
from .queries import PRODUCT_FIELDS_FRAGMENT

CREATE_PRODUCT_MUTATION = (
    PRODUCT_FIELDS_FRAGMENT
    + """
mutation CreateProduct($input: ProductInput!) {
    productCreate(input: $input) {
        product {
            ...ProductFields
        }
        userErrors {
            field
            message
        }
    }
}
"""
)

UPDATE_PRODUCT_MUTATION = (
    PRODUCT_FIELDS_FRAGMENT
    + """
mutation UpdateProduct($input: ProductInput!) {
    productUpdate(input: $input) {
        product {
            ...ProductFields
        }
        userErrors {
            field
            message
        }
    }
}
"""
)

DELETE_PRODUCT_MUTATION = """
mutation DeleteProduct($input: ProductDeleteInput!) {
    productDelete(input: $input) {
        deletedProductId
        userErrors {
            field
            message
        }
    }
}
"""
