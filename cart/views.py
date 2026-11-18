from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_POST

from store.models import Product

from .cart import Cart


def _error(message, status=400):
    return JsonResponse({'error': message}, status=status)


def _parse_product_and_quantity(request, require_quantity=True):
    """Return (product_id, quantity) from POST data or raise ValueError."""
    product_id = int(request.POST.get('product_id'))
    quantity = Cart.clean_quantity(request.POST.get('product_qty')) if require_quantity else None
    return product_id, quantity


def cart_summary(request):
    # Get the cart
    cart = Cart(request)
    cart_products = cart.get_prods
    quantities = cart.get_quants
    totals = cart.cart_total()
    return render(request, "cart_summary.html",
                  {"cart_products": cart_products, "quantities": quantities, "totals": totals})


@require_POST
def cart_add(request):
    cart = Cart(request)
    try:
        product_id, quantity = _parse_product_and_quantity(request)
    except (TypeError, ValueError):
        return _error('Invalid product or quantity.')

    product = get_object_or_404(Product, id=product_id)
    if product.availability_status == 'Out of Stock':
        return _error('This product is out of stock.', status=409)

    line_quantity = cart.add(product=product, quantity=quantity)
    messages.success(request, "Product Added To Cart...")
    return JsonResponse({'qty': len(cart), 'line_qty': line_quantity})


@require_POST
def cart_delete(request):
    cart = Cart(request)
    try:
        product_id, _ = _parse_product_and_quantity(request, require_quantity=False)
    except (TypeError, ValueError):
        return _error('Invalid product.')

    cart.delete(product=product_id)
    messages.success(request, "Item Deleted From Shopping Cart...")
    return JsonResponse({'product': product_id})


@require_POST
def cart_update(request):
    cart = Cart(request)
    try:
        product_id, quantity = _parse_product_and_quantity(request)
    except (TypeError, ValueError):
        return _error('Invalid product or quantity.')

    if str(product_id) not in cart.get_quants():
        return _error('That product is not in your cart.', status=404)

    cart.update(product=product_id, quantity=quantity)
    messages.success(request, "Your Cart Has Been Updated...")
    return JsonResponse({'qty': quantity})
