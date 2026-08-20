"""GraphQL query strings for the Products, Options, and Variants area.

Scope: list products, get single product, list variants, get single variant.
"""

PRODUCT_FIELDS_FRAGMENT = """
fragment ProductFields on Product {
    id
    title
    handle
    description
    status
    vendor
    productType
    tags
    createdAt
    updatedAt
    options {
        id
        name
        position
        values
    }
    variants(first: 100) {
        edges {
            cursor
            node {
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
        }
    }
    images(first: 50) {
        edges {
            node {
                id
                url
                altText
            }
        }
    }
}
"""

LIST_PRODUCTS_QUERY = (
    PRODUCT_FIELDS_FRAGMENT
    + """
query ListProducts($first: Int!, $after: String) {
    products(first: $first, after: $after) {
        edges {
            cursor
            node {
                ...ProductFields
            }
        }
        pageInfo {
            hasNextPage
            endCursor
        }
    }
}
"""
)

GET_PRODUCT_QUERY = (
    PRODUCT_FIELDS_FRAGMENT
    + """
query GetProduct($id: ID!) {
    product(id: $id) {
        ...ProductFields
    }
}
"""
)

LIST_PRODUCT_VARIANTS_QUERY = """
query ListProductVariants($id: ID!, $first: Int!, $after: String) {
    product(id: $id) {
        variants(first: $first, after: $after) {
            edges {
                cursor
                node {
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
            }
            pageInfo {
                hasNextPage
                endCursor
            }
        }
    }
}
"""

GET_PRODUCT_VARIANT_QUERY = """
query GetProductVariant($id: ID!) {
    node(id: $id) {
        ... on ProductVariant {
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
            weight
            weightUnit
            requiresShipping
            taxable
            product {
                id
            }
        }
    }
}
"""
