"""HTML sanitizing for user-supplied blog content.

Blog posts are written in a rich-text editor (TinyMCE), so they are stored and shown as HTML.
That HTML is untrusted: it must never be rendered with `|safe` as-is. Everything goes through
nh3 (an allowlist sanitizer) first, which removes <script>, event handlers such as onerror=,
javascript: links, iframes and inline styles while keeping normal formatting.
"""
import html

import markdown
import nh3

# Comments are Markdown from readers: allow basic text formatting and links, but no images,
# tables or headings.
COMMENT_TAGS = {'p', 'br', 'strong', 'em', 'b', 'i', 'code', 'pre', 'blockquote', 'ul', 'ol', 'li', 'a'}
COMMENT_ATTRIBUTES = {'a': {'href'}}
COMMENT_LINK_REL = 'noopener noreferrer nofollow ugc'


def sanitize_post_html(value):
    """Clean editor HTML (posts). Safe to mark_safe the result."""
    return nh3.clean(value or '')


def render_comment(value):
    """Render a Markdown comment to sanitized HTML. Safe to mark_safe the result."""
    rendered = markdown.markdown(value or '', extensions=['nl2br'])
    return nh3.clean(
        rendered,
        tags=COMMENT_TAGS,
        attributes=COMMENT_ATTRIBUTES,
        link_rel=COMMENT_LINK_REL,
    )


def plain_text(value):
    """Strip all HTML (including the contents of <script>/<style>) and return plain text."""
    return html.unescape(nh3.clean(value or '', tags=set()))
