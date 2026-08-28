"""
URL configuration for workbench project.
"""

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import TemplateView
from django.views.generic import RedirectView
from donations.views import donor_certs
from donations.erasure_summary import donor_erasure_summary

from . import views
from api.views import CoordinatorDashboardView
from environmental.views import order_report, donation_report, donor_environmental_report, order_environmental_report
from workbench.order_views import order_certs

urlpatterns = [
    path('', RedirectView.as_view(url='/devices/', permanent=False)),
    path('admin/', admin.site.urls),
    path('api/', include('api.urls')),
    path('api/checklists/', include('checklists.urls')),
    path('', include('donations.urls')),
    path('api-auth/', include('rest_framework.urls')),
    path('devices/', views.device_list, name='device_list'),
    path('devices/<int:pk>/', views.device_detail, name='device_detail'),
    path('pledges/', views.pledge_list, name='pledge_list'),
    path('pledges/<str:reference>/', views.pledge_detail, name='pledge_detail'),
    path('pledges/<str:reference>/complete/', views.pledge_mark_complete, name='pledge_mark_complete'),
    path('pledges/<str:reference>/link-device/', views.pledge_link_device, name='pledge_link_device'),
    path('devices/manual/create/', views.manual_device_create, name='manual_device_create'),
    path('devices/manual/create/', views.manual_device_create, name='manual_device_create'),
    path("devices/<int:pk>/edit/", views.device_edit, name="device_edit"),
    path('devices/<int:pk>/<str:stage>/', views.device_checklist, name='device_checklist'),
    path('photos/', views.photo_capture, name='photo_capture'),
    path('scan/', views.scan_page, name='scan_page'),
    path("stock/", views.stock_available_page, name="stock_available"),
    path('dashboard/', CoordinatorDashboardView.as_view(), name='dashboard'),
    path('manifest.json', TemplateView.as_view(template_name='manifest.json', content_type='application/json')),
    path('accounts/', include('django.contrib.auth.urls')),
    path('recipients/', views.recipient_list, name='recipient_list'),
    path('recipients/new/', views.recipient_create, name='recipient_create'),
    path('recipients/<int:pk>/', views.recipient_detail, name='recipient_detail'),
    path('recipients/<int:pk>/edit/', views.recipient_edit, name='recipient_edit'),
    path('fulfilment-requests/', views.fulfilment_request_list, name='fr_list'),
    path('fulfilment-requests/<int:pk>/', views.fulfilment_request_detail, name='fr_detail'),
    path('fulfilment-requests/<int:pk>/environmental-report/', order_report, name='fr_environmental_report'),
    path('pledges/<str:reference>/environmental-report/', donation_report, name='pledge_environmental_report'),
    path('donate/certs/', donor_certs, name='donor_certs'),
    path('donate/certs/summary/', donor_erasure_summary, name='donor_certs_summary'),
    path('donate/certs/environmental/', donor_environmental_report, name='donor_certs_environmental'),
    path('orders/', RedirectView.as_view(url='/orders/certs/', permanent=False), name='orders'),
    path('orders/certs/', order_certs, name='order_certs'),
    path('orders/certs/environmental/', order_environmental_report, name='order_certs_environmental'),
    path('api/integration/', include('integrations.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
