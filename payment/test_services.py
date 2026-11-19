"""Unit tests for pricing, validation and PayPal amount conversion (the money rules)."""
from decimal import Decimal

from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from payment.services import (CartLine, CheckoutError, PaymentConfigError, cart_total, get_cart_lines,
                              paypal_amount, validate_lines)
from payment.tests import PAYPAL_SETTINGS, make_product


class FakeCart:
    """Just enough of Cart for get_cart_lines."""

    def __init__(self, products, quantities):
        self._products, self._quantities = products, quantities

    def get_prods(self):
        return self._products

    def get_quants(self):
        return self._quantities


@override_settings(**PAYPAL_SETTINGS)
class CartLineTests(TestCase):
    def test_sale_price_is_used_when_the_product_is_on_sale(self):
        sale = make_product('Sale', '1000', is_sale=True, sale_price=Decimal('800'))
        normal = make_product('Normal', '300')
        lines = get_cart_lines(FakeCart([sale, normal], {str(sale.id): 2, str(normal.id): 1}))
        self.assertEqual([l.unit_price for l in lines], [Decimal('800'), Decimal('300')])
        self.assertEqual(cart_total(lines), Decimal('1900'))

    def test_zero_or_garbage_quantities_are_dropped(self):
        a, b, c = make_product('A'), make_product('B'), make_product('C')
        lines = get_cart_lines(FakeCart([a, b, c], {str(a.id): 0, str(b.id): 'x', str(c.id): 3}))
        self.assertEqual([l.product for l in lines], [c])

    def test_empty_cart_totals_zero(self):
        self.assertEqual(cart_total([]), Decimal('0'))


@override_settings(**PAYPAL_SETTINGS)
class ValidateLinesTests(TestCase):
    def line(self, quantity=1, **product_fields):
        product = make_product(**product_fields)
        return CartLine(product=product, quantity=quantity, unit_price=product.price)

    def test_empty_cart_is_refused(self):
        with self.assertRaises(CheckoutError):
            validate_lines([])

    def test_out_of_stock_is_refused(self):
        with self.assertRaisesMessage(CheckoutError, 'out of stock'):
            validate_lines([self.line(availability_status='Out of Stock')])

    def test_pre_order_is_allowed(self):
        validate_lines([self.line(availability_status='Pre-order')])

    def test_quantity_over_the_limit_is_refused(self):
        with self.assertRaisesMessage(CheckoutError, 'at most 5'):
            validate_lines([self.line(quantity=6)])

    def test_quantity_at_the_limit_is_allowed(self):
        validate_lines([self.line(quantity=5)])

    def test_free_products_cannot_be_ordered(self):
        with self.assertRaises(CheckoutError):
            validate_lines([self.line(price='0')])


class PayPalAmountTests(SimpleTestCase):
    @override_settings(**PAYPAL_SETTINGS)
    def test_converts_at_the_configured_rate(self):
        self.assertEqual(paypal_amount(Decimal('3000')), (Decimal('5.00'), 'USD'))

    @override_settings(**PAYPAL_SETTINGS)
    def test_rounds_half_up_to_cents(self):
        # 1 XAF / 600 = 0.001666 -> too small; 3 XAF-ish values round to cents
        self.assertEqual(paypal_amount(Decimal('3001'))[0], Decimal('5.00'))   # 5.00166
        self.assertEqual(paypal_amount(Decimal('3003'))[0], Decimal('5.01'))   # 5.005 rounds up

    @override_settings(**{**PAYPAL_SETTINGS, 'STORE_CURRENCY': 'USD'})
    def test_same_currency_needs_no_exchange_rate(self):
        self.assertEqual(paypal_amount(Decimal('12.345')), (Decimal('12.35'), 'USD'))

    @override_settings(**{**PAYPAL_SETTINGS, 'PAYPAL_EXCHANGE_RATE': ''})
    def test_missing_rate_is_a_configuration_error_not_a_guess(self):
        with self.assertRaises(PaymentConfigError):
            paypal_amount(Decimal('3000'))

    @override_settings(**{**PAYPAL_SETTINGS, 'PAYPAL_EXCHANGE_RATE': 'abc'})
    def test_garbage_rate_is_a_configuration_error(self):
        with self.assertRaises(PaymentConfigError):
            paypal_amount(Decimal('3000'))

    @override_settings(**{**PAYPAL_SETTINGS, 'PAYPAL_EXCHANGE_RATE': '-5'})
    def test_negative_rate_is_a_configuration_error(self):
        with self.assertRaises(PaymentConfigError):
            paypal_amount(Decimal('3000'))

    @override_settings(**{**PAYPAL_SETTINGS, 'PAYPAL_RECEIVER_EMAIL': ''})
    def test_missing_receiver_email_is_a_configuration_error(self):
        with self.assertRaises(PaymentConfigError):
            paypal_amount(Decimal('3000'))

    @override_settings(**PAYPAL_SETTINGS)
    def test_amounts_below_one_cent_are_refused(self):
        with self.assertRaises(PaymentConfigError):
            paypal_amount(Decimal('1'))


class EmptyCartRedirectTests(TestCase):
    def test_checkout_and_billing_with_an_empty_cart_go_to_the_cart_page(self):
        self.assertRedirects(self.client.get(reverse('checkout')), reverse('cart_summary'),
                             fetch_redirect_response=False)
        self.assertRedirects(self.client.post(reverse('billing_info'), {}), reverse('cart_summary'),
                             fetch_redirect_response=False)
