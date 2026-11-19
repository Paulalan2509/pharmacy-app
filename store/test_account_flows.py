"""Registration, logout, profile/password/info updates and saved-cart restore on login."""
import json
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from payment.models import ShippingAddress
from store.models import Category, Product, Profile

PASSWORD = 'pw-Strong-123'
NEW_PASSWORD = 'another-Strong-456'


class RegistrationTests(TestCase):
    def register(self, **overrides):
        data = {'username': 'newbie', 'first_name': 'New', 'last_name': 'Bie', 'email': 'new@example.com',
                'password1': PASSWORD, 'password2': PASSWORD, **overrides}
        return self.client.post(reverse('register'), data)

    def test_registration_creates_user_and_profile_and_logs_in(self):
        response = self.register()
        self.assertRedirects(response, reverse('update_info'), fetch_redirect_response=False)
        user = User.objects.get(username='newbie')
        self.assertTrue(Profile.objects.filter(user=user).exists())
        self.assertEqual(int(self.client.session['_auth_user_id']), user.pk)

    def test_mismatched_passwords_create_nothing(self):
        self.register(password2='different-Pass-1')
        self.assertFalse(User.objects.filter(username='newbie').exists())

    def test_weak_password_is_rejected(self):
        self.register(password1='12345678', password2='12345678')
        self.assertFalse(User.objects.filter(username='newbie').exists())

    def test_duplicate_username_is_rejected(self):
        User.objects.create_user('newbie', 'x@example.com', PASSWORD)
        self.register()
        self.assertEqual(User.objects.filter(username='newbie').count(), 1)


class LogoutTests(TestCase):
    def test_logout_ends_the_session(self):
        self.client.force_login(User.objects.create_user('u', 'u@example.com', PASSWORD))
        response = self.client.get(reverse('logout'))
        self.assertRedirects(response, reverse('home'))
        self.assertNotIn('_auth_user_id', self.client.session)


class AccountPagesRequireLoginTests(TestCase):
    def test_anonymous_visitors_are_sent_home(self):
        for name in ('update_user', 'update_password', 'update_info'):
            response = self.client.get(reverse(name))
            self.assertRedirects(response, reverse('home'), msg_prefix=name)


class ProfileUpdateTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('ada', 'ada@example.com', PASSWORD)
        self.client.force_login(self.user)

    def test_update_user_changes_name_and_email_and_keeps_you_signed_in(self):
        response = self.client.post(reverse('update_user'), {
            'username': 'ada', 'first_name': 'Ada', 'last_name': 'Lovelace', 'email': 'ada2@example.com'})
        self.assertRedirects(response, reverse('home'))
        self.user.refresh_from_db()
        self.assertEqual((self.user.first_name, self.user.email), ('Ada', 'ada2@example.com'))
        self.assertEqual(self.client.get(reverse('update_user')).status_code, 200)

    def test_cannot_take_an_existing_username(self):
        User.objects.create_user('grace', 'grace@example.com', PASSWORD)
        self.client.post(reverse('update_user'), {'username': 'grace', 'email': 'ada@example.com'})
        self.user.refresh_from_db()
        self.assertEqual(self.user.username, 'ada')

    def test_update_info_saves_profile_and_shipping_details(self):
        response = self.client.post(reverse('update_info'), {
            'phone_number': '123', 'address_1': '1 Main St', 'city': 'Douala', 'country': 'Cameroon',
            'shipping_full_name': 'Ada L', 'shipping_email': 'ada@example.com',
            'shipping_address1': '1 Main St', 'shipping_city': 'Douala',
            'shipping_country': 'Cameroon', 'shipping_phone': '123'})
        self.assertRedirects(response, reverse('home'))
        self.assertEqual(Profile.objects.get(user=self.user).city, 'Douala')
        self.assertEqual(ShippingAddress.objects.get(user=self.user).shipping_city, 'Douala')

    def test_update_info_with_missing_shipping_fields_saves_nothing(self):
        self.client.post(reverse('update_info'), {'city': 'Douala'})
        self.assertEqual(Profile.objects.get(user=self.user).city, '')

    def test_update_info_creates_a_shipping_address_once(self):
        self.client.get(reverse('update_info'))
        self.client.get(reverse('update_info'))
        self.assertEqual(ShippingAddress.objects.filter(user=self.user).count(), 1)


class PasswordChangeTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('ada', 'ada@example.com', PASSWORD)
        self.client.force_login(self.user)

    def test_password_can_be_changed_and_session_survives(self):
        response = self.client.post(reverse('update_password'),
                                    {'new_password1': NEW_PASSWORD, 'new_password2': NEW_PASSWORD})
        self.assertRedirects(response, reverse('update_user'))
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(NEW_PASSWORD))
        self.assertEqual(self.client.get(reverse('update_user')).status_code, 200)

    def test_mismatch_or_weak_password_changes_nothing(self):
        for first, second in ((NEW_PASSWORD, 'different-Pass-9'), ('12345678', '12345678')):
            self.client.post(reverse('update_password'), {'new_password1': first, 'new_password2': second})
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(PASSWORD))

    def test_form_page_renders(self):
        self.assertEqual(self.client.get(reverse('update_password')).status_code, 200)


class SavedCartRestoreTests(TestCase):
    def setUp(self):
        cache.clear()
        category = Category.objects.create(name='Pain')
        self.product = Product.objects.create(name='Ibu', price=Decimal('10'), category=category, image='x.png')
        self.user = User.objects.create_user('ada', 'ada@example.com', PASSWORD)

    def login(self):
        return self.client.post(reverse('login'), {'username': 'ada', 'password': PASSWORD})

    def test_saved_cart_comes_back_on_login(self):
        Profile.objects.filter(user=self.user).update(old_cart=json.dumps({str(self.product.pk): 2}))
        self.login()
        self.assertEqual(self.client.session['session_key'], {str(self.product.pk): 2})

    def test_corrupt_saved_cart_does_not_block_login(self):
        Profile.objects.filter(user=self.user).update(old_cart='{not json')
        response = self.login()
        self.assertEqual(response.status_code, 302)
        self.assertIn('_auth_user_id', self.client.session)

    def test_saved_cart_with_junk_entries_keeps_the_valid_ones(self):
        Profile.objects.filter(user=self.user).update(
            old_cart=json.dumps({str(self.product.pk): 1, 'abc': 3, '7': 'lots'}))
        self.login()
        self.assertEqual(self.client.session['session_key'], {str(self.product.pk): 1})

    def test_remember_me_sets_a_two_week_session(self):
        self.client.post(reverse('login'), {'username': 'ada', 'password': PASSWORD, 'remember': 'on'})
        self.assertEqual(self.client.session.get_expiry_age(), 1209600)

    def test_without_remember_me_the_session_ends_with_the_browser(self):
        self.login()
        self.assertTrue(self.client.session.get_expire_at_browser_close())
