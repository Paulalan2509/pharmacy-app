from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from .models import BlogPost


@receiver(post_save, sender=BlogPost)
def update_published_at(sender, instance, **kwargs):
    """
    Automatically set published_at when a post is published
    """
    if instance.status == 'published' and not instance.published_at:
        instance.published_at = timezone.now()
        instance.save()