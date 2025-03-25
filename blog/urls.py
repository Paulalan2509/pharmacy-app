from django.urls import path
from . import views

app_name = 'blog'

urlpatterns = [
    path('', views.blog_post_list, name='post_list'),
    # Place 'new' pattern before the slug pattern
    path('post/new/', views.blog_post_create, name='post_create'),
    path('post/<slug:slug>/', views.blog_post_detail, name='post_detail'),
    path('post/<slug:slug>/update/', views.blog_post_update, name='post_update'),
    path('post/<slug:slug>/delete/', views.blog_post_delete, name='post_delete'),
    path('category/<slug:slug>/', views.category_posts, name='category_posts'),
    path('tag/<slug:slug>/', views.tag_posts, name='tag_posts'),
]