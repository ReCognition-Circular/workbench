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
)

router = DefaultRouter()
router.register("devices", DeviceViewSet, basename="device")
router.register("locations", LocationViewSet, basename="location")
router.register("stages", StageViewSet, basename="stage")
router.register("donors", DonorViewSet, basename="donor")

urlpatterns = [
    path("", include(router.urls)),
]
