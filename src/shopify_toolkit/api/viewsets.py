"""DRF viewsets wrapping the products/orders/customers services.

These are plain rest_framework.viewsets.ViewSet subclasses (not
ModelViewSet) since the underlying data comes from Shopify via GraphQL, not
the Django ORM. This module only imports from the services modules, never
the reverse. Every viewset is scoped to a ShopifyStore resolved from the
`store_pk` URL kwarg — see api/urls.py.

Error mapping (StoreScopedViewSet): an unknown/inactive store is a 404, a bad `?first=` is a
400, and a ShopifyUserError (Shopify rejected the input) is a 400 carrying its userErrors.
Anything else — GraphQL, rate-limit, transport errors — is left to DRF/Django as before.
"""
from __future__ import annotations

from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.viewsets import ViewSet

from ..customers import services as customer_services
from ..exceptions import ShopifyUserError
from ..models import ShopifyStore
from ..orders import services as order_services
from ..products import services as product_services
from .serializers import (
    CreateCustomerSerializer,
    CreateProductSerializer,
    CustomerSerializer,
    OrderSerializer,
    ProductSerializer,
    UpdateCustomerSerializer,
    UpdateProductSerializer,
)


DEFAULT_PAGE_SIZE = 50
# Shopify's hard cap on `first` for any connection; larger values are a GraphQL error.
MAX_PAGE_SIZE = 250


class StoreScopedViewSet(ViewSet):
    """Base class that resolves the ShopifyStore from the store_pk URL kwarg."""

    def get_store(self) -> ShopifyStore:
        return get_object_or_404(ShopifyStore, pk=self.kwargs["store_pk"], is_active=True)

    def get_list_params(self, request) -> dict:
        """first/after/query kwargs for a list_* service call, validated from the query string."""
        raw_first = request.query_params.get("first", DEFAULT_PAGE_SIZE)
        try:
            first = int(raw_first)
        except (TypeError, ValueError):
            raise ValidationError({"first": ["A valid integer is required."]})
        if not 1 <= first <= MAX_PAGE_SIZE:
            raise ValidationError({"first": [f"Must be between 1 and {MAX_PAGE_SIZE}."]})
        return {
            "first": first,
            "after": request.query_params.get("after") or None,
            "query": request.query_params.get("query") or None,
        }

    def handle_exception(self, exc):
        if isinstance(exc, ShopifyUserError):
            return Response(
                {"detail": "Shopify rejected the request.", "user_errors": exc.user_errors},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return super().handle_exception(exc)


class ProductViewSet(StoreScopedViewSet):
    def list(self, request, store_pk=None):
        store = self.get_store()
        page = product_services.list_products(store, **self.get_list_params(request))
        return Response(
            {
                "results": ProductSerializer(page.products, many=True).data,
                "has_next_page": page.has_next_page,
                "end_cursor": page.end_cursor,
            }
        )

    def retrieve(self, request, pk=None, store_pk=None):
        store = self.get_store()
        product = product_services.get_product(store, pk)
        if product is None:
            return Response(status=status.HTTP_404_NOT_FOUND)
        return Response(ProductSerializer(product).data)

    def create(self, request, store_pk=None):
        store = self.get_store()
        serializer = CreateProductSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        product = product_services.create_product(store, **serializer.validated_data)
        return Response(ProductSerializer(product).data, status=status.HTTP_201_CREATED)

    def update(self, request, pk=None, store_pk=None):
        store = self.get_store()
        serializer = UpdateProductSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        product = product_services.update_product(store, product_id=pk, **serializer.validated_data)
        return Response(ProductSerializer(product).data)

    def destroy(self, request, pk=None, store_pk=None):
        store = self.get_store()
        product_services.delete_product(store, pk)
        return Response(status=status.HTTP_204_NO_CONTENT)


class OrderViewSet(StoreScopedViewSet):
    def list(self, request, store_pk=None):
        store = self.get_store()
        page = order_services.list_orders(store, **self.get_list_params(request))
        return Response(
            {
                "results": OrderSerializer(page.orders, many=True).data,
                "has_next_page": page.has_next_page,
                "end_cursor": page.end_cursor,
            }
        )

    def retrieve(self, request, pk=None, store_pk=None):
        store = self.get_store()
        order = order_services.get_order(store, pk)
        if order is None:
            return Response(status=status.HTTP_404_NOT_FOUND)
        return Response(OrderSerializer(order).data)

    @action(detail=True, methods=["post"])
    def fulfill(self, request, pk=None, store_pk=None):
        """POST .../orders/<fulfillment_order_id>/fulfill/ — mark an order fulfilled."""
        store = self.get_store()
        order = order_services.update_fulfillment_status(
            store,
            pk,
            tracking_number=request.data.get("tracking_number"),
            tracking_company=request.data.get("tracking_company"),
            notify_customer=request.data.get("notify_customer", True),
        )
        return Response(OrderSerializer(order).data)


class CustomerViewSet(StoreScopedViewSet):
    def list(self, request, store_pk=None):
        store = self.get_store()
        page = customer_services.list_customers(store, **self.get_list_params(request))
        return Response(
            {
                "results": CustomerSerializer(page.customers, many=True).data,
                "has_next_page": page.has_next_page,
                "end_cursor": page.end_cursor,
            }
        )

    def retrieve(self, request, pk=None, store_pk=None):
        store = self.get_store()
        customer = customer_services.get_customer(store, pk)
        if customer is None:
            return Response(status=status.HTTP_404_NOT_FOUND)
        return Response(CustomerSerializer(customer).data)

    def create(self, request, store_pk=None):
        store = self.get_store()
        serializer = CreateCustomerSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        customer = customer_services.create_customer(store, **serializer.validated_data)
        return Response(CustomerSerializer(customer).data, status=status.HTTP_201_CREATED)

    def update(self, request, pk=None, store_pk=None):
        store = self.get_store()
        serializer = UpdateCustomerSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        customer = customer_services.update_customer(
            store, customer_id=pk, **serializer.validated_data
        )
        return Response(CustomerSerializer(customer).data)

    def destroy(self, request, pk=None, store_pk=None):
        store = self.get_store()
        customer_services.delete_customer(store, pk)
        return Response(status=status.HTTP_204_NO_CONTENT)
