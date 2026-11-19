"""Editing, deleting and browsing blog posts by category/tag, and what editors may do."""
from django.contrib.auth.models import Permission, User
from django.test import TestCase
from django.urls import reverse

from blog.models import BlogCategory, BlogPost, BlogTag
from blog.permissions import can_delete_post, can_edit_post, can_publish, can_view_post

PASSWORD = 'pw-Strong-123'


def grant(user, *codenames):
    user.user_permissions.add(*Permission.objects.filter(codename__in=codenames, content_type__app_label='blog'))
    return User.objects.get(pk=user.pk)  # drop the cached permission set


class ManagementTestCase(TestCase):
    def setUp(self):
        self.category = BlogCategory.objects.create(name='Health')
        self.author = grant(User.objects.create_user('author', 'a@example.com', PASSWORD), 'add_blogpost')
        self.editor = grant(User.objects.create_user('editor', 'e@example.com', PASSWORD),
                            'change_blogpost', 'delete_blogpost')
        self.reader = User.objects.create_user('reader', 'r@example.com', PASSWORD)
        self.post = BlogPost.objects.create(title='Original', content='<p>x</p>', status='published',
                                            author=self.author, category=self.category)

    def form_data(self, **overrides):
        return {'title': 'Changed', 'content': '<p>new</p>', 'category': self.category.pk,
                'status': 'published', **overrides}


class UpdateTests(ManagementTestCase):
    def url(self):
        return reverse('blog:post_update', args=[self.post.slug])

    def test_author_can_open_and_save_the_edit_form(self):
        self.client.force_login(self.author)
        self.assertEqual(self.client.get(self.url()).status_code, 200)
        response = self.client.post(self.url(), self.form_data())
        self.post.refresh_from_db()
        self.assertEqual(self.post.title, 'Changed')
        self.assertRedirects(response, self.post.get_absolute_url())

    def test_editor_can_edit_someone_elses_post(self):
        self.client.force_login(self.editor)
        self.client.post(self.url(), self.form_data())
        self.post.refresh_from_db()
        self.assertEqual(self.post.title, 'Changed')

    def test_author_who_lost_publishing_rights_cannot_edit(self):
        self.author.user_permissions.clear()
        self.client.force_login(User.objects.get(pk=self.author.pk))
        self.client.post(self.url(), self.form_data())
        self.post.refresh_from_db()
        self.assertEqual(self.post.title, 'Original')

    def test_edited_content_is_sanitized_too(self):
        self.client.force_login(self.author)
        self.client.post(self.url(), self.form_data(content='<p>ok</p><script>alert(1)</script>'))
        self.post.refresh_from_db()
        self.assertNotIn('<script>', self.post.content)

    def test_invalid_edit_redisplays_the_form_without_saving(self):
        self.client.force_login(self.author)
        response = self.client.post(self.url(), self.form_data(title=''))
        self.assertEqual(response.status_code, 200)
        self.post.refresh_from_db()
        self.assertEqual(self.post.title, 'Original')

    def test_slug_stays_stable_when_the_title_is_edited(self):
        slug = self.post.slug
        self.client.force_login(self.author)
        self.client.post(self.url(), self.form_data())
        self.post.refresh_from_db()
        self.assertEqual(self.post.slug, slug)  # links and bookmarks keep working

    def test_readers_and_anonymous_visitors_cannot_open_the_edit_form(self):
        self.assertEqual(self.client.get(self.url()).status_code, 302)
        self.client.force_login(self.reader)
        self.assertRedirects(self.client.get(self.url()), reverse('blog:post_list'))


class DeleteTests(ManagementTestCase):
    def url(self):
        return reverse('blog:post_delete', args=[self.post.slug])

    def test_confirmation_page_does_not_delete(self):
        self.client.force_login(self.author)
        self.assertEqual(self.client.get(self.url()).status_code, 200)
        self.assertTrue(BlogPost.objects.filter(pk=self.post.pk).exists())

    def test_editor_with_delete_permission_can_delete(self):
        self.client.force_login(self.editor)
        self.client.post(self.url())
        self.assertFalse(BlogPost.objects.filter(pk=self.post.pk).exists())

    def test_readers_cannot_open_the_delete_page(self):
        self.client.force_login(self.reader)
        self.assertRedirects(self.client.get(self.url()), reverse('blog:post_list'))


class CreateTests(ManagementTestCase):
    def test_author_sees_the_create_form(self):
        self.client.force_login(self.author)
        self.assertEqual(self.client.get(reverse('blog:post_create')).status_code, 200)

    def test_invalid_post_redisplays_the_form(self):
        self.client.force_login(self.author)
        response = self.client.post(reverse('blog:post_create'), self.form_data(title=''))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(BlogPost.objects.count(), 1)

    def test_new_post_is_credited_to_the_signed_in_author(self):
        self.client.force_login(self.author)
        self.client.post(reverse('blog:post_create'), self.form_data(title='Brand new'))
        self.assertEqual(BlogPost.objects.get(title='Brand new').author, self.author)

    def test_readers_are_turned_back_from_the_create_form(self):
        self.client.force_login(self.reader)
        self.assertRedirects(self.client.get(reverse('blog:post_create')), reverse('blog:post_list'))


class BrowseTests(ManagementTestCase):
    def test_category_page_lists_published_posts_only(self):
        BlogPost.objects.create(title='Hidden draft', content='x', status='draft',
                                author=self.author, category=self.category)
        response = self.client.get(reverse('blog:category_posts', args=[self.category.slug]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual([p.title for p in response.context['posts']], ['Original'])

    def test_tag_page_lists_published_posts_only(self):
        tag = BlogTag.objects.create(name='Tips')
        self.post.tags.add(tag)
        draft = BlogPost.objects.create(title='Draft tagged', content='x', status='draft',
                                        author=self.author, category=self.category)
        draft.tags.add(tag)
        response = self.client.get(reverse('blog:tag_posts', args=[tag.slug]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual([p.title for p in response.context['posts']], ['Original'])

    def test_unknown_category_or_tag_is_404(self):
        self.assertEqual(self.client.get(reverse('blog:category_posts', args=['nope'])).status_code, 404)
        self.assertEqual(self.client.get(reverse('blog:tag_posts', args=['nope'])).status_code, 404)

    def test_list_pagination_tolerates_bad_page_numbers(self):
        for page in ('junk', '999', '0'):
            self.assertEqual(self.client.get(reverse('blog:post_list'), {'page': page}).status_code, 200, page)


class PermissionHelperTests(ManagementTestCase):
    def test_anonymous_users_can_do_nothing_but_read_published(self):
        from django.contrib.auth.models import AnonymousUser
        anon = AnonymousUser()
        self.assertFalse(can_publish(anon))
        self.assertFalse(can_edit_post(anon, self.post))
        self.assertFalse(can_delete_post(anon, self.post))
        self.assertTrue(can_view_post(anon, self.post))

    def test_drafts_are_visible_to_author_and_editor_only(self):
        self.post.status = 'draft'
        self.assertTrue(can_view_post(self.author, self.post))
        self.assertTrue(can_view_post(self.editor, self.post))
        self.assertFalse(can_view_post(self.reader, self.post))
