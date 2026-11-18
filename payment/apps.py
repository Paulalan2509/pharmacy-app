from django.apps import AppConfig


class PaymentConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'payment'

    def ready(self):
        # Register the PayPal IPN handler.
        from . import signals  # noqa: F401
