
from django.db import migrations

from shopify_toolkit.conf import get_db_schema, get_qualified_table_name

_schema = get_db_schema()


def _move_tables_to_schema(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(f'CREATE SCHEMA IF NOT EXISTS "{_schema}"')
    schema_editor.execute(f'ALTER TABLE "shopify_toolkit_shopifystore" SET SCHEMA "{_schema}"')
    schema_editor.execute(f'ALTER TABLE "shopify_toolkit_webhookevent" SET SCHEMA "{_schema}"')


def _move_tables_back_to_public(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(
        f'ALTER TABLE "{_schema}"."shopify_toolkit_shopifystore" SET SCHEMA "public"'
    )
    schema_editor.execute(
        f'ALTER TABLE "{_schema}"."shopify_toolkit_webhookevent" SET SCHEMA "public"'
    )


class Migration(migrations.Migration):

    dependencies = [("shopify_toolkit", "0001_initial")]

    
    if _schema:
        operations = [
            migrations.SeparateDatabaseAndState(
                database_operations=[
                    migrations.RunPython(
                        _move_tables_to_schema, _move_tables_back_to_public
                    ),
                ],
                state_operations=[
                    migrations.AlterModelTable(
                        name="shopifystore",
                        table=get_qualified_table_name("shopify_toolkit_shopifystore"),
                    ),
                    migrations.AlterModelTable(
                        name="webhookevent",
                        table=get_qualified_table_name("shopify_toolkit_webhookevent"),
                    ),
                ],
            ),
        ]
    else:
        operations = []
