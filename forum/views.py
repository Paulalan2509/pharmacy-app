from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib.auth.views import redirect_to_login
from django.core.paginator import Paginator
from django.db.models import Count, F
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .forms import ReplyForm, ThreadForm
from .models import ForumCategory, ForumReply, ForumThread


def forum_home(request):
    categories = ForumCategory.objects.annotate(
        thread_count=Count('threads', distinct=True),
        reply_count=Count('threads__replies', distinct=True),
    )

    context = {
        'categories': categories,
        'total_posts': ForumReply.objects.count(),
        'total_threads': ForumThread.objects.count(),
        'total_users': User.objects.count(),
        'latest_post': ForumReply.objects.select_related('thread', 'user').order_by('-created_at').first(),
    }

    return render(request, 'forum/home.html', context)


def category_detail(request, slug):
    category = get_object_or_404(ForumCategory, slug=slug)
    threads = category.threads.select_related('author').annotate(
        reply_total=Count('replies')
    ).order_by('-created_at')

    paginator = Paginator(threads, 20)  # 20 threads per page
    threads = paginator.get_page(request.GET.get('page'))

    return render(request, 'forum/category_detail.html', {
        'category': category,
        'threads': threads
    })


def _save_reply(request, thread, form, parent=None):
    reply = form.save(commit=False)
    reply.thread = thread
    reply.user = request.user
    reply.parent = parent
    reply.save()
    messages.success(request, 'Your reply has been posted.')


def thread_detail(request, slug):
    thread = get_object_or_404(ForumThread.objects.select_related('author', 'category'), slug=slug)

    if request.method == 'POST':
        if not request.user.is_authenticated:
            messages.warning(request, 'Please log in to reply.')
            return redirect_to_login(thread.get_absolute_url())
        if thread.is_closed:
            messages.error(request, 'This thread is closed to new replies.')
            return redirect('forum:thread_detail', slug=slug)
        form = ReplyForm(request.POST)
        if form.is_valid():
            _save_reply(request, thread, form)
            return redirect('forum:thread_detail', slug=slug)
    else:
        form = ReplyForm()
        # Count the view atomically, and without touching updated_at (a full save() would).
        ForumThread.objects.filter(pk=thread.pk).update(views=F('views') + 1)
        thread.refresh_from_db(fields=['views'])

    replies = thread.replies.select_related('user', 'parent__user').order_by('created_at')

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
@require_POST
def reply_to_post(request, thread_id, parent_id=None):
    thread = get_object_or_404(ForumThread, id=thread_id)

    if thread.is_closed:
        messages.error(request, 'This thread is closed to new replies.')
        return redirect('forum:thread_detail', slug=thread.slug)

    # A reply can only answer another reply from the *same* thread.
    parent = get_object_or_404(ForumReply, id=parent_id, thread=thread) if parent_id else None

    form = ReplyForm(request.POST)
    if form.is_valid():
        _save_reply(request, thread, form, parent=parent)
    else:
        messages.error(request, 'Your reply could not be posted. Please write something and try again.')
    return redirect('forum:thread_detail', slug=thread.slug)


@login_required
@require_POST  # changing state through a GET link would bypass CSRF protection
def mark_solution(request, reply_id):
    reply = get_object_or_404(ForumReply.objects.select_related('thread'), id=reply_id)
    if request.user == reply.thread.author:
        reply.is_solution = not reply.is_solution
        reply.save(update_fields=['is_solution'])
        messages.success(request, 'Solution status updated.')
    else:
        messages.error(request, 'Only the person who started the thread can mark a solution.')
    return redirect('forum:thread_detail', slug=reply.thread.slug)
