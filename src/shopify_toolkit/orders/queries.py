"""GraphQL query and mutation strings for the Orders area.

Covers: list orders, get single order, update order/fulfillment status.
There's no separate mutations.py for this module — mutation strings live here too.
"""

ORDER_FIELDS_FRAGMENT = """
fragment OrderFields on Order {
    id
    name
    email
    displayFinancialStatus
    displayFulfillmentStatus
    totalPriceSet {
        shopMoney {
            amount
            currencyCode
        }
    }
    createdAt
    updatedAt
}
"""

LIST_ORDERS_QUERY = (
    ORDER_FIELDS_FRAGMENT
    + """
query ListOrders($first: Int!, $after: String) {
    orders(first: $first, after: $after) {
        edges {
            cursor
            node {
                ...OrderFields
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

GET_ORDER_QUERY = (
    ORDER_FIELDS_FRAGMENT
    + """
query GetOrder($id: ID!) {
    order(id: $id) {
        ...OrderFields
    }
}
"""
)

UPDATE_ORDER_MUTATION = (
    ORDER_FIELDS_FRAGMENT
    + """
mutation UpdateOrder($input: OrderInput!) {
    orderUpdate(input: $input) {
        order {
            ...OrderFields
        }
        userErrors {
            field
            message
        }
    }
}
"""
)

# Shopify's Admin GraphQL API surfaces "update fulfillment status" through
# fulfillment creation against a FulfillmentOrder, not a direct field on
# Order — fulfillmentOrderId below is a FulfillmentOrder GraphQL ID.
FULFILL_ORDER_MUTATION = (
    ORDER_FIELDS_FRAGMENT
    + """
mutation FulfillOrder($fulfillment: FulfillmentV2Input!) {
    fulfillmentCreateV2(fulfillment: $fulfillment) {
        fulfillment {
            id
            status
            order {
                ...OrderFields
            }
        }
        userErrors {
            field
            message
        }
    }
}
"""
)
