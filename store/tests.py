from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from payment.models import Order


class DashboardTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser('boss', 'boss@example.com', 'pw-Strong-123')
        self.customer = User.objects.create_user('cust', 'cust@example.com', 'pw-Strong-123', first_name='Cora')
        Order.objects.create(full_name='Paid', email='p@example.com', shipping_address='a',
                             amount_paid=Decimal('100'), payment_status=Order.PAYMENT_PAID)
        Order.objects.create(full_name='Unpaid', email='u@example.com', shipping_address='a',
                             amount_paid=Decimal('200'))

    def test_dashboard_renders_customers_and_only_lists_paid_orders_to_ship(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'cust@example.com')  # customers table now works
        self.assertEqual([o.full_name for o in response.context['not_shipped_orders']], ['Paid'])

    def test_dashboard_is_superuser_only(self):
        self.client.force_login(self.customer)
        response = self.client.get(reverse('dashboard'))
        self.assertRedirects(response, reverse('home'), fetch_redirect_response=False)


class LoginRedirectTests(TestCase):
    def test_login_required_pages_send_visitors_to_this_sites_login_page(self):
        # Without LOGIN_URL they were sent to Django's default /accounts/login/, which 404s here.
        for name in ('blog:post_create',):
            response = self.client.get(reverse(name))
            self.assertEqual(response.status_code, 302)
            self.assertTrue(response['Location'].startswith(reverse('login')), name)
        self.assertEqual(self.client.get(reverse('login')).status_code, 200)
