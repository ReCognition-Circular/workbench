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
)

router = DefaultRouter()
router.register("devices", DeviceViewSet, basename="device")
router.register("locations", LocationViewSet, basename="location")
router.register("stages", StageViewSet, basename="stage")
router.register("donors", DonorViewSet, basename="donor")
router.register("sites", SiteViewSet, basename="site")

urlpatterns = [
    path("", include(router.urls)),
    path("", include("donations.urls")),
    path("", include("wipe.urls")),
    path("stock/overview/", StockOverviewView.as_view(), name="stock-overview"),
    path("stock/available/", StockAvailableView.as_view(), name="stock-available"),
    path('stock/bulk-update/', StockBulkUpdateView.as_view(), name='stock-bulk-update'),
    path('devices/<int:pk>/intent/', update_device_intent, name='update-device-intent'),
    path("inventory/next-number/", next_inventory_number, name="next-inventory-number"),
    path("inventory/check-serial/", check_serial, name="check-serial"),

]

