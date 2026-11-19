"""Admin order screens and the signed-in checkout path."""
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

from payment.models import Order, ShippingAddress
from payment.tests import PAYPAL_SETTINGS, make_product

PASSWORD = 'pw-Strong-123'


class OrderScreenTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser('boss', 'boss@example.com', PASSWORD)
        self.customer = User.objects.create_user('cust', 'c@example.com', PASSWORD)
        self.paid = Order.objects.create(full_name='Paid', email='p@example.com', shipping_address='a',
                                         amount_paid=Decimal('100'), payment_status=Order.PAYMENT_PAID)
        self.unpaid = Order.objects.create(full_name='Unpaid', email='u@example.com', shipping_address='a',
                                           amount_paid=Decimal('50'))

    def test_dashboards_are_superuser_only(self):
        self.client.force_login(self.customer)
        for name, args in (('not_shipped_dash', []), ('shipped_dash', []), ('orders', [self.paid.pk])):
            response = self.client.get(reverse(name, args=args))
            self.assertEqual(response.status_code, 302, name)
            self.assertNotEqual(response.status_code, 200)

    def test_anonymous_visitors_cannot_see_order_screens(self):
        for name, args in (('not_shipped_dash', []), ('shipped_dash', []), ('orders', [self.paid.pk])):
            self.assertEqual(self.client.get(reverse(name, args=args)).status_code, 302, name)

    def test_not_shipped_list_only_has_paid_orders(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse('not_shipped_dash'))
        self.assertEqual(list(response.context['orders']), [self.paid])

    def test_shipped_list_and_unship(self):
        self.client.force_login(self.admin)
        self.client.post(reverse('not_shipped_dash'), {'num': self.paid.pk})
        self.assertEqual(list(self.client.get(reverse('shipped_dash')).context['orders']), [self.paid])
        self.client.post(reverse('shipped_dash'), {'num': self.paid.pk})
        self.paid.refresh_from_db()
        self.assertFalse(self.paid.shipped)

    def test_order_detail_page_and_status_change(self):
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(reverse('orders', args=[self.paid.pk])).status_code, 200)
        self.client.post(reverse('orders', args=[self.paid.pk]), {'shipping_status': 'true'})
        self.paid.refresh_from_db()
        self.assertTrue(self.paid.shipped)
        self.assertIsNotNone(self.paid.date_shipped)

    def test_unpaid_order_cannot_be_shipped_from_the_detail_page(self):
        self.client.force_login(self.admin)
        self.client.post(reverse('orders', args=[self.unpaid.pk]), {'shipping_status': 'true'})
        self.unpaid.refresh_from_db()
        self.assertFalse(self.unpaid.shipped)

    def test_shipping_post_without_an_order_number_is_not_a_crash(self):
        self.client.force_login(self.admin)
        response = self.client.post(reverse('not_shipped_dash'), {})
        self.assertIn(response.status_code, (302, 404))


@override_settings(**PAYPAL_SETTINGS)
class SignedInCheckoutTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('ada', 'ada@example.com', PASSWORD)
        self.client.force_login(self.user)
        self.product = make_product()

    def test_signed_in_checkout_prefills_and_creates_one_shipping_address(self):
        self.client.post(reverse('cart_add'), {'product_id': self.product.id, 'product_qty': 1})
        self.assertEqual(self.client.get(reverse('checkout')).status_code, 200)
        self.client.get(reverse('checkout'))
        self.assertEqual(ShippingAddress.objects.filter(user=self.user).count(), 1)

    def test_signed_in_order_is_linked_to_the_user(self):
        self.client.post(reverse('cart_add'), {'product_id': self.product.id, 'product_qty': 2})
        self.client.post(reverse('billing_info'), {
            'shipping_full_name': 'Ada', 'shipping_email': 'ada@example.com', 'shipping_address1': '1 Main',
            'shipping_city': 'Douala', 'shipping_country': 'Cameroon', 'shipping_phone': '123'})
        order = Order.objects.get()
        self.assertEqual(order.user, self.user)
        self.assertEqual(order.amount_paid, Decimal('3000'))

    def test_invalid_shipping_for_signed_in_user_redisplays_checkout(self):
        self.client.post(reverse('cart_add'), {'product_id': self.product.id, 'product_qty': 1})
        response = self.client.post(reverse('billing_info'), {'shipping_full_name': 'Ada'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Order.objects.count(), 0)

    def test_billing_info_by_get_goes_back_to_checkout(self):
        self.assertRedirects(self.client.get(reverse('billing_info')), reverse('checkout'),
                             fetch_redirect_response=False)

    def test_payment_failed_page_renders(self):
        self.assertEqual(self.client.get(reverse('payment_failed')).status_code, 200)
