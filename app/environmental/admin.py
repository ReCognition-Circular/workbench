from django.contrib import admin

from .models import EnvironmentalReport


@admin.register(EnvironmentalReport)
class EnvironmentalReportAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "kind",
        "prepared_for",
        "device_count",
        "excluded_count",
        "total_gwp_kg",
        "methodology_version",
        "generated_at",
    )
    list_filter = ("kind", "methodology_version")
    search_fields = (
        "prepared_for",
        "fulfilment_request__erpnext_order_id",
        "donation_pledge__reference_number",
    )
    readonly_fields = (
        "kind",
        "fulfilment_request",
        "donation_pledge",
        "prepared_for",
        "device_count",
        "excluded_count",
        "total_gwp_kg",
        "breakdown_json",
        "constants_json",
        "methodology_version",
        "generated_by",
        "generated_at",
        "pdf_file",
    )
    date_hierarchy = "generated_at"
