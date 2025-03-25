from django.contrib.auth.models import User
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Count
from .models import ForumCategory, ForumThread, ForumReply
from .forms import ThreadForm, ReplyForm


def forum_home(request):
    categories = ForumCategory.objects.annotate(
        thread_count=Count('threads'),
        reply_count=Count('threads__replies')
    )

    context = {
        'categories': categories,
        'total_posts': ForumReply.objects.count(),
        'total_threads': ForumThread.objects.count(),
        'total_users': User.objects.count(),
        'latest_post': ForumReply.objects.order_by('-created_at').first(),
    }

    return render(request, 'forum/home.html', context)


def category_detail(request, slug):
    category = get_object_or_404(ForumCategory, slug=slug)
    threads = category.threads.all().order_by('-created_at')

    paginator = Paginator(threads, 20)  # 20 threads per page
    page = request.GET.get('page')
    threads = paginator.get_page(page)

    return render(request, 'forum/category_detail.html', {
        'category': category,
        'threads': threads
    })


def thread_detail(request, slug):
    thread = get_object_or_404(ForumThread, slug=slug)
    replies = thread.replies.filter(parent=None).order_by('created_at')

    # Increment view count
    thread.views += 1
    thread.save()

    if request.method == 'POST' and request.user.is_authenticated:
        form = ReplyForm(request.POST)
        if form.is_valid():
            reply = form.save(commit=False)
            reply.thread = thread
            reply.user = request.user
            reply.save()
            messages.success(request, 'Your reply has been posted.')
            return redirect('forum:thread_detail', slug=slug)
    else:
        form = ReplyForm()

    return render(request, 'forum/thread_detail.html', {
        'thread': thread,
        'replies': replies,
        'form': form
    })


@login_required
def create_thread(request, category_slug):
    category = get_object_or_404(ForumCategory, slug=category_slug)

    if request.method == 'POST':
        form = ThreadForm(request.POST)
        if form.is_valid():
            thread = form.save(commit=False)
            thread.author = request.user
            thread.category = category
            thread.save()
            messages.success(request, 'Your thread has been created.')
            return redirect('forum:thread_detail', slug=thread.slug)
    else:
        form = ThreadForm()

    return render(request, 'forum/create_thread.html', {
        'form': form,
        'category': category
    })


@login_required
def reply_to_post(request, thread_id, parent_id=None):
    thread = get_object_or_404(ForumThread, id=thread_id)
    parent = get_object_or_404(ForumReply, id=parent_id) if parent_id else None

    if request.method == 'POST':
        form = ReplyForm(request.POST)
        if form.is_valid():
            reply = form.save(commit=False)
            reply.thread = thread
            reply.user = request.user
            reply.parent = parent
            reply.save()
            messages.success(request, 'Your reply has been posted.')
            return redirect('forum:thread_detail', slug=thread.slug)

    return redirect('forum:thread_detail', slug=thread.slug)


@login_required
def mark_solution(request, reply_id):
    reply = get_object_or_404(ForumReply, id=reply_id)
    if request.user == reply.thread.author:
        reply.is_solution = not reply.is_solution
        reply.save()
        messages.success(request, 'Solution status updated.')
    return redirect('forum:thread_detail', slug=reply.thread.slug)