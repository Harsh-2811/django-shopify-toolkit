"""GraphQL mutation strings for the Bulk Operations area.

Scope-locked per CLAUDE.md: run a bulk query. Field shapes and arguments
verified against shopify.dev's bulkOperationRunQuery mutation reference.
"""
from .queries import BULK_OPERATION_FIELDS_FRAGMENT

RUN_BULK_QUERY_MUTATION = (
    BULK_OPERATION_FIELDS_FRAGMENT
    + """
mutation RunBulkQuery($query: String!) {
    bulkOperationRunQuery(query: $query) {
        bulkOperation {
            ...BulkOperationFields
        }
        userErrors {
            field
            message
        }
    }
}
"""
)
