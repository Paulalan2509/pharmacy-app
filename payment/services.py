"""Server-side checkout logic: pricing, currency conversion and order creation.

Nothing in here trusts the browser. Prices, quantities and totals always come
from the database and the session cart.
"""
import logging
import uuid
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from django.conf import settings
from django.db import transaction

from .models import Order, OrderItem

logger = logging.getLogger(__name__)

TWO_PLACES = Decimal('0.01')


class PaymentConfigError(Exception):
    """Online payment cannot be started because the shop is not configured for it."""


class CheckoutError(Exception):
    """The cart cannot be checked out (for example an item is out of stock)."""


@dataclass
class CartLine:
    product: object
    quantity: int
    unit_price: Decimal

    @property
    def line_total(self):
        return self.unit_price * self.quantity


def get_cart_lines(cart):
    """Return the cart's contents as priced lines, using current database prices."""
    quantities = cart.get_quants()
    lines = []
    for product in cart.get_prods():
        try:
            quantity = int(quantities.get(str(product.id), 0))
        except (TypeError, ValueError):
            continue
        if quantity < 1:
            continue
        unit_price = product.sale_price if product.is_sale else product.price
        lines.append(CartLine(product=product, quantity=quantity, unit_price=unit_price))
    return lines


def cart_total(lines):
    return sum((line.line_total for line in lines), Decimal('0'))


def validate_lines(lines):
    """Raise CheckoutError if the cart is empty or contains something we cannot sell."""
    if not lines:
        raise CheckoutError('Your cart is empty.')
    for line in lines:
        if line.product.availability_status == 'Out of Stock':
            raise CheckoutError(f'"{line.product.name}" is out of stock. Please remove it from your cart.')
        if line.quantity > settings.CART_MAX_QTY:
            raise CheckoutError(
                f'You can order at most {settings.CART_MAX_QTY} of "{line.product.name}".'
            )
        if line.unit_price <= 0:
            raise CheckoutError(f'"{line.product.name}" cannot be ordered right now.')


def paypal_amount(total):
    """Convert a store-currency total into the amount to request from PayPal.

    PayPal does not support every currency (XAF/Fcfa is not supported), so when
    the store currency differs from PAYPAL_CURRENCY a configured exchange rate is
    required. We refuse to guess: a missing rate would charge the wrong amount.
    """
    if not settings.PAYPAL_RECEIVER_EMAIL:
        raise PaymentConfigError('PAYPAL_RECEIVER_EMAIL is not configured.')

    total = Decimal(total)
    store_currency = settings.STORE_CURRENCY.upper()
    paypal_currency = settings.PAYPAL_CURRENCY.upper()

    if store_currency == paypal_currency:
        rate = Decimal('1')
    else:
        try:
            rate = Decimal(str(settings.PAYPAL_EXCHANGE_RATE).strip())
        except (InvalidOperation, ValueError):
            rate = Decimal('0')
        if rate <= 0:
            raise PaymentConfigError(
                f'PAYPAL_EXCHANGE_RATE ({store_currency} per 1 {paypal_currency}) is not configured.'
            )

    amount = (total / rate).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
    if amount < TWO_PLACES:
        raise PaymentConfigError('The order total is too small to pay with PayPal.')
    return amount, paypal_currency


def format_shipping_address(data):
    parts = [
        data.get('shipping_address1', ''),
        data.get('shipping_address2', ''),
        data.get('shipping_city', ''),
        data.get('shipping_region') or '',
        data.get('shipping_zipcode') or '',
        data.get('shipping_country', ''),
    ]
    address = '\n'.join(part for part in parts if part)
    phone = data.get('shipping_phone')
    if phone:
        address += f'\nPhone: {phone}'
    return address


@transaction.atomic
def create_pending_order(*, user, shipping_data, lines, replace_order_id=None):
    """Create an unpaid order and its items from validated shipping data and cart lines.

    The order stays "pending" until PayPal confirms the payment through the IPN
    handler. An earlier still-pending order from the same session is replaced so
    abandoned checkouts do not pile up.
    """
    validate_lines(lines)
    total = cart_total(lines)
    amount, currency = paypal_amount(total)

    if replace_order_id:
        Order.objects.filter(pk=replace_order_id, payment_status=Order.PAYMENT_PENDING).delete()

    order = Order.objects.create(
        user=user if user is not None and user.is_authenticated else None,
        full_name=shipping_data['shipping_full_name'],
        email=shipping_data['shipping_email'],
        shipping_address=format_shipping_address(shipping_data),
        amount_paid=total,
        payment_status=Order.PAYMENT_PENDING,
        invoice=uuid.uuid4().hex,
        paypal_amount=amount,
        paypal_currency=currency,
    )
    OrderItem.objects.bulk_create([
        OrderItem(
            order=order,
            product=line.product,
            product_name=line.product.name,
            user=order.user,
            quantity=line.quantity,
            price=line.unit_price,
        )
        for line in lines
    ])
    return order
