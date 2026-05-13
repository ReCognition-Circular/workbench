from django.contrib import admin
from .models import Site, Location, LocationScan


class LocationInline(admin.TabularInline):
    model = Location
    fields = ["code", "zone", "shelf", "section", "barcode", "is_active"]
    extra = 0
    show_change_link = True


@admin.register(Site)
class SiteAdmin(admin.ModelAdmin):
    list_display = ["code", "name", "is_active", "created_at"]
    list_filter = ["is_active"]
    search_fields = ["code", "name", "address"]
    inlines = [LocationInline]


class SiteListFilter(admin.SimpleListFilter):
    title = "site"
    parameter_name = "site"

    def lookups(self, request, model_admin):
        return [(s.code, s.name) for s in Site.objects.filter(is_active=True)]

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(site__code=self.value())
        return queryset


@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    list_display = [
        "code",
        "description",
        "site",
        "zone",
        "shelf",
        "section",
        "barcode",
        "is_active",
    ]
    list_filter = [
        SiteListFilter,
        "is_active",
        "zone",
    ]
    search_fields = [
        "code",
        "barcode",
        "description",
    ]
    ordering = ["site", "zone", "shelf", "section"]
    list_editable = ["is_active"]


@admin.register(LocationScan)
class LocationScanAdmin(admin.ModelAdmin):
    list_display = [
        "device",
        "to_location",
        "scanned_by",
        "created_at",
    ]
    list_filter = ["created_at"]
    search_fields = [
        "device__inventory_number",
        "to_location__code",
    ]
    readonly_fields = ["device", "from_location", "to_location", "scanned_by", "created_at"]
    ordering = ["-created_at"]
