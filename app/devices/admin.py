from django.contrib import admin
from .models import Device, DeviceSpecification, DeviceType, Grade, Recipient, Allocation, FulfilmentRequest, Manufacturer

class DeviceTypeListFilter(admin.SimpleListFilter):
    title = "device type"
    parameter_name = "device_type"

    def lookups(self, request, model_admin):
        return DeviceType.choices

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(device_type=self.value())
        return queryset


class GradeListFilter(admin.SimpleListFilter):
    title = "grade"
    parameter_name = "grade"

    def lookups(self, request, model_admin):
        return Grade.choices

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(grade=self.value())
        return queryset

@admin.register(Manufacturer)
class ManufacturerAdmin(admin.ModelAdmin):
    list_display = ["name", "slug"]
    prepopulated_fields = {"slug": ("name",)}

@admin.register(Device)
class DeviceAdmin(admin.ModelAdmin):
    list_display = [
        "inventory_number",
        "serial_number",
        "device_type",
        "grade", 
        "allocation_intent",
        "stage",
        "location",
        "donor",
        "created_at",
        "updated_at",
    ]
    list_filter = [
        DeviceTypeListFilter,
        GradeListFilter,
        "allocation_intent",
        "ownership_type",
        "stage",
        "location__site",
    ]
    search_fields = [
        "inventory_number",
        "serial_number",
        "notes",
    ]
    ordering = ["-created_at"]
    date_hierarchy = "created_at"
    readonly_fields = ["created_at", "updated_at"]
    list_select_related = ["stage", "location", "donor"]

    fieldsets = [
        ("Identification", {
            "fields": ["inventory_number", "serial_number"]
        }),
        ("Classification", {
            "fields": ["device_type", "ownership_type", "grade", "allocation_intent", "market_value_pounds"]
        }),
        ("Location & Status", {
            "fields": ["location", "stage"]
        }),
        ("Donor", {
            "fields": ["donor"]
        }),
        ("Notes", {
            "fields": ["notes"]
        }),
        ("Timestamps", {
            "fields": ["created_at", "updated_at"],
            "classes": ["collapse"],
        }),
    ]


@admin.register(DeviceSpecification)
class DeviceSpecificationAdmin(admin.ModelAdmin):
    list_display = [
        "device",
        "manufacturer",
        "model_name",
        "processor",
        "memory_gb",
        "storage_type",
        "source",
    ]
    search_fields = [
        "manufacturer",
        "model_name",
        "serial_number",
    ]
    list_filter = [
        "source",
        "storage_type",
    ]

@admin.register(Recipient)
class RecipientAdmin(admin.ModelAdmin):
    list_display = ["name", "recipient_type", "contact_email", "contact_phone"]
    list_filter = ["recipient_type"]
    search_fields = ["name", "contact_email", "contact_phone"]

@admin.register(Allocation)
class AllocationAdmin(admin.ModelAdmin):
    list_display = [
        "device", "recipient", "status", "allocation_type",
        "price_pounds", "allocated_at", "dispatched_at",
    ]
    list_filter = ["status", "allocation_type"]
    search_fields = ["device__inventory_number", "recipient__name"]
    readonly_fields = ["allocated_at", "dispatched_at", "cancelled_at"]


@admin.register(FulfilmentRequest)
class FulfilmentRequestAdmin(admin.ModelAdmin):
    list_display = ["erpnext_order_id", "recipient", "summary", "status", "target_date"]
    list_filter = ["status", "delivery_method"]
    search_fields = ["erpnext_order_id", "summary", "recipient__name"]
