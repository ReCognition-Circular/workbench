from django.contrib import admin
from .models import DonationPledge, ExpectedDevice


class ExpectedDeviceInline(admin.TabularInline):
    model = ExpectedDevice
    extra = 1


@admin.register(DonationPledge)
class DonationPledgeAdmin(admin.ModelAdmin):
    list_display = ["reference_number", "donor_name", "status", "source", "created_at"]
    list_filter = ["status", "source"]
    search_fields = ["donor_name", "reference_number"]
    inlines = [ExpectedDeviceInline]


@admin.register(ExpectedDevice)
class ExpectedDeviceAdmin(admin.ModelAdmin):
    list_display = ["serial_number", "make", "model", "status", "donation_pledge"]
    list_filter = ["status", "device_type"]
    search_fields = ["serial_number", "make", "model"]
