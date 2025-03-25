from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.contrib.auth.decorators import user_passes_test

from store.models import Profile
from .models import BlogPost, BlogCategory, BlogTag, BlogComment
from .forms import BlogPostForm, BlogCommentForm


def blog_post_list(request):
    if request.user.is_authenticated:
        user_profile = Profile.objects.get(user=request.user)
    else:
        user_profile = None
    """
    View to list all published blog posts with pagination and context
    """
    # Retrieve only published posts, ordered by creation date
    post_list = BlogPost.objects.filter(status='published').order_by('-created_at')

    # Pagination
    paginator = Paginator(post_list, 10)  # 10 posts per page
    page = request.GET.get('page')

    try:
        posts = paginator.page(page)
    except PageNotAnInteger:
        # If page is not an integer, deliver first page
        posts = paginator.page(1)
    except EmptyPage:
        # If page is out of range, deliver last page of results
        posts = paginator.page(paginator.num_pages)

    # Additional context
    context = {
        'posts': posts,
        'categories': BlogCategory.objects.all(),
        'tags': BlogTag.objects.all(),
        'user_profile': user_profile
    }

    return render(request, 'post_list.html', context)


def blog_post_detail(request, slug):
    if request.user.is_authenticated:
        user_profile = Profile.objects.get(user=request.user)
    else:
        user_profile = None

    """
    View to display a single blog post with comments
    """
    # Retrieve the post or return 404
    post = get_object_or_404(BlogPost, slug=slug)

    # Handle comment submission
    if request.method == 'POST':
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

    # Retrieve approved top-level comments
    comments = post.comments.filter(is_approved=True, parent__isnull=True)

    context = {
        'post': post,
        'comments': comments,
        'comment_form': comment_form,
        'user_profile': user_profile
    }

    return render(request, 'post_detail.html', context)


@login_required
def blog_post_create(request):
    """
    View to create a new blog post
    """
    # Get all categories with their hierarchy
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
    """
    View to update an existing blog post
    """
    # Retrieve the post or return 404
    post = get_object_or_404(BlogPost, slug=slug)

    # Check if the current user is the author
    if request.user != post.author:
        messages.error(request, 'You do not have permission to edit this post.')
        return redirect('blog:post_detail', slug=post.slug)

    if request.method == 'POST':
        form = BlogPostForm(request.POST, request.FILES, instance=post)
        if form.is_valid():
            form.save()
            messages.success(request, 'Blog post updated successfully.')
            return redirect(post.get_absolute_url())
    else:
        form = BlogPostForm(instance=post)

    return render(request, 'post_form.html', {'form': form})


@login_required
def blog_post_delete(request, slug):
    """
    View to delete a blog post with improved error handling and user feedback
    """
    post = get_object_or_404(BlogPost, slug=slug)

    # Check if the current user is the author or has delete permissions
    if not (request.user == post.author or request.user.has_perm('blog.delete_blogpost')):
        messages.error(request, 'You do not have permission to delete this post.')
        return redirect('blog:post_detail', slug=post.slug)

    if request.method == 'POST':
        try:
            post.delete()
            messages.success(request, 'Blog post deleted successfully.')
            return redirect('blog:post_list')
        except Exception as e:
            messages.error(request, f'Error deleting post: {str(e)}')
            return redirect('blog:post_detail', slug=post.slug)

    return render(request, 'post_confirm_delete.html', {
        'post': post,
        'page_title': 'Delete Post',
        'cancel_url': post.get_absolute_url()
    })


def category_posts(request, slug):
    """
    View to list posts in a specific category
    """
    category = get_object_or_404(BlogCategory, slug=slug)
    posts = BlogPost.objects.filter(category=category, status='published')

    context = {
        'category': category,
        'posts': posts
    }

    return render(request, 'category_posts.html', context)


def tag_posts(request, slug):
    """
    View to list posts with a specific tag
    """
    tag = get_object_or_404(BlogTag, slug=slug)
    posts = tag.blogpost_set.filter(status='published')

    context = {
        'tag': tag,
        'posts': posts
    }

    return render(request, 'tag_posts.html', context)
