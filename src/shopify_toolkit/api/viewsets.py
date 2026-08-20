"""DRF viewsets wrapping the products/orders/customers services.

These are plain rest_framework.viewsets.ViewSet subclasses (not
ModelViewSet) since the underlying data comes from Shopify via GraphQL, not
the Django ORM. This module only imports from the services modules, never
the reverse. Every viewset is scoped to a ShopifyStore resolved from the
`store_pk` URL kwarg — see api/urls.py.
"""
from __future__ import annotations

from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import ViewSet

from ..customers import services as customer_services
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


class StoreScopedViewSet(ViewSet):
    """Base class that resolves the ShopifyStore from the store_pk URL kwarg."""

    def get_store(self) -> ShopifyStore:
        return ShopifyStore.objects.get(pk=self.kwargs["store_pk"], is_active=True)


class ProductViewSet(StoreScopedViewSet):
    def list(self, request, store_pk=None):
        store = self.get_store()
        page = product_services.list_products(
            store,
            first=int(request.query_params.get("first", 50)),
            after=request.query_params.get("after"),
        )
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
        page = order_services.list_orders(
            store,
            first=int(request.query_params.get("first", 50)),
            after=request.query_params.get("after"),
        )
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
        page = customer_services.list_customers(
            store,
            first=int(request.query_params.get("first", 50)),
            after=request.query_params.get("after"),
        )
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
