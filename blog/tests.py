from django.contrib.auth.models import Permission, User
from django.test import TestCase
from django.urls import reverse

from .models import BlogCategory, BlogComment, BlogPost

XSS_HTML = '<p>Hello <strong>world</strong></p><script>alert("xss")</script><img src="x" onerror="alert(1)">'
PASSWORD = 'pw-Strong-123'


class BlogTestCase(TestCase):
    def setUp(self):
        self.category = BlogCategory.objects.create(name='Health')
        add_perm = Permission.objects.get(codename='add_blogpost')
        self.author = User.objects.create_user('author', 'author@example.com', PASSWORD)
        self.author.user_permissions.add(add_perm)
        self.reader = User.objects.create_user('reader', 'reader@example.com', PASSWORD)
        self.admin = User.objects.create_superuser('boss', 'boss@example.com', PASSWORD)

    def make_post(self, title='A post', status='published', content='<p>Body</p>', author=None):
        return BlogPost.objects.create(
            title=title, content=content, status=status, author=author or self.author, category=self.category)

    def detail_url(self, post):
        return reverse('blog:post_detail', args=[post.slug])


class PostContentSecurityTests(BlogTestCase):
    def test_script_and_event_handlers_are_stripped_when_rendering(self):
        post = self.make_post(content=XSS_HTML)
        html = self.client.get(self.detail_url(post)).content.decode()
        self.assertNotIn('alert("xss")', html)
        self.assertNotIn('onerror', html)
        self.assertIn('<strong>world</strong>', html)  # legitimate formatting survives

    def test_javascript_links_are_removed(self):
        post = self.make_post(content='<a href="javascript:alert(1)">click</a>')
        html = self.client.get(self.detail_url(post)).content.decode()
        self.assertNotIn('javascript:', html)

    def test_content_is_sanitized_when_saved_through_the_form(self):
        self.client.force_login(self.author)
        self.client.post(reverse('blog:post_create'), {
            'title': 'Clean me', 'content': XSS_HTML, 'category': self.category.pk, 'status': 'draft',
        })
        saved = BlogPost.objects.get(title='Clean me')
        self.assertNotIn('<script>', saved.content)
        self.assertNotIn('onerror', saved.content)
        self.assertIn('<strong>world</strong>', saved.content)


class CommentTests(BlogTestCase):
    def setUp(self):
        super().setUp()
        self.post = self.make_post()

    def test_comment_html_is_not_executed(self):
        BlogComment.objects.create(post=self.post, user=self.reader, is_approved=True,
                                   content='<img src=x onerror=alert(1)> <script>alert(2)</script>')
        html = self.client.get(self.detail_url(self.post)).content.decode()
        self.assertNotIn('onerror', html)
        self.assertNotIn('alert(2)', html)

    def test_comment_markdown_is_rendered_safely_on_the_server(self):
        BlogComment.objects.create(post=self.post, user=self.reader, is_approved=True, content='This is **important**')
        self.assertContains(self.client.get(self.detail_url(self.post)), '<strong>important</strong>')

    def test_comment_form_really_submits(self):
        # The old form called preventDefault and only console.log'd, so nothing was ever posted.
        html = self.client.get(self.detail_url(self.post)).content.decode()
        self.assertNotIn('submit.prevent', html)

    def test_anonymous_comment_redirects_to_login_instead_of_crashing(self):
        response = self.client.post(self.detail_url(self.post), {'content': 'hi'})
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response['Location'].startswith(reverse('login')))
        self.assertEqual(BlogComment.objects.count(), 0)

    def test_logged_in_comment_waits_for_approval(self):
        self.client.force_login(self.reader)
        self.client.post(self.detail_url(self.post), {'content': 'Nice post'})
        comment = BlogComment.objects.get()
        self.assertFalse(comment.is_approved)
        self.assertNotContains(self.client.get(self.detail_url(self.post)), 'Nice post')


