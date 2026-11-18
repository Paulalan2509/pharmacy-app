from django.conf import settings

from .cart import Cart


# Create a context processor so our cart can work on all pages of the site
def cart(request):
    max_qty = settings.CART_MAX_QTY
    return {
        'cart': Cart(request),
        'cart_max_qty': max_qty,
        'qty_choices': range(1, max_qty + 1),
    }
