from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .models import ForumCategory, ForumReply, ForumThread


class ForumTestCase(TestCase):
    def setUp(self):
        self.category = ForumCategory.objects.create(name='General Health')
        self.author = User.objects.create_user('author', 'a@example.com', 'pw-Strong-123')
        self.other = User.objects.create_user('other', 'o@example.com', 'pw-Strong-123')
        self.thread = ForumThread.objects.create(
            title='Is ibuprofen safe?', content='Asking for a friend', author=self.author, category=self.category)


class PageRenderingTests(ForumTestCase):
    def test_all_forum_pages_render(self):
        reply = ForumReply.objects.create(thread=self.thread, user=self.other, content='Ask a pharmacist.')
        self.client.force_login(self.author)
        urls = [
            reverse('forum:forum_home'),
            reverse('forum:category_detail', args=[self.category.slug]),
            reverse('forum:thread_detail', args=[self.thread.slug]),
            reverse('forum:create_thread', args=[self.category.slug]),
        ]
        for url in urls:
            self.assertEqual(self.client.get(url).status_code, 200, url)
        self.assertContains(self.client.get(urls[2]), reply.content)

    def test_user_content_is_escaped(self):
        ForumReply.objects.create(thread=self.thread, user=self.other, content='<script>alert(1)</script>')
        html = self.client.get(reverse('forum:thread_detail', args=[self.thread.slug])).content.decode()
        self.assertNotIn('<script>alert(1)</script>', html)
        self.assertIn('&lt;script&gt;alert(1)&lt;/script&gt;', html)


class ThreadTests(ForumTestCase):
    def test_duplicate_titles_get_unique_slugs(self):
        again = ForumThread.objects.create(
            title=self.thread.title, content='Same title', author=self.other, category=self.category)
        self.assertNotEqual(again.slug, self.thread.slug)
        self.assertTrue(again.slug.startswith(self.thread.slug))

    def test_symbol_only_title_still_gets_a_slug(self):
        thread = ForumThread.objects.create(title='???', content='x', author=self.other, category=self.category)
        self.assertEqual(thread.slug, 'thread')

    def test_view_counter_increments_without_changing_updated_at(self):
        before = ForumThread.objects.get(pk=self.thread.pk)
        self.client.get(reverse('forum:thread_detail', args=[self.thread.slug]))
        self.client.get(reverse('forum:thread_detail', args=[self.thread.slug]))
        after = ForumThread.objects.get(pk=self.thread.pk)
        self.assertEqual(after.views, before.views + 2)
        self.assertEqual(after.updated_at, before.updated_at)

    def test_creating_a_thread_requires_login_and_redirects_to_the_real_login_page(self):
        url = reverse('forum:create_thread', args=[self.category.slug])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response['Location'].startswith(reverse('login')))

    def test_create_thread(self):
        self.client.force_login(self.other)
        response = self.client.post(reverse('forum:create_thread', args=[self.category.slug]),
                                    {'title': 'New topic', 'content': 'Body'})
        thread = ForumThread.objects.get(title='New topic')
        self.assertRedirects(response, thread.get_absolute_url())
        self.assertEqual(thread.author, self.other)


class ReplyTests(ForumTestCase):
    def test_reply_is_saved(self):
        self.client.force_login(self.other)
        self.client.post(reverse('forum:thread_detail', args=[self.thread.slug]), {'content': 'Hello'})
        self.assertEqual(ForumReply.objects.get().user, self.other)

    def test_anonymous_reply_is_redirected_to_login(self):
        response = self.client.post(reverse('forum:thread_detail', args=[self.thread.slug]), {'content': 'Hi'})
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response['Location'].startswith(reverse('login')))
        self.assertEqual(ForumReply.objects.count(), 0)

    def test_closed_thread_rejects_replies_both_ways(self):
        ForumThread.objects.filter(pk=self.thread.pk).update(status='closed')
        self.client.force_login(self.other)
        self.client.post(reverse('forum:thread_detail', args=[self.thread.slug]), {'content': 'Late'})
        self.client.post(reverse('forum:reply_to_post', args=[self.thread.pk]), {'content': 'Late'})
        self.assertEqual(ForumReply.objects.count(), 0)

    def test_parent_must_belong_to_the_same_thread(self):
        other_thread = ForumThread.objects.create(
            title='Other', content='x', author=self.author, category=self.category)
        foreign = ForumReply.objects.create(thread=other_thread, user=self.author, content='elsewhere')
        self.client.force_login(self.other)
        response = self.client.post(
            reverse('forum:reply_to_comment', args=[self.thread.pk, foreign.pk]), {'content': 'Cross-thread'})
        self.assertEqual(response.status_code, 404)
        self.assertEqual(ForumReply.objects.filter(content='Cross-thread').count(), 0)

    def test_nested_reply_to_a_reply_in_the_same_thread(self):
        parent = ForumReply.objects.create(thread=self.thread, user=self.author, content='first')
        self.client.force_login(self.other)
        self.client.post(reverse('forum:reply_to_comment', args=[self.thread.pk, parent.pk]), {'content': 'child'})
        self.assertEqual(ForumReply.objects.get(content='child').parent, parent)

    def test_reply_endpoint_rejects_get(self):
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(reverse('forum:reply_to_post', args=[self.thread.pk])).status_code, 405)


class MarkSolutionTests(ForumTestCase):
    def setUp(self):
        super().setUp()
        self.reply = ForumReply.objects.create(thread=self.thread, user=self.other, content='Try this')
        self.url = reverse('forum:mark_solution', args=[self.reply.pk])

    def test_get_cannot_change_state(self):
        self.client.force_login(self.author)
        self.assertEqual(self.client.get(self.url).status_code, 405)
        self.reply.refresh_from_db()
        self.assertFalse(self.reply.is_solution)

    def test_thread_author_can_toggle_with_post(self):
        self.client.force_login(self.author)
        self.client.post(self.url)
        self.reply.refresh_from_db()
        self.assertTrue(self.reply.is_solution)
        self.client.post(self.url)
        self.reply.refresh_from_db()
        self.assertFalse(self.reply.is_solution)

    def test_other_users_cannot_mark_a_solution(self):
        self.client.force_login(self.other)
        self.client.post(self.url)
        self.reply.refresh_from_db()
        self.assertFalse(self.reply.is_solution)
