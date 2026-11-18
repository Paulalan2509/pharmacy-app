import logging
from functools import wraps

from django.conf import settings
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from paypal.standard.forms import PayPalPaymentsForm

from cart.cart import Cart
from payment.forms import ShippingForm
from payment.models import Order, OrderItem, ShippingAddress
from payment.services import (
    CheckoutError,
    PaymentConfigError,
    cart_total,
    create_pending_order,
    get_cart_lines,
    validate_lines,
)

logger = logging.getLogger(__name__)

PENDING_ORDER_SESSION_KEY = 'pending_order_id'


def superuser_required(view):
    """Restrict a view to superusers; everyone else is sent home."""
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if request.user.is_authenticated and request.user.is_superuser:
            return view(request, *args, **kwargs)
        messages.error(request, "Access Denied")
        return redirect('home')
    return wrapper


def _set_shipped(order_id, shipped, request):
    """Mark an order shipped / not shipped. Only paid orders can be shipped."""
    order = get_object_or_404(Order, id=order_id)
    if shipped and not order.is_paid:
        messages.error(request, "Only paid orders can be marked as shipped.")
        return False
    order.shipped = shipped
    if shipped:
        order.date_shipped = timezone.now()
    order.save(update_fields=['shipped', 'date_shipped'])
    messages.success(request, "Shipping Status Updated")
    return True


@superuser_required
def orders(request, pk):
    order = get_object_or_404(Order, id=pk)
    items = OrderItem.objects.filter(order=order)

    if request.method == 'POST':
        _set_shipped(order.id, request.POST.get('shipping_status') == "true", request)
        return redirect('home')

    return render(request, 'payment/orders.html', {"order": order, "items": items})


@superuser_required
def not_shipped_dash(request):
    if request.method == 'POST':
        _set_shipped(request.POST.get('num'), True, request)
        return redirect('home')

    # Only paid orders are waiting to be shipped.
    orders = Order.objects.filter(shipped=False, payment_status=Order.PAYMENT_PAID)
    return render(request, "payment/not_shipped_dash.html", {"orders": orders})


@superuser_required
def shipped_dash(request):
    if request.method == 'POST':
        _set_shipped(request.POST.get('num'), False, request)
        return redirect('home')

    orders = Order.objects.filter(shipped=True)
    return render(request, "payment/shipped_dash.html", {"orders": orders})


def _render_checkout(request, cart, shipping_form, shipping_user=None):
    context = {
        "cart_products": cart.get_prods,
        "quantities": cart.get_quants,
        "totals": cart.cart_total(),
        "shipping_form": shipping_form,
    }
    if shipping_user is not None:
        context["shipping_user"] = shipping_user
    return render(request, "payment/checkout.html", context)


def checkout(request):
    cart = Cart(request)
    if not len(cart):
        messages.warning(request, "Your cart is empty.")
        return redirect('cart_summary')

    if request.user.is_authenticated:
        # Use the user's saved shipping address, creating one if they have none yet.
        shipping_user = ShippingAddress.objects.filter(user=request.user).first()
        if shipping_user is None:
            shipping_user = ShippingAddress.objects.create(user=request.user)
            messages.warning(request,
                             "A new shipping address has been created for you. Please update it with your information.")
        return _render_checkout(request, cart, ShippingForm(instance=shipping_user), shipping_user)

    return _render_checkout(request, cart, ShippingForm())


def billing_info(request):
    """Validate shipping details, create a pending order and show the PayPal button."""
    if request.method != 'POST':
        return redirect('checkout')

    cart = Cart(request)
    if not len(cart):
        messages.warning(request, "Your cart is empty.")
        return redirect('cart_summary')

    shipping_form = ShippingForm(request.POST)
    if not shipping_form.is_valid():
        messages.error(request, "Please correct the shipping information below.")
        shipping_user = None
        if request.user.is_authenticated:
            shipping_user = ShippingAddress.objects.filter(user=request.user).first()
        return _render_checkout(request, cart, shipping_form, shipping_user)

    shipping_data = shipping_form.cleaned_data
    lines = get_cart_lines(cart)

    try:
        order = create_pending_order(
            user=request.user,
            shipping_data=shipping_data,
            lines=lines,
            replace_order_id=request.session.get(PENDING_ORDER_SESSION_KEY),
        )
    except CheckoutError as error:
        messages.error(request, str(error))
        return redirect('cart_summary')
    except PaymentConfigError as error:
        logger.error('PayPal checkout unavailable: %s', error)
        messages.error(request, "Online payment is temporarily unavailable. Please try again later.")
        return redirect('checkout')

    request.session[PENDING_ORDER_SESSION_KEY] = order.pk

    paypal_form = PayPalPaymentsForm(initial={
        'business': settings.PAYPAL_RECEIVER_EMAIL,
        'amount': order.paypal_amount,
        'currency_code': order.paypal_currency,
        'item_name': f'PharmaHope order #{order.pk}',
        'invoice': order.invoice,
        'no_shipping': '2',
        'notify_url': request.build_absolute_uri(reverse('paypal-ipn')),
        'return': request.build_absolute_uri(reverse('payment_success')),
        'cancel_return': request.build_absolute_uri(reverse('payment_failed')),
    })

    return render(request, "payment/billing_info.html", {
        "paypal_form": paypal_form,
        "order": order,
        "lines": lines,
        "totals": order.amount_paid,
        "shipping_info": shipping_data,
    })


def payment_success(request):
    """Where PayPal sends the customer back. This does NOT confirm payment.

    Only the verified IPN notification marks an order paid, so we just report
    the order's real status here. The cart is emptied because its contents now
    live in the order.
    """
    order = None
    order_id = request.session.get(PENDING_ORDER_SESSION_KEY)
    if order_id:
        order = Order.objects.filter(pk=order_id).first()
        Cart(request).clear()
        request.session.pop(PENDING_ORDER_SESSION_KEY, None)
    return render(request, "payment/payment_success.html", {"order": order})


def payment_failed(request):
    return render(request, "payment/payment_failed.html", {})
