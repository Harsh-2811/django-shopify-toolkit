"""URL patterns for the optional DRF API layer.

Every endpoint is nested under a store: /stores/<store_pk>/products/, etc.
Detail routes use the `path` converter for `pk` because Shopify GraphQL IDs
(e.g. "gid://shopify/Product/123") contain slashes.
"""
from django.urls import path

from .viewsets import CustomerViewSet, OrderViewSet, ProductViewSet

app_name = "shopify_toolkit_api"

product_list = ProductViewSet.as_view({"get": "list", "post": "create"})
product_detail = ProductViewSet.as_view(
    {"get": "retrieve", "put": "update", "patch": "update", "delete": "destroy"}
)

order_list = OrderViewSet.as_view({"get": "list"})
order_detail = OrderViewSet.as_view({"get": "retrieve"})
order_fulfill = OrderViewSet.as_view({"post": "fulfill"})

customer_list = CustomerViewSet.as_view({"get": "list", "post": "create"})
customer_detail = CustomerViewSet.as_view({"get": "retrieve", "put": "update", "patch": "update"})

urlpatterns = [
    path("stores/<int:store_pk>/products/", product_list, name="product-list"),
    path("stores/<int:store_pk>/products/<path:pk>/", product_detail, name="product-detail"),
    path("stores/<int:store_pk>/orders/", order_list, name="order-list"),
    path("stores/<int:store_pk>/orders/<path:pk>/", order_detail, name="order-detail"),
    path("stores/<int:store_pk>/orders/<path:pk>/fulfill/", order_fulfill, name="order-fulfill"),
    path("stores/<int:store_pk>/customers/", customer_list, name="customer-list"),
    path("stores/<int:store_pk>/customers/<path:pk>/", customer_detail, name="customer-detail"),
]
