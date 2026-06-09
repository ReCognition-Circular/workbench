from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import DataWipeRecordViewSet

router = DefaultRouter()
router.register("wipe-records", DataWipeRecordViewSet, basename="wipe-record")

urlpatterns = [
    path("", include(router.urls)),
]
