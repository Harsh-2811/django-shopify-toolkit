import django.db.models.deletion
import encrypted_model_fields.fields
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="ShopifyStore",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("shop_domain", models.CharField(max_length=255, unique=True)),
                (
                    "access_token",
                    encrypted_model_fields.fields.EncryptedCharField(
                        blank=True, default="", max_length=255
                    ),
                ),
                ("access_token_expires_at", models.DateTimeField(blank=True, null=True)),
                (
                    "client_id",
                    encrypted_model_fields.fields.EncryptedCharField(
                        blank=True, default="", max_length=255
                    ),
                ),
                (
                    "client_secret",
                    encrypted_model_fields.fields.EncryptedCharField(
                        blank=True, default="", max_length=255
                    ),
                ),
                ("api_version", models.CharField(default="2026-07", max_length=10)),
                ("scopes", models.TextField(blank=True)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "Shopify store",
                "verbose_name_plural": "Shopify stores",
            },
        ),
        migrations.CreateModel(
            name="WebhookEvent",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("topic", models.CharField(max_length=100)),
                ("payload", models.JSONField()),
                ("received_at", models.DateTimeField(auto_now_add=True)),
                ("processed", models.BooleanField(default=False)),
                ("processing_error", models.TextField(blank=True)),
                (
                    "store",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="webhook_events",
                        to="shopify_toolkit.shopifystore",
                    ),
                ),
            ],
            options={
                "ordering": ["-received_at"],
            },
        ),
    ]
