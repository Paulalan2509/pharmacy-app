"""Page-level tests for the storefront: static pages, product detail, reviews, search, categories."""
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from store.models import Category, Product, ProductReview

PASSWORD = 'pw-Strong-123'


def make_product(name='Ibuprofen', price='10', category=None, **extra):
    category = category or Category.objects.get_or_create(name='Pain')[0]
    return Product.objects.create(name=name, price=Decimal(price), category=category,
                                  description=extra.pop('description', 'Relieves pain'),
                                  image='uploads/product/x.png', **extra)


class StaticPageTests(TestCase):
    def test_public_pages_render_for_visitors(self):
        for name in ('home', 'pharmacy', 'contact', 'about', 'faq', 'login', 'register', 'category_summary', 'search'):
            self.assertEqual(self.client.get(reverse(name)).status_code, 200, name)

    def test_public_pages_render_for_signed_in_customers(self):
        self.client.force_login(User.objects.create_user('cust', 'c@example.com', PASSWORD))
        for name in ('home', 'pharmacy', 'contact', 'about', 'faq', 'category_summary'):
            self.assertEqual(self.client.get(reverse(name)).status_code, 200, name)


class ProductPageTests(TestCase):
    def setUp(self):
        self.product = make_product()
        self.user = User.objects.create_user('reviewer', 'r@example.com', PASSWORD)

    def test_unknown_product_is_404(self):
        self.assertEqual(self.client.get(reverse('product', args=[9999])).status_code, 404)

    def test_product_page_shows_the_average_rating(self):
        other = User.objects.create_user('other', 'o@example.com', PASSWORD)
        ProductReview.objects.create(user=self.user, product=self.product, review='ok', rating=4)
        ProductReview.objects.create(user=other, product=self.product, review='great', rating=2)
        response = self.client.get(reverse('product', args=[self.product.pk]))
        self.assertEqual(response.context['average_rating'], 3)

    def test_signed_in_user_can_post_a_review_from_the_product_page(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse('product', args=[self.product.pk]), {'rating': 5, 'review': 'Works well'})
        self.assertRedirects(response, reverse('product', args=[self.product.pk]))
        review = ProductReview.objects.get()
        self.assertEqual((review.user, review.rating), (self.user, 5))

    def test_anonymous_visitors_cannot_post_reviews_there(self):
        self.client.post(reverse('product', args=[self.product.pk]), {'rating': 5, 'review': 'spam'})
        self.assertEqual(ProductReview.objects.count(), 0)

    def test_review_rating_must_be_between_one_and_five(self):
        self.client.force_login(self.user)
        for bad in ('0', '6', 'x'):
            self.client.post(reverse('product', args=[self.product.pk]), {'rating': bad, 'review': 'hmm'})
        self.assertEqual(ProductReview.objects.count(), 0)

    def test_add_review_requires_login(self):
        response = self.client.post(reverse('add_review', args=[self.product.pk]), {'rating': 5, 'review': 'x'})
        self.assertTrue(response['Location'].startswith(reverse('login')))
        self.assertEqual(ProductReview.objects.count(), 0)

    def test_add_review_saves_for_the_signed_in_user(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse('add_review', args=[self.product.pk]), {'rating': 3, 'review': 'fine'})
        self.assertRedirects(response, reverse('product', args=[self.product.pk]))
        self.assertEqual(ProductReview.objects.get().user, self.user)

    def test_review_html_is_escaped(self):
        ProductReview.objects.create(user=self.user, product=self.product, rating=5,
                                     review='<script>alert("x")</script>')
        html = self.client.get(reverse('product', args=[self.product.pk])).content.decode()
        self.assertNotIn('<script>alert("x")</script>', html)


class SearchTests(TestCase):
    def setUp(self):
        make_product('Paracetamol 500', description='fever reducer')
        make_product('Vitamin C', description='immune support')

    def search(self, term):
        return self.client.post(reverse('search'), {'searched': term})

    def test_search_matches_name_and_description_case_insensitively(self):
        self.assertEqual([p.name for p in self.search('PARACET').context['searched']], ['Paracetamol 500'])
        self.assertEqual([p.name for p in self.search('immune').context['searched']], ['Vitamin C'])

    def test_no_match_shows_a_message_not_an_error(self):
        response = self.search('zzzz')
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('searched', response.context)

    def test_post_without_a_search_term_does_not_crash(self):
        self.assertEqual(self.client.post(reverse('search'), {}).status_code, 200)


class CategoryTests(TestCase):
    def test_category_page_lists_only_its_products(self):
        pain = Category.objects.create(name='Pain Relief')
        vit = Category.objects.create(name='Vitamins')
        make_product('Ibu', category=pain)
        make_product('VitC', category=vit)
        response = self.client.get(reverse('category', args=['Pain-Relief']))  # hyphen stands for a space
        self.assertEqual([p.name for p in response.context['products']], ['Ibu'])


class StoreFilterTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cheap = make_product('Cheap', '5')
        cls.pricey = make_product('Pricey', '500', is_sale=True, sale_price=Decimal('400'))

    def names(self, **params):
        return {p.name for p in self.client.get(reverse('pharmacy'), params).context['page_obj']}

    def test_price_range_filters(self):
        self.assertEqual(self.names(min_price='100'), {'Pricey'})
        self.assertEqual(self.names(max_price='100'), {'Cheap'})
        self.assertEqual(self.names(min_price='1', max_price='1000'), {'Cheap', 'Pricey'})

    def test_negative_or_non_numeric_prices_are_ignored(self):
        self.assertEqual(self.names(min_price='-5'), {'Cheap', 'Pricey'})
        self.assertEqual(self.names(max_price='NaN'), {'Cheap', 'Pricey'})

    def test_on_sale_filter(self):
        self.assertEqual(self.names(on_sale='1'), {'Pricey'})

    def test_non_numeric_category_ids_are_ignored(self):
        self.assertEqual(self.names(category='abc'), {'Cheap', 'Pricey'})

    def test_page_beyond_the_end_shows_the_last_page(self):
        self.assertEqual(self.client.get(reverse('pharmacy'), {'page': 99}).status_code, 200)
        self.assertEqual(self.client.get(reverse('pharmacy'), {'page': 'junk'}).status_code, 200)


class BlankSearchTests(TestCase):
    def test_blank_search_does_not_list_every_product(self):
        make_product('Anything')
        response = self.client.post(reverse('search'), {'searched': '   '})
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('searched', response.context)
