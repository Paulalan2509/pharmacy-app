from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse
from paypal.standard.ipn.signals import valid_ipn_received

from payment.models import Order, OrderItem
from store.models import Category, Product

class FakeIPN:
    """Stands in for a verified django-paypal IPN record (the real signal sender)."""

    def __init__(self, **fields):
        self.__dict__.update(fields)


PAYPAL_SETTINGS = dict(
    PAYPAL_RECEIVER_EMAIL='shop@example.com',
    STORE_CURRENCY='XAF',
    PAYPAL_CURRENCY='USD',
    PAYPAL_EXCHANGE_RATE='600',
    CART_MAX_QTY=5,
)

SHIPPING = {
    'shipping_full_name': 'Ada Lovelace',
    'shipping_email': 'ada@example.com',
    'shipping_address1': '1 Main Street',
    'shipping_address2': '',
    'shipping_city': 'Yaounde',
    'shipping_region': 'Centre',
    'shipping_zipcode': '00237',
    'shipping_country': 'Cameroon',
    'shipping_phone': '+237600000000',
}


def make_product(name='Ibuprofen', price='1500', **extra):
    category, _ = Category.objects.get_or_create(name='Pain')
    return Product.objects.create(name=name, price=Decimal(price), category=category, image='x.jpg', **extra)


