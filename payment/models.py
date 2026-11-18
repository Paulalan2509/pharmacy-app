from django.contrib.auth.models import User
from django.db import models
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone

from store.models import Product


class ShippingAddress(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    shipping_full_name = models.CharField(max_length=100)
    shipping_email = models.CharField(max_length=100)
    shipping_address1 = models.CharField(max_length=100)
    shipping_address2 = models.CharField(max_length=100)
    shipping_city = models.CharField(max_length=100)
    shipping_region = models.CharField(max_length=100, null=True, blank=True)
    shipping_zipcode = models.CharField(max_length=10, null=True, blank=True)
    shipping_country = models.CharField(max_length=100)
    shipping_phone = models.CharField(max_length=30, null=True, blank=True)

    # Don't pluralize address
    class Meta:
        verbose_name_plural = "Shipping Address"

    def __str__(self):
        return f'Shipping Address - {self.id}'

    @receiver(post_save, sender=User)
    def create_shipping(sender, instance, created, **kwargs):
        if created:
            ShippingAddress.objects.create(user=instance)


# Create Order Model
class Order(models.Model):
    PAYMENT_PENDING = 'pending'
    PAYMENT_PAID = 'paid'
    PAYMENT_FAILED = 'failed'
    PAYMENT_REFUNDED = 'refunded'
    PAYMENT_STATUS_CHOICES = [
        (PAYMENT_PENDING, 'Pending'),
        (PAYMENT_PAID, 'Paid'),
        (PAYMENT_FAILED, 'Failed'),
        (PAYMENT_REFUNDED, 'Refunded'),
    ]

    # Foreign key
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    full_name = models.CharField(max_length=100)
    email = models.EmailField(max_length=100)
    shipping_address = models.TextField(max_length=500)
    # The order total in the store currency, computed on the server at checkout.
    amount_paid = models.DecimalField(max_digits=15, decimal_places=2,
                                      help_text='Order total in the store currency.')
    date_ordered = models.DateTimeField(auto_now_add=True)
    shipped = models.BooleanField(default=False)
    date_shipped = models.DateTimeField(blank=True, null=True)

    # Payment tracking. An order is only "paid" after PayPal confirms it (IPN).
    payment_status = models.CharField(max_length=10, choices=PAYMENT_STATUS_CHOICES,
                                      default=PAYMENT_PENDING, db_index=True)
    invoice = models.CharField(max_length=64, unique=True, null=True, blank=True, editable=False)
    # The exact amount and currency requested from PayPal, fixed when the order is created.
    paypal_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    paypal_currency = models.CharField(max_length=3, blank=True)
    paypal_txn_id = models.CharField(max_length=64, blank=True)
    paid_at = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return f'Order - {str(self.id)}'

    @property
    def is_paid(self):
        return self.payment_status == self.PAYMENT_PAID


# Auto Add shipping Date
@receiver(pre_save, sender=Order)
def set_shipped_date_on_update(sender, instance, **kwargs):
    if instance.shipped and not instance.date_shipped:
        instance.date_shipped = timezone.now()


# Create Order Items Model
class OrderItem(models.Model):
    # Foreign Keys
    order = models.ForeignKey(Order, on_delete=models.CASCADE, null=True)
    # Deleting a product must not delete the order history that references it.
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)

    # Snapshot of the product name at the time of purchase.
    product_name = models.CharField(max_length=255, blank=True)
    quantity = models.PositiveBigIntegerField(default=1)
    price = models.DecimalField(max_digits=12, decimal_places=2)

    def __str__(self):
        return f'Order Item - {str(self.id)}'
