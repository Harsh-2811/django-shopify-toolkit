"""Django signals dispatched by this package.

Lets consumers react to events with `@receiver(...)` anywhere in their
project, without subclassing or monkeypatching this package's views.
"""
import django.dispatch

# Sent after a webhook is verified and saved as a WebhookEvent row (see
# webhooks/views.py). Keyword args: store (ShopifyStore), topic (str),
# payload (dict), event (WebhookEvent).
webhook_received = django.dispatch.Signal()
