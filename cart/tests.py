from decimal import Decimal

from django.test import TestCase, override_settings
from django.urls import reverse

from store.models import Category, Product


@override_settings(CART_MAX_QTY=5)
class CartTests(TestCase):
    def setUp(self):
        category = Category.objects.create(name='Pain')
        self.product = Product.objects.create(name='Ibuprofen', price=Decimal('1500'), category=category,
                                              image='x.jpg')
        self.sale = Product.objects.create(name='Aspirin', price=Decimal('500'), is_sale=True,
                                           sale_price=Decimal('300'), category=category, image='y.jpg')

    def post(self, name, **data):
        return self.client.post(reverse(name), data)

    def cart(self):
        return self.client.session.get('session_key', {})

    def test_add_and_total_use_database_prices(self):
        self.post('cart_add', product_id=self.product.id, product_qty=2)
        self.post('cart_add', product_id=self.sale.id, product_qty=1)
        self.assertEqual(self.cart(), {str(self.product.id): 2, str(self.sale.id): 1})
        response = self.client.get(reverse('cart_summary'))
        self.assertEqual(response.context['totals'], Decimal('3300'))  # 2*1500 + sale 300

    def test_negative_zero_and_junk_quantities_are_rejected(self):
        for bad in ('-5', '0', 'abc', ''):
            response = self.post('cart_add', product_id=self.product.id, product_qty=bad)
            self.assertEqual(response.status_code, 400, bad)
        self.assertEqual(self.cart(), {})

    def test_huge_quantity_is_capped(self):
        self.post('cart_add', product_id=self.product.id, product_qty=999)
        self.assertEqual(self.cart()[str(self.product.id)], 5)

    def test_adding_an_existing_product_increases_quantity_up_to_the_cap(self):
        self.post('cart_add', product_id=self.product.id, product_qty=2)
        self.post('cart_add', product_id=self.product.id, product_qty=2)
        self.assertEqual(self.cart()[str(self.product.id)], 4)
        self.post('cart_add', product_id=self.product.id, product_qty=3)
        self.assertEqual(self.cart()[str(self.product.id)], 5)

    def test_update_rejects_negative_and_unknown_items(self):
        self.post('cart_add', product_id=self.product.id, product_qty=2)
        self.assertEqual(self.post('cart_update', product_id=self.product.id, product_qty=-1).status_code, 400)
        self.assertEqual(self.post('cart_update', product_id=self.sale.id, product_qty=1).status_code, 404)
        self.assertEqual(self.cart()[str(self.product.id)], 2)

    def test_update_and_delete(self):
        self.post('cart_add', product_id=self.product.id, product_qty=2)
        self.post('cart_update', product_id=self.product.id, product_qty=4)
        self.assertEqual(self.cart()[str(self.product.id)], 4)
        self.post('cart_delete', product_id=self.product.id)
        self.assertEqual(self.cart(), {})

    def test_out_of_stock_product_cannot_be_added(self):
        Product.objects.filter(pk=self.product.pk).update(availability_status='Out of Stock')
        response = self.post('cart_add', product_id=self.product.id, product_qty=1)
        self.assertEqual(response.status_code, 409)

    def test_get_requests_are_not_allowed(self):
        self.assertEqual(self.client.get(reverse('cart_add')).status_code, 405)

    def test_browsing_does_not_create_a_session(self):
        self.client.get(reverse('home'))
        self.assertNotIn('sessionid', self.client.cookies)
