from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import redirect_to_login
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render

from store.models import Profile

from .forms import BlogCommentForm, BlogPostForm
from .models import BlogCategory, BlogPost, BlogTag
from .permissions import can_delete_post, can_edit_post, can_publish, can_view_post


def _profile_for(request):
    """The signed-in user's profile, or None (a missing profile must not crash the page)."""
    if request.user.is_authenticated:
        return Profile.objects.filter(user=request.user).first()
    return None


def blog_post_list(request):
    """List published posts, newest first, with pagination."""
    post_list = BlogPost.objects.filter(status='published').select_related('category', 'author').order_by('-created_at')

    paginator = Paginator(post_list, 10)  # 10 posts per page
    page = request.GET.get('page')

    try:
        posts = paginator.page(page)
    except PageNotAnInteger:
        posts = paginator.page(1)
    except EmptyPage:
        posts = paginator.page(paginator.num_pages)

    context = {
        'posts': posts,
        'categories': BlogCategory.objects.all(),
        'tags': BlogTag.objects.all(),
        'user_profile': _profile_for(request),
    }

    return render(request, 'post_list.html', context)


def blog_post_detail(request, slug):
    """Show one post with its approved comments, and accept new comments from signed-in users."""
    post = get_object_or_404(BlogPost, slug=slug)

    # Drafts and archived posts are only visible to their author and editors.
    if not can_view_post(request.user, post):
        raise Http404

    if request.method == 'POST':
        if not request.user.is_authenticated:
            messages.warning(request, 'Please log in to comment.')
            return redirect_to_login(post.get_absolute_url())

        comment_form = BlogCommentForm(request.POST)
        if comment_form.is_valid():
            new_comment = comment_form.save(commit=False)
            new_comment.post = post
            new_comment.user = request.user
            new_comment.save()
            messages.success(request, 'Your comment is pending approval.')
            return redirect(post.get_absolute_url())
    else:
        comment_form = BlogCommentForm()

    comments = post.comments.filter(is_approved=True, parent__isnull=True).select_related('user')

    context = {
        'post': post,
        'comments': comments,
        'comment_form': comment_form,
        'user_profile': _profile_for(request),
    }

    return render(request, 'post_detail.html', context)


@login_required
def blog_post_create(request):
    """Create a post. Restricted to people allowed to publish (see blog/permissions.py)."""
    if not can_publish(request.user):
        messages.error(request, 'Only authorised authors can write blog posts.')
        return redirect('blog:post_list')

    categories = BlogCategory.objects.all().order_by('name')

    if request.method == 'POST':
        form = BlogPostForm(request.POST, request.FILES)
        if form.is_valid():
            post = form.save(commit=False)
            post.author = request.user
            post.save()
            form.save_m2m()
            messages.success(request, 'Blog post created successfully.')
            return redirect(post.get_absolute_url())
    else:
        form = BlogPostForm()

    return render(request, 'post_form.html', {
        'form': form,
        'categories': categories
    })


@login_required
def blog_post_update(request, slug):
    post = get_object_or_404(BlogPost, slug=slug)

    if not can_edit_post(request.user, post):
        messages.error(request, 'You do not have permission to edit this post.')
        return redirect('blog:post_list')

    if request.method == 'POST':
        form = BlogPostForm(request.POST, request.FILES, instance=post)
        if form.is_valid():
            form.save()
            messages.success(request, 'Blog post updated successfully.')
            return redirect(post.get_absolute_url())
    else:
        form = BlogPostForm(instance=post)

    return render(request, 'post_form.html', {
        'form': form,
        'categories': BlogCategory.objects.all().order_by('name'),
    })


@login_required
def blog_post_delete(request, slug):
    post = get_object_or_404(BlogPost, slug=slug)

    if not can_delete_post(request.user, post):
        messages.error(request, 'You do not have permission to delete this post.')
        return redirect('blog:post_list')

    if request.method == 'POST':
        post.delete()
        messages.success(request, 'Blog post deleted successfully.')
        return redirect('blog:post_list')

    return render(request, 'post_confirm_delete.html', {
        'post': post,
        'page_title': 'Delete Post',
        'cancel_url': post.get_absolute_url()
    })


def category_posts(request, slug):
    category = get_object_or_404(BlogCategory, slug=slug)
    posts = BlogPost.objects.filter(category=category, status='published')

    return render(request, 'category_posts.html', {'category': category, 'posts': posts})


def tag_posts(request, slug):
    tag = get_object_or_404(BlogTag, slug=slug)
    posts = tag.blogpost_set.filter(status='published')

    return render(request, 'tag_posts.html', {'tag': tag, 'posts': posts})
