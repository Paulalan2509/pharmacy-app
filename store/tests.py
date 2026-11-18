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


class LoginSecurityTests(TestCase):
    def setUp(self):
        from django.core.cache import cache
        cache.clear()
        self.user = User.objects.create_user('victim', 'victim@example.com', 'pw-Strong-123')

    def attempt(self, password, username='victim', **extra):
        return self.client.post(reverse('login'), {'username': username, 'password': password, **extra})

    def test_account_is_locked_after_repeated_failures_even_for_the_right_password(self):
        for _ in range(5):
            self.attempt('wrong')
        response = self.attempt('pw-Strong-123')
        self.assertNotIn('_auth_user_id', self.client.session)
        self.assertContains(response, 'Too many', status_code=429)

    def test_failures_do_not_reveal_whether_the_account_exists(self):
        real = self.attempt('wrong').content.decode()
        fake = self.attempt('wrong', username='nobody-here').content.decode()
        self.assertIn('Invalid username or password', real)
        self.assertIn('Invalid username or password', fake)

    def test_successful_login_resets_the_counter(self):
        for _ in range(4):
            self.attempt('wrong')
        self.attempt('pw-Strong-123')
        self.client.logout()
        for _ in range(4):
            self.attempt('wrong')
        self.attempt('pw-Strong-123')
        self.assertIn('_auth_user_id', self.client.session)

    def test_next_redirect_is_followed_only_for_this_site(self):
        ok = self.attempt('pw-Strong-123', next='/blog/')
        self.assertRedirects(ok, '/blog/', fetch_redirect_response=False)
        self.client.logout()
        evil = self.attempt('pw-Strong-123', next='https://evil.example/phish')
        self.assertNotIn('evil.example', evil['Location'])

    def test_missing_fields_do_not_crash(self):
        response = self.client.post(reverse('login'), {})
        self.assertEqual(response.status_code, 200)


class UniqueEmailTests(TestCase):
    def setUp(self):
        self.existing = User.objects.create_user('first', 'Taken@Example.com', 'pw-Strong-123')

    def signup(self, email, username='second'):
        return self.client.post(reverse('register'), {
            'username': username, 'first_name': 'A', 'last_name': 'B', 'email': email,
            'password1': 'pw-Strong-123', 'password2': 'pw-Strong-123'})

    def test_signup_rejects_an_email_already_in_use_case_insensitively(self):
        self.signup('taken@example.com')
        self.assertFalse(User.objects.filter(username='second').exists())

    def test_signup_accepts_a_new_email(self):
        self.signup('new@example.com')
        self.assertTrue(User.objects.filter(username='second').exists())

    def test_profile_update_cannot_take_someone_elses_email(self):
        other = User.objects.create_user('other', 'other@example.com', 'pw-Strong-123')
        self.client.force_login(other)
        self.client.post(reverse('update_user'), {'username': 'other', 'email': 'taken@example.com'})
        other.refresh_from_db()
        self.assertEqual(other.email, 'other@example.com')

    def test_profile_update_can_keep_your_own_email(self):
        self.client.force_login(self.existing)
        response = self.client.post(reverse('update_user'), {'username': 'first', 'email': 'Taken@Example.com'})
        self.assertEqual(response.status_code, 302)


class StoreRobustnessTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        from store.models import Category, Product
        cls.cat = Category.objects.create(name='Pain')
        cls.other_cat = Category.objects.create(name='Vitamins')
        for i in range(8):
            Product.objects.create(name=f'Pain {i}', price=Decimal(i + 1), category=cls.cat, description='d', image='uploads/product/x.png')
        Product.objects.create(name='Vit C', price=Decimal('50'), category=cls.other_cat, description='d', image='uploads/product/x.png')

    def names(self, response):
        return [p.name for p in response.context['page_obj']]

    def test_filters_actually_apply_to_the_paginated_list(self):
        response = self.client.get(reverse('pharmacy'), {'category': self.other_cat.pk})
        self.assertEqual(self.names(response), ['Vit C'])

    def test_sorting_applies_to_the_paginated_list(self):
        response = self.client.get(reverse('pharmacy'), {'sort': 'price_desc'})
        self.assertEqual(self.names(response)[0], 'Vit C')

    def test_garbage_price_filters_do_not_crash(self):
        response = self.client.get(reverse('pharmacy'), {'min_price': 'abc', 'max_price': '1e999'})
        self.assertEqual(response.status_code, 200)

    def test_pagination_has_a_stable_order(self):
        first = self.names(self.client.get(reverse('pharmacy'), {'page': 1}))
        second = self.names(self.client.get(reverse('pharmacy'), {'page': 2}))
        self.assertEqual(len(set(first) | set(second)), len(first) + len(second))

    def test_unknown_category_redirects_with_a_message(self):
        response = self.client.get(reverse('category', args=['nope']))
        self.assertEqual(response.status_code, 302)

    def test_invalid_review_does_not_crash(self):
        from store.models import Product
        user = User.objects.create_user('rev', 'rev@example.com', 'pw-Strong-123')
        self.client.force_login(user)
        product = Product.objects.first()
        response = self.client.post(reverse('add_review', args=[product.pk]), {'rating': '', 'review': ''})
        self.assertEqual(response.status_code, 200)
