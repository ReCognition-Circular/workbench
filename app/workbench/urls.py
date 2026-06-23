"""
URL configuration for workbench project.
"""

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import TemplateView
from django.views.generic import RedirectView

from . import views
from api.views import CoordinatorDashboardView

urlpatterns = [
    path('', RedirectView.as_view(url='/devices/', permanent=False)),
    path('admin/', admin.site.urls),
    path('api/', include('api.urls')),
    path('', include('donations.urls')),
    path('api-auth/', include('rest_framework.urls')),
    path('devices/', views.device_list, name='device_list'),
    path('devices/<int:pk>/', views.device_detail, name='device_detail'),
    path('devices/manual/create/', views.manual_device_create, name='manual_device_create'),
    path('devices/manual/create/', views.manual_device_create, name='manual_device_create'),
    path("devices/<int:pk>/edit/", views.device_edit, name="device_edit"),
    path('scan/', views.scan_page, name='scan_page'),
    path("stock/", views.stock_available_page, name="stock_available"),
    path('dashboard/', CoordinatorDashboardView.as_view(), name='dashboard'),
    path('manifest.json', TemplateView.as_view(template_name='manifest.json', content_type='application/json')),
    path('accounts/', include('django.contrib.auth.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