@override_settings(**PAYPAL_SETTINGS)
class CheckoutTests(TestCase):
    def setUp(self):
        self.product = make_product()  # 1500 XAF
        self.cheap = make_product('Aspirin', '300')

    def add_to_cart(self, product, qty):
        return self.client.post(reverse('cart_add'), {'product_id': product.id, 'product_qty': qty})

    def test_order_total_is_computed_on_the_server(self):
        self.add_to_cart(self.product, 2)
        self.add_to_cart(self.cheap, 1)
        # Tampered extra fields must be ignored: only shipping data is read from the form.
        response = self.client.post(reverse('billing_info'), {**SHIPPING, 'amount_paid': '1', 'totals': '1'})
        self.assertEqual(response.status_code, 200)

        order = Order.objects.get()
        self.assertEqual(order.amount_paid, Decimal('3300.00'))  # 2*1500 + 300
        self.assertEqual(order.paypal_amount, Decimal('5.50'))  # 3300 / 600
        self.assertEqual(order.paypal_currency, 'USD')
        self.assertEqual(order.payment_status, Order.PAYMENT_PENDING)
        self.assertEqual(OrderItem.objects.filter(order=order).count(), 2)
        self.assertIn(order.invoice, response.content.decode())

    def test_state_and_region_are_stored_from_the_validated_form(self):
        self.add_to_cart(self.product, 1)
        self.client.post(reverse('billing_info'), SHIPPING)
        self.assertIn('Centre', Order.objects.get().shipping_address)

    def test_invalid_shipping_creates_no_order(self):
        self.add_to_cart(self.product, 1)
        response = self.client.post(reverse('billing_info'), {**SHIPPING, 'shipping_email': ''})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Order.objects.count(), 0)

    def test_empty_cart_cannot_check_out(self):
        response = self.client.post(reverse('billing_info'), SHIPPING)
        self.assertRedirects(response, reverse('cart_summary'))
        self.assertEqual(Order.objects.count(), 0)

    def test_out_of_stock_item_blocks_checkout(self):
        self.add_to_cart(self.product, 1)
        Product.objects.filter(pk=self.product.pk).update(availability_status='Out of Stock')
        self.client.post(reverse('billing_info'), SHIPPING)
        self.assertEqual(Order.objects.count(), 0)

    @override_settings(PAYPAL_EXCHANGE_RATE='')
    def test_missing_exchange_rate_never_charges_a_guessed_amount(self):
        self.add_to_cart(self.product, 1)
        response = self.client.post(reverse('billing_info'), SHIPPING)
        self.assertRedirects(response, reverse('checkout'))
        self.assertEqual(Order.objects.count(), 0)

    def test_restarting_checkout_replaces_the_abandoned_pending_order(self):
        self.add_to_cart(self.product, 1)
        self.client.post(reverse('billing_info'), SHIPPING)
        self.client.post(reverse('billing_info'), SHIPPING)
        self.assertEqual(Order.objects.count(), 1)

    def test_returning_from_paypal_does_not_mark_the_order_paid(self):
        self.add_to_cart(self.product, 1)
        self.client.post(reverse('billing_info'), SHIPPING)
        response = self.client.get(reverse('payment_success'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Order.objects.get().payment_status, Order.PAYMENT_PENDING)
        self.assertEqual(len(self.client.session.get('session_key', {})), 0)  # cart emptied


@override_settings(**PAYPAL_SETTINGS)
class PayPalIPNTests(TestCase):
    def setUp(self):
        self.order = Order.objects.create(
            full_name='Ada', email='ada@example.com', shipping_address='addr',
            amount_paid=Decimal('3300'), invoice='inv123',
            paypal_amount=Decimal('5.50'), paypal_currency='USD',
        )

    def send_ipn(self, **overrides):
        data = dict(payment_status='Completed', receiver_email='shop@example.com', invoice='inv123',
                    mc_gross=Decimal('5.50'), mc_currency='USD', txn_id='TXN1')
        data.update(overrides)
        valid_ipn_received.send(sender=FakeIPN(**data))
        self.order.refresh_from_db()

    def test_matching_payment_marks_order_paid(self):
        self.send_ipn()
        self.assertEqual(self.order.payment_status, Order.PAYMENT_PAID)
        self.assertEqual(self.order.paypal_txn_id, 'TXN1')
        self.assertIsNotNone(self.order.paid_at)

    def test_underpayment_is_rejected(self):
        self.send_ipn(mc_gross=Decimal('0.01'))
        self.assertEqual(self.order.payment_status, Order.PAYMENT_PENDING)

    def test_wrong_currency_is_rejected(self):
        self.send_ipn(mc_currency='EUR')
        self.assertEqual(self.order.payment_status, Order.PAYMENT_PENDING)

    def test_payment_to_a_different_receiver_is_rejected(self):
        self.send_ipn(receiver_email='attacker@example.com')
        self.assertEqual(self.order.payment_status, Order.PAYMENT_PENDING)

    def test_unknown_invoice_is_ignored(self):
        self.send_ipn(invoice='nope')
        self.assertEqual(self.order.payment_status, Order.PAYMENT_PENDING)

    def test_pending_status_does_not_mark_paid(self):
        self.send_ipn(payment_status='Pending')
        self.assertEqual(self.order.payment_status, Order.PAYMENT_PENDING)

    def test_replayed_notification_is_harmless(self):
        self.send_ipn()
        first_paid_at = self.order.paid_at
        self.send_ipn()
        self.assertEqual(self.order.paid_at, first_paid_at)

    def test_refund_after_payment_marks_refunded(self):
        self.send_ipn()
        self.send_ipn(payment_status='Refunded', txn_id='TXN2')
        self.assertEqual(self.order.payment_status, Order.PAYMENT_REFUNDED)


class ShippingTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser('boss', 'boss@example.com', 'pw-Strong-123')
        self.client.force_login(self.admin)
        self.order = Order.objects.create(full_name='Ada', email='a@example.com',
                                          shipping_address='addr', amount_paid=Decimal('100'))

    def ship(self):
        return self.client.post(reverse('not_shipped_dash'), {'num': self.order.pk, 'shipping_status': 'true'})

    def test_unpaid_order_cannot_be_shipped(self):
        self.ship()
        self.order.refresh_from_db()
        self.assertFalse(self.order.shipped)

    def test_paid_order_can_be_shipped_and_gets_a_date(self):
        Order.objects.filter(pk=self.order.pk).update(payment_status=Order.PAYMENT_PAID)
        self.ship()
        self.order.refresh_from_db()
        self.assertTrue(self.order.shipped)
        self.assertIsNotNone(self.order.date_shipped)

    def test_non_superuser_is_denied(self):
        self.client.logout()
        response = self.client.get(reverse('not_shipped_dash'))
        self.assertRedirects(response, reverse('home'), fetch_redirect_response=False)

    def test_unknown_order_is_404_not_500(self):
        response = self.client.get(reverse('orders', args=[99999]))
        self.assertEqual(response.status_code, 404)
