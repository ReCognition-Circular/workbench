from django.contrib import admin
from .models import Donor


@admin.register(Donor)
class DonorAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "contact_name",
        "contact_email",
        "default_ownership_type",
        "requires_wipe_certificate",
    ]
    list_filter = [
        "default_ownership_type",
        "requires_wipe_certificate",
        "requires_environmental_report",
    ]
    search_fields = [
        "name",
        "contact_name",
        "contact_email",
    ]
    ordering = ["name"]
