from django.contrib import admin
from .models import IntegrationLog, CachedProduct


@admin.register(IntegrationLog)
class IntegrationLogAdmin(admin.ModelAdmin):
    list_display = [
        "created_at", "direction", "doctype", "action",
        "response_code", "status", "completed_at",
    ]
    list_filter = ["direction", "status", "action"]
    search_fields = ["doctype", "doc_name", "error_message"]
    readonly_fields = ["created_at", "completed_at"]


@admin.register(CachedProduct)
class CachedProductAdmin(admin.ModelAdmin):
    list_display = ["item_code", "item_name", "item_group", "is_variant", "last_synced_at"]
    search_fields = ["item_code", "item_name"]
