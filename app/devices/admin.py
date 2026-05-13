from django.contrib import admin
from .models import Device, DeviceSpecification, DeviceType, Grade



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


@admin.register(Device)
class DeviceAdmin(admin.ModelAdmin):
    list_display = [
        "inventory_number",
        "serial_number",
        "device_type",
        "grade",
        "stage",
        "location",
        "donor",
        "created_at",
        "updated_at",
    ]
    list_filter = [
        DeviceTypeListFilter,
        GradeListFilter,
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
            "fields": ["device_type", "ownership_type", "grade"]
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
