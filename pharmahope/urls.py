"""
URL configuration for the pharmahope project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
"""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('store.urls')),
    path('cart/', include('cart.urls')),
    path('payment/', include('payment.urls')),
    path('blog/', include('blog.urls')),
    path('forum/', include('forum.urls')),
]

# Development-only helpers (static() is a no-op when DEBUG is False).
if getattr(settings, 'USE_BROWSER_RELOAD', False):
    urlpatterns.append(path('__reload__/', include('django_browser_reload.urls')))

urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
