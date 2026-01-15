"""
API URL Configuration
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter

# Create a router for API views
router = DefaultRouter()

# We'll add actual API endpoints later
# router.register('devices', DeviceViewSet)
# router.register('locations', LocationViewSet)

urlpatterns = [
    path('', include(router.urls)),
]
