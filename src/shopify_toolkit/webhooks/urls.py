from django.urls import path

from .views import receive_webhook

app_name = "shopify_toolkit_webhooks"

urlpatterns = [
    path("receive/", receive_webhook, name="receive"),
]
