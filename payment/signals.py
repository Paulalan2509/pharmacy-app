"""PayPal IPN handling.

An order only becomes "paid" here, after django-paypal has verified the
notification with PayPal and the payment details match the order exactly.
"""
import logging

from django.conf import settings
from django.db import transaction
from django.dispatch import receiver
from django.utils import timezone
from paypal.standard.ipn.signals import valid_ipn_received
from paypal.standard.models import ST_PP_COMPLETED, ST_PP_REFUNDED, ST_PP_REVERSED

from .models import Order

logger = logging.getLogger(__name__)


@receiver(valid_ipn_received, dispatch_uid='payment.handle_paypal_ipn')
def handle_paypal_ipn(sender, **kwargs):
    ipn = sender
    status = ipn.payment_status

    if status not in (ST_PP_COMPLETED, ST_PP_REFUNDED, ST_PP_REVERSED):
        logger.info('Ignoring PayPal IPN %s with status %s', ipn.txn_id, status)
        return

    receiver_email = (ipn.receiver_email or '').lower()
    if receiver_email != settings.PAYPAL_RECEIVER_EMAIL.lower():
        logger.warning('PayPal IPN %s ignored: unexpected receiver %s', ipn.txn_id, receiver_email)
        return

    with transaction.atomic():
        order = Order.objects.select_for_update().filter(invoice=ipn.invoice).first()
        if order is None:
            logger.warning('PayPal IPN %s ignored: no order for invoice %s', ipn.txn_id, ipn.invoice)
            return

        if status in (ST_PP_REFUNDED, ST_PP_REVERSED):
            if order.payment_status == Order.PAYMENT_PAID:
                order.payment_status = Order.PAYMENT_REFUNDED
                order.save(update_fields=['payment_status'])
                logger.warning('Order %s marked refunded (PayPal %s)', order.pk, status)
            return

        # Completed: the amount and currency must match what we asked PayPal for.
        if ipn.mc_currency != order.paypal_currency or ipn.mc_gross != order.paypal_amount:
            logger.error(
                'PayPal IPN %s does not match order %s (got %s %s, expected %s %s); not marking paid',
                ipn.txn_id, order.pk, ipn.mc_gross, ipn.mc_currency,
                order.paypal_amount, order.paypal_currency,
            )
            return

        if order.payment_status == Order.PAYMENT_PAID:
            return  # already processed (PayPal can resend notifications)

        order.payment_status = Order.PAYMENT_PAID
        order.paid_at = timezone.now()
        order.paypal_txn_id = ipn.txn_id or ''
        order.save(update_fields=['payment_status', 'paid_at', 'paypal_txn_id'])
        logger.info('Order %s marked paid (PayPal %s)', order.pk, ipn.txn_id)
