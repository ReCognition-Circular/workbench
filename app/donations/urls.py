from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import DonationPledgeViewSet, ExpectedDeviceViewSet, donate_page, donate_thanks, donate_template

router = DefaultRouter()
router.register("donation-pledges", DonationPledgeViewSet, basename="donation-pledge")
router.register("expected-devices", ExpectedDeviceViewSet, basename="expected-device")

urlpatterns = [
    path("", include(router.urls)),
    path("donate/template/", donate_template, name="donate_template"),
    path("donate/", donate_page, name="donate"),
    path("donate/thanks/<str:reference>/", donate_thanks, name="donate_thanks")
]
