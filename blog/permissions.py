"""Who may do what on the blog.

Publishing is limited to trusted people: superusers, or anyone granted the "Can add blog post"
permission in the admin (the easiest way is a "Blog authors" group). Ordinary registered
customers can read and comment, but not publish.
"""


def can_publish(user):
    return user.is_authenticated and user.has_perm('blog.add_blogpost')


def can_edit_post(user, post):
    """Authors may edit their own posts while they still hold publishing rights; editors may edit any."""
    if not user.is_authenticated:
        return False
    if user.has_perm('blog.change_blogpost'):
        return True
    return user == post.author and can_publish(user)


def can_delete_post(user, post):
    return user.is_authenticated and (user == post.author or user.has_perm('blog.delete_blogpost'))


def can_view_post(user, post):
    """Published posts are public; drafts and archived posts only to their author and editors."""
    if post.status == 'published':
        return True
    return user.is_authenticated and (user == post.author or user.has_perm('blog.change_blogpost'))
