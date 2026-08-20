"""GraphQL query strings for the Products area.

Scope-locked per CLAUDE.md: list products, get single product. Creation,
update, and delete live in mutations.py.
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
    images(first: 20) {
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
