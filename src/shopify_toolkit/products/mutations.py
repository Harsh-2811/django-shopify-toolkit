"""GraphQL mutation strings for the Products, Options, and Variants area.

Scope: create, update/edit, delete products, variants, and product options.

No single-variant productVariantCreate/productVariantUpdate/
productVariantDelete mutations here on purpose — Shopify deprecated all
three in API version 2024-10 in favor of the Bulk equivalents
(productVariantsBulkCreate/Update/Delete), which is all that's used below,
even for updating just one variant (see services.update_product_variant).
Verified against shopify.dev's changelog, not assumed.
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

PRODUCT_VARIANTS_BULK_CREATE_MUTATION = """
mutation ProductVariantsBulkCreate($productId: ID!, $variants: [ProductVariantsBulkInput!]!) {
    productVariantsBulkCreate(productId: $productId, variants: $variants) {
        productVariants {
            id
            title
            price
            compareAtPrice
            sku
            barcode
            availableForSale
            inventoryQuantity
            inventoryItem {
                id
                tracked
                requiresShipping
                measurement {
                    weight {
                        unit
                        value
                    }
                }
            }
            selectedOptions {
                name
                value
            }
            image {
                id
                url
                altText
            }
            taxable
        }
        userErrors {
            field
            message
        }
    }
}
"""

PRODUCT_VARIANTS_BULK_UPDATE_MUTATION = """
mutation ProductVariantsBulkUpdate($productId: ID!, $variants: [ProductVariantsBulkInput!]!) {
    productVariantsBulkUpdate(productId: $productId, variants: $variants) {
        productVariants {
            id
            title
            price
            compareAtPrice
            sku
            barcode
            availableForSale
            inventoryQuantity
            inventoryItem {
                id
                tracked
                requiresShipping
                measurement {
                    weight {
                        unit
                        value
                    }
                }
            }
            selectedOptions {
                name
                value
            }
            image {
                id
                url
                altText
            }
            taxable
        }
        userErrors {
            field
            message
        }
    }
}
"""

PRODUCT_VARIANTS_BULK_DELETE_MUTATION = """
mutation ProductVariantsBulkDelete($productId: ID!, $variantsIds: [ID!]!) {
    productVariantsBulkDelete(productId: $productId, variantsIds: $variantsIds) {
        userErrors {
            field
            message
        }
    }
}
"""

PRODUCT_OPTIONS_CREATE_MUTATION = """
mutation ProductOptionsCreate($productId: ID!, $options: [OptionCreateInput!]!) {
    productOptionsCreate(productId: $productId, options: $options) {
        userErrors {
            field
            message
        }
        product {
            id
            options {
                id
                name
                position
                values
            }
        }
    }
}
"""

PRODUCT_OPTION_UPDATE_MUTATION = """
mutation ProductOptionUpdate($productId: ID!, $option: OptionUpdateInput!, $optionValuesToAdd: [OptionValueCreateInput!], $optionValuesToUpdate: [OptionValueUpdateInput!], $optionValuesToDelete: [ID!]) {
    productOptionUpdate(productId: $productId, option: $option, optionValuesToAdd: $optionValuesToAdd, optionValuesToUpdate: $optionValuesToUpdate, optionValuesToDelete: $optionValuesToDelete) {
        userErrors {
            field
            message
        }
        product {
            id
            options {
                id
                name
                position
                values
            }
        }
    }
}
"""

PRODUCT_OPTIONS_DELETE_MUTATION = """
mutation ProductOptionsDelete($productId: ID!, $options: [ID!]!) {
    productOptionsDelete(productId: $productId, options: $options) {
        userErrors {
            field
            message
        }
        deletedOptionsIds
    }
}
"""
