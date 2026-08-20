"""GraphQL query strings for the Bulk Operations area.

Scope-locked per CLAUDE.md: check the current bulk operation's status.
Field shapes verified against shopify.dev's BulkOperation object reference.
"""

BULK_OPERATION_FIELDS_FRAGMENT = """
fragment BulkOperationFields on BulkOperation {
    id
    status
    errorCode
    createdAt
    completedAt
    objectCount
    fileSize
    url
    partialDataUrl
}
"""

CURRENT_BULK_OPERATION_QUERY = (
    BULK_OPERATION_FIELDS_FRAGMENT
    + """
query CurrentBulkOperation {
    currentBulkOperation {
        ...BulkOperationFields
    }
}
"""
)
