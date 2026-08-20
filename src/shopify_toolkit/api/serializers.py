"""DRF serializers wrapping the products/orders/customers service dataclasses.

Output serializers read from the plain dataclasses returned by
products/orders/customers services.py — they never touch the ORM or raw
GraphQL response shapes. Input serializers validate request bodies before
their fields are handed to those same service functions as keyword
arguments, so field names here intentionally match the Shopify GraphQL
input field names (camelCase) that the service functions forward as-is.
"""
from rest_framework import serializers


class ProductImageSerializer(serializers.Serializer):
    id = serializers.CharField()
    url = serializers.CharField()
    alt_text = serializers.CharField(allow_null=True, required=False)


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
    images = ProductImageSerializer(many=True)


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
