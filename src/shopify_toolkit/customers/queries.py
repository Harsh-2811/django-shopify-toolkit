"""GraphQL query and mutation strings for the Customers area.

Covers: list customers, get single customer, create customer, update
customer, delete customer. No separate mutations.py for this module — mutation strings live here too.
"""

CUSTOMER_FIELDS_FRAGMENT = """
fragment CustomerFields on Customer {
    id
    firstName
    lastName
    email
    phone
    tags
    createdAt
    updatedAt
}
"""

LIST_CUSTOMERS_QUERY = (
    CUSTOMER_FIELDS_FRAGMENT
    + """
query ListCustomers($first: Int!, $after: String, $query: String) {
    customers(first: $first, after: $after, query: $query) {
        edges {
            cursor
            node {
                ...CustomerFields
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

GET_CUSTOMER_QUERY = (
    CUSTOMER_FIELDS_FRAGMENT
    + """
query GetCustomer($id: ID!) {
    customer(id: $id) {
        ...CustomerFields
    }
}
"""
)

CREATE_CUSTOMER_MUTATION = (
    CUSTOMER_FIELDS_FRAGMENT
    + """
mutation CreateCustomer($input: CustomerInput!) {
    customerCreate(input: $input) {
        customer {
            ...CustomerFields
        }
        userErrors {
            field
            message
        }
    }
}
"""
)

UPDATE_CUSTOMER_MUTATION = (
    CUSTOMER_FIELDS_FRAGMENT
    + """
mutation UpdateCustomer($input: CustomerInput!) {
    customerUpdate(input: $input) {
        customer {
            ...CustomerFields
        }
        userErrors {
            field
            message
        }
    }
}
"""
)

DELETE_CUSTOMER_MUTATION = """
mutation DeleteCustomer($input: CustomerDeleteInput!) {
    customerDelete(input: $input) {
        deletedCustomerId
        userErrors {
            field
            message
        }
    }
}
"""
