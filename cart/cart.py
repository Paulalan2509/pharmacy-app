import json
import logging
from decimal import Decimal

from django.conf import settings

from store.models import Product, Profile

logger = logging.getLogger(__name__)

SESSION_KEY = 'session_key'


class Cart:
    """A session-backed shopping cart: {"<product id>": <quantity>}.

    For signed-in users the cart is also saved on their profile so it survives
    logging out. Quantities are always validated and capped (see clean_quantity).
    """

    def __init__(self, request):
        self.session = request.session
        self.request = request
        # Don't create a session just because someone viewed a page.
        self.cart = self.session.get(SESSION_KEY, {})

    @staticmethod
    def clean_quantity(value):
        """Return a valid quantity (1..CART_MAX_QTY) or raise ValueError."""
        quantity = int(value)  # raises ValueError/TypeError for junk input
        if quantity < 1:
            raise ValueError('Quantity must be at least 1.')
        return min(quantity, settings.CART_MAX_QTY)

    def _commit(self):
        """Persist the cart to the session and, for signed-in users, to their profile."""
        self.session[SESSION_KEY] = self.cart
        self.session.modified = True
        if self.request.user.is_authenticated:
            Profile.objects.filter(user_id=self.request.user.id).update(old_cart=json.dumps(self.cart))

    def db_add(self, product, quantity):
        """Restore one saved item (used when a user logs in). Invalid entries are skipped."""
        try:
            product_id = str(int(product))
            quantity = self.clean_quantity(quantity)
        except (TypeError, ValueError):
            logger.warning('Skipping invalid saved cart entry: %r x %r', product, quantity)
            return
        if product_id not in self.cart:
            self.cart[product_id] = quantity
        self._commit()

    def add(self, product, quantity):
        """Add to the cart; adding a product that is already there increases its quantity."""
        product_id = str(product.id)
        quantity = self.clean_quantity(quantity)
        self.cart[product_id] = min(self.cart.get(product_id, 0) + quantity, settings.CART_MAX_QTY)
        self._commit()
        return self.cart[product_id]

    def update(self, product, quantity):
        product_id = str(product)
        self.cart[product_id] = self.clean_quantity(quantity)
        self._commit()
        return self.cart

    def delete(self, product):
        product_id = str(product)
        if product_id in self.cart:
            del self.cart[product_id]
        self._commit()

    def clear(self):
        self.cart = {}
        self._commit()

    def cart_total(self):
        quantities = self.get_quants()
        total = Decimal('0')
        for product in self.get_prods():
            quantity = quantities.get(str(product.id), 0)
            price = product.sale_price if product.is_sale else product.price
            total += price * quantity
        return total

    def __len__(self):
        return len(self.cart)

    def get_prods(self):
        # Look the products up from the ids in the cart
        return Product.objects.filter(id__in=self.cart.keys())

    def get_quants(self):
        return self.cart
