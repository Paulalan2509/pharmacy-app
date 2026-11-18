from django import template
from django.utils.safestring import mark_safe

from blog.sanitizers import render_comment as _render_comment
from blog.sanitizers import sanitize_post_html

register = template.Library()


@register.filter
def sanitize_html(value):
    """Render untrusted editor HTML safely (replaces `|safe`)."""
    return mark_safe(sanitize_post_html(value))


@register.filter
def render_comment(value):
    """Render a Markdown comment to sanitized HTML."""
    return mark_safe(_render_comment(value))
