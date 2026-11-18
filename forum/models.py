from django.db import models
from django.contrib.auth.models import User
from django.utils.text import slugify

from pharmahope.slugs import unique_slug
from django.urls import reverse


class ForumCategory(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    slug = models.SlugField(unique=True, max_length=120)
    order = models.PositiveIntegerField(default=0)

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name_plural = "Forum Categories"
        ordering = ['order']


class ForumThread(models.Model):
    STATUS_CHOICES = [
        ('open', 'Open'),
        ('closed', 'Closed'),
        ('pinned', 'Pinned')
    ]

    title = models.CharField(max_length=255)
    slug = models.SlugField(unique=True, max_length=280)
    content = models.TextField()
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='forum_threads')
    category = models.ForeignKey(ForumCategory, on_delete=models.CASCADE, related_name='threads')

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='open')
    views = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slug(self, self.title, fallback='thread')
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse('forum:thread_detail', kwargs={'slug': self.slug})

    @property
    def is_closed(self):
        return self.status == 'closed'

    def __str__(self):
        return self.title


class ForumReply(models.Model):
    thread = models.ForeignKey(ForumThread, on_delete=models.CASCADE, related_name='replies')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    is_solution = models.BooleanField(default=False)
    parent = models.ForeignKey('self', null=True, blank=True, on_delete=models.CASCADE, related_name='child_replies')

    def __str__(self):
        return f"Reply by {self.user.username} on {self.thread.title}"
