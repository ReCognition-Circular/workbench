"""
API URL Configuration
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    DeviceViewSet,
    LocationViewSet,
    StageViewSet,
    DonorViewSet,
    SiteViewSet,
    StockOverviewView,
    StockAvailableView,
    StockBulkUpdateView,
    next_inventory_number,
    check_serial,
    update_device_intent,
    RecipientViewSet,
    ReserveView,
    FulfilmentRequestViewSet,
    CustomerWebhookView
)

router = DefaultRouter()
router.register("devices", DeviceViewSet, basename="device")
router.register("locations", LocationViewSet, basename="location")
router.register("stages", StageViewSet, basename="stage")
router.register("donors", DonorViewSet, basename="donor")
router.register("sites", SiteViewSet, basename="site")
router.register("recipients", RecipientViewSet, basename="recipient")
router.register(r'fulfilment-requests', FulfilmentRequestViewSet, basename='fulfilment-request')

urlpatterns = [
    path("", include(router.urls)),
    path("", include("donations.urls")),
    path("", include("wipe.urls")),
    path("stock/overview/", StockOverviewView.as_view(), name="stock-overview"),
    path("stock/available/", StockAvailableView.as_view(), name="stock-available"),
    path('stock/bulk-update/', StockBulkUpdateView.as_view(), name='stock-bulk-update'),
    path('stock/reserve/', ReserveView.as_view(), name='stock-reserve'),
    path('devices/<int:pk>/intent/', update_device_intent, name='update-device-intent'),
    path("inventory/next-number/", next_inventory_number, name="next-inventory-number"),
    path("inventory/check-serial/", check_serial, name="check-serial"),
    path('integration/customer/', CustomerWebhookView.as_view(), name='customer-webhook'),
]

# Location scan endpoints (destination-first workflow)
from .location_views import location_resolve, scan_device_to_location

urlpatterns += [
    path('locations/resolve/', location_resolve, name='location-resolve'),
    path('locations/<str:code>/scan-device/<str:inventory>/', scan_device_to_location, name='scan-device-to-location'),
]
# Barcode resolution — detect if a scanned barcode is a location or a device
from .views import resolve_barcode

urlpatterns += [
    path('resolve-barcode/', resolve_barcode, name='resolve-barcode'),
]
