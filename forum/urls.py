from django.urls import path
from . import views

app_name = 'forum'

urlpatterns = [
    path('', views.forum_home, name='forum_home'),
    path('category/<slug:slug>/', views.category_detail, name='category_detail'),
    path('thread/<slug:slug>/', views.thread_detail, name='thread_detail'),
    path('category/<slug:category_slug>/create/', views.create_thread, name='create_thread'),
    path('reply/<int:thread_id>/', views.reply_to_post, name='reply_to_post'),
    path('reply/<int:thread_id>/<int:parent_id>/', views.reply_to_post, name='reply_to_comment'),
    path('mark-solution/<int:reply_id>/', views.mark_solution, name='mark_solution'),
]