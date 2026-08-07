from django.contrib import admin
from django.db import models
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
            return queryset.filter(
                models.Q(initial_grade=self.value()) | models.Q(final_grade=self.value())
            )
        return queryset

class QAStatusListFilter(admin.SimpleListFilter):
    title = "qa status"
    parameter_name = "qa_status"

    def lookups(self, request, model_admin):
        return [('PASS', 'Pass'), ('FAIL', 'Fail')]

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(qa_status=self.value())
        return queryset


class ImageListFilter(admin.SimpleListFilter):
    title = "image"
    parameter_name = "image"

    def lookups(self, request, model_admin):
        return [
            ('NONE', 'None'),
            ('WINDOWS_11', 'Windows 11'),
            ('LINUX_UBUNTU', 'Linux - Ubuntu'),
            ('LINUX_MINT', 'Linux - Mint'),
            ('LINUX_OTHER', 'Linux - Other'),
            ('OTHER_OS', 'Other OS'),
        ]

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(image=self.value())
        return queryset


class AllocationIntentListFilter(admin.SimpleListFilter):
    title = "allocation intent"
    parameter_name = "allocation_intent"

    def lookups(self, request, model_admin):
        return [
            ('UNDECIDED', 'Undecided'),
            ('FOR_SALE', 'For Sale'),
            ('DEVICE_BANK', 'Device Bank'),
            ('PARTS_HARVESTING', 'Parts Harvesting'),
            ('RECYCLE', 'Recycle'),
        ]

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(allocation_intent=self.value())
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
        "initial_grade", 
        "final_grade",
        "allocation_intent",
        "stage",
        "qa_status",
        "image", 
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
        "wipe_status",
        "initial_audit_status",
        "final_audit_status",
        "stage",
        "qa_status", 
        "image",
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
        "fields": ["device_type", "ownership_type", "initial_grade", "final_grade", "qa_status", "image"]
    }),
    ("Location & Status", {
        "fields": ["location", "stage", "allocation_intent"]
    }),
    ("Donor", {
        "fields": ["donor"]
    }),
    ("Refurbishment", {
        "fields": ["refurb_notes"]
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
        "drive_serial",
    ]
    search_fields = [
        "manufacturer",
        "model_name",
        "serial_number",
        "drive_serial",
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
