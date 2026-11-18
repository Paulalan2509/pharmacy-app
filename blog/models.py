from django.db import models
from django.contrib.auth.models import User
from django.utils.text import Truncator, slugify
from django.urls import reverse
from django.conf import settings
from pharmahope.slugs import unique_slug
from store.models import Profile

from .sanitizers import plain_text


class BlogCategory(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    slug = models.SlugField(unique=True, max_length=120)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name_plural = "Blog Categories"


class BlogPost(models.Model):
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('published', 'Published'),
        ('archived', 'Archived')
    ]

    title = models.CharField(max_length=255)
    slug = models.SlugField(unique=True, max_length=280)
    content = models.TextField()
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='blog_posts')
    category = models.ForeignKey(BlogCategory, on_delete=models.SET_NULL, null=True, related_name='posts')

    featured_image = models.ImageField(upload_to='blog/featured_images/', null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    published_at = models.DateTimeField(null=True, blank=True)

    meta_description = models.CharField(max_length=320, blank=True)
    tags = models.ManyToManyField('BlogTag', blank=True)

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slug(self, self.title, fallback='post')
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse('blog:post_detail', kwargs={'slug': self.slug})

    @property
    def excerpt(self):
        """A short plain-text summary for post cards (all HTML removed)."""
        return Truncator(plain_text(self.content)).words(30)

    def __str__(self):
        return self.title

    def get_author_profile_picture(self):
        """URL of the author's profile picture, or '' when they have none."""
        try:
            image = self.author.profile.image
            return image.url if image else ''
        except (Profile.DoesNotExist, ValueError):
            return ''


class BlogTag(models.Model):
    name = models.CharField(max_length=50, unique=True)
    slug = models.SlugField(unique=True)

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class BlogComment(models.Model):
    post = models.ForeignKey(BlogPost, on_delete=models.CASCADE, related_name='comments')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    is_approved = models.BooleanField(default=False)
    parent = models.ForeignKey('self', null=True, blank=True, on_delete=models.CASCADE, related_name='replies')

    def __str__(self):
        return f"Comment by {self.user.username} on {self.post.title}"
