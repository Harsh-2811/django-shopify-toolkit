"""DRF serializers wrapping the products/orders/customers service dataclasses.

Output serializers read from the plain dataclasses returned by
products/orders/customers services.py — they never touch the ORM or raw
GraphQL response shapes.
"""
from rest_framework import serializers


class ProductImageSerializer(serializers.Serializer):
    id = serializers.CharField()
    url = serializers.CharField()
    alt_text = serializers.CharField(allow_null=True, required=False)


class SelectedOptionSerializer(serializers.Serializer):
    name = serializers.CharField()
    value = serializers.CharField()


class ProductOptionSerializer(serializers.Serializer):
    id = serializers.CharField()
    name = serializers.CharField()
    position = serializers.IntegerField()
    values = serializers.ListField(child=serializers.CharField())


class ProductVariantSerializer(serializers.Serializer):
    id = serializers.CharField()
    title = serializers.CharField()
    price = serializers.CharField()
    compare_at_price = serializers.CharField(allow_null=True, required=False)
    sku = serializers.CharField(allow_null=True, required=False)
    barcode = serializers.CharField(allow_null=True, required=False)
    available_for_sale = serializers.BooleanField(default=True)
    inventory_quantity = serializers.IntegerField(allow_null=True, required=False)
    inventory_item_id = serializers.CharField(allow_null=True, required=False)
    inventory_tracked = serializers.BooleanField(default=False)
    weight = serializers.FloatField(allow_null=True, required=False)
    weight_unit = serializers.CharField(allow_null=True, required=False)
    requires_shipping = serializers.BooleanField(default=True)
    taxable = serializers.BooleanField(default=True)
    image_id = serializers.CharField(allow_null=True, required=False)
    image_url = serializers.CharField(allow_null=True, required=False)
    image_alt_text = serializers.CharField(allow_null=True, required=False)
    selected_options = SelectedOptionSerializer(many=True, required=False)
    product_id = serializers.CharField(allow_null=True, required=False)


class ProductSerializer(serializers.Serializer):
    id = serializers.CharField()
    title = serializers.CharField()
    handle = serializers.CharField()
    description = serializers.CharField()
    status = serializers.CharField()
    vendor = serializers.CharField()
    product_type = serializers.CharField()
    tags = serializers.ListField(child=serializers.CharField())
    created_at = serializers.CharField()
    updated_at = serializers.CharField()
    options = ProductOptionSerializer(many=True, required=False)
    variants = ProductVariantSerializer(many=True, required=False)
    images = ProductImageSerializer(many=True, required=False)


class CreateProductSerializer(serializers.Serializer):
    title = serializers.CharField()
    vendor = serializers.CharField(required=False)
    productType = serializers.CharField(required=False)
    descriptionHtml = serializers.CharField(required=False)
    tags = serializers.ListField(child=serializers.CharField(), required=False)


class UpdateProductSerializer(serializers.Serializer):
    title = serializers.CharField(required=False)
    vendor = serializers.CharField(required=False)
    productType = serializers.CharField(required=False)
    descriptionHtml = serializers.CharField(required=False)
    tags = serializers.ListField(child=serializers.CharField(), required=False)


class CreateVariantSerializer(serializers.Serializer):
    price = serializers.CharField()
    compareAtPrice = serializers.CharField(required=False, allow_null=True)
    sku = serializers.CharField(required=False, allow_null=True)
    barcode = serializers.CharField(required=False, allow_null=True)
    optionValues = serializers.ListField(child=serializers.DictField(), required=False)


class UpdateVariantSerializer(serializers.Serializer):
    price = serializers.CharField(required=False)
    compareAtPrice = serializers.CharField(required=False, allow_null=True)
    sku = serializers.CharField(required=False, allow_null=True)
    barcode = serializers.CharField(required=False, allow_null=True)


class OrderSerializer(serializers.Serializer):
    id = serializers.CharField()
    name = serializers.CharField()
    email = serializers.CharField(allow_null=True)
    financial_status = serializers.CharField()
    fulfillment_status = serializers.CharField()
    total_price = serializers.CharField(allow_null=True)
    currency_code = serializers.CharField(allow_null=True)
    created_at = serializers.CharField()
    updated_at = serializers.CharField()


class CustomerSerializer(serializers.Serializer):
    id = serializers.CharField()
    first_name = serializers.CharField(allow_null=True)
    last_name = serializers.CharField(allow_null=True)
    email = serializers.CharField(allow_null=True)
    phone = serializers.CharField(allow_null=True)
    tags = serializers.ListField(child=serializers.CharField())
    created_at = serializers.CharField()
    updated_at = serializers.CharField()


class CreateCustomerSerializer(serializers.Serializer):
    email = serializers.CharField(required=False)
    firstName = serializers.CharField(required=False)
    lastName = serializers.CharField(required=False)
    phone = serializers.CharField(required=False)


class UpdateCustomerSerializer(serializers.Serializer):
    email = serializers.CharField(required=False)
    firstName = serializers.CharField(required=False)
    lastName = serializers.CharField(required=False)
    phone = serializers.CharField(required=False)