class VisibilityTests(BlogTestCase):
    def test_drafts_and_archived_posts_are_hidden_from_the_public(self):
        for status in ('draft', 'archived'):
            post = self.make_post(title=f'{status} post', status=status)
            self.assertEqual(self.client.get(self.detail_url(post)).status_code, 404, status)

    def test_drafts_are_hidden_from_other_logged_in_users(self):
        post = self.make_post(status='draft')
        self.client.force_login(self.reader)
        self.assertEqual(self.client.get(self.detail_url(post)).status_code, 404)

    def test_author_and_admin_can_preview_their_drafts(self):
        post = self.make_post(status='draft')
        for user in (self.author, self.admin):
            self.client.force_login(user)
            self.assertEqual(self.client.get(self.detail_url(post)).status_code, 200, user.username)

    def test_list_only_shows_published_posts(self):
        self.make_post(title='Visible', status='published')
        self.make_post(title='Secret draft', status='draft')
        response = self.client.get(reverse('blog:post_list'))
        self.assertContains(response, 'Visible')
        self.assertNotContains(response, 'Secret draft')


class PublishingPermissionTests(BlogTestCase):
    def test_ordinary_registered_users_cannot_publish(self):
        self.client.force_login(self.reader)
        response = self.client.post(reverse('blog:post_create'), {
            'title': 'Spam', 'content': '<p>buy now</p>', 'category': self.category.pk, 'status': 'published'})
        self.assertIn(response.status_code, (302, 403))
        self.assertEqual(BlogPost.objects.count(), 0)

    def test_anonymous_users_are_sent_to_login(self):
        response = self.client.get(reverse('blog:post_create'))
        self.assertTrue(response['Location'].startswith(reverse('login')))

    def test_trusted_author_can_publish(self):
        self.client.force_login(self.author)
        response = self.client.post(reverse('blog:post_create'), {
            'title': 'Real post', 'content': '<p>Hello</p>', 'category': self.category.pk, 'status': 'published'})
        post = BlogPost.objects.get(title='Real post')
        self.assertRedirects(response, post.get_absolute_url())

    def test_only_the_author_can_edit(self):
        post = self.make_post()
        self.client.force_login(self.reader)
        self.client.post(reverse('blog:post_update', args=[post.slug]), {
            'title': 'Hacked', 'content': '<p>x</p>', 'category': self.category.pk, 'status': 'published'})
        post.refresh_from_db()
        self.assertEqual(post.title, 'A post')

    def test_create_post_button_only_shown_to_people_who_can_publish(self):
        self.client.force_login(self.reader)
        self.assertNotContains(self.client.get(reverse('blog:post_list')), reverse('blog:post_create'))
        self.client.force_login(self.author)
        self.assertContains(self.client.get(reverse('blog:post_list')), reverse('blog:post_create'))

    def test_delete_requires_post_and_the_right_person(self):
        post = self.make_post()
        self.client.force_login(self.reader)
        self.client.post(reverse('blog:post_delete', args=[post.slug]))
        self.assertTrue(BlogPost.objects.filter(pk=post.pk).exists())
        self.client.force_login(self.author)
        self.client.post(reverse('blog:post_delete', args=[post.slug]))
        self.assertFalse(BlogPost.objects.filter(pk=post.pk).exists())


class RobustnessTests(BlogTestCase):
    def test_duplicate_titles_get_unique_slugs(self):
        first = self.make_post(title='Same title')
        second = self.make_post(title='Same title')
        self.assertNotEqual(first.slug, second.slug)

    def test_post_detail_renders_for_an_author_without_a_profile_picture(self):
        post = self.make_post()
        self.assertEqual(self.client.get(self.detail_url(post)).status_code, 200)

    def test_cards_show_a_plain_text_excerpt(self):
        self.make_post(title='Excerpt me', content='<p>Short <b>summary</b> here</p><script>x()</script>')
        response = self.client.get(reverse('blog:post_list'))
        self.assertContains(response, 'Short summary here')
        self.assertNotContains(response, 'x()')
