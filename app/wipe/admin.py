from django.contrib import admin
from .models import DataWipeRecord


@admin.register(DataWipeRecord)
class DataWipeRecordAdmin(admin.ModelAdmin):
    list_display = ["device", "result", "wipe_method", "wiped_at", "uploaded_at"]
    list_filter = ["result"]
    search_fields = ["device__inventory_number", "device__serial_number"]
