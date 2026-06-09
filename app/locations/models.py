from django.db import models
import uuid


class Site(models.Model):
    """
    Site - Physical premises
    From specification: Supports multi-site operations
    """
    code = models.CharField(
        max_length=50,
        primary_key=True,
        help_text="Site code (e.g., RECOGNITION_DIGBETH)"
    )

    name = models.CharField(
        max_length=200,
        help_text="Site name (e.g., ReCognition - Digbeth)"
    )

    address = models.TextField(
        help_text="Full postal address"
    )

    is_active = models.BooleanField(
        default=True,
        help_text="Currently in use"
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When site was added"
    )

    deactivated_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When site was closed if applicable"
    )

    def __str__(self):
        return f"{self.code} - {self.name}"


class LocationPurpose(models.TextChoices):
    DEVICE = 'DEVICE', 'Device Storage'
    SUPPLIES = 'SUPPLIES', 'Supplies'
    TOOLS = 'TOOLS', 'Tools'
    RECYCLING = 'RECYCLING', 'Recycling'
    MIXED = 'MIXED', 'Mixed'


class LocationMaxSize(models.TextChoices):
    SMALL = 'SMALL', 'Small (Laptop)'
    MEDIUM = 'MEDIUM', 'Medium (Desktop)'
    LARGE = 'LARGE', 'Large (AIO/Server)'


class Location(models.Model):
    """
    Location - Physical storage location
    From specification: Hierarchical structure with barcode tracking
    """
    code = models.CharField(
        max_length=20,
        primary_key=True,
        help_text="Location code (e.g., MH18D04 or A1-1)"
    )

    site = models.ForeignKey(
        Site,
        on_delete=models.CASCADE,
        related_name='locations',
        help_text="Which premises"
    )

    zone = models.CharField(
        max_length=20,
        help_text="Physical zone e.g., CHECK IN, WIP, FINISHED STOCK, MISC"
    )

    shelf = models.CharField(
        max_length=10,
        blank=True,
        default='',
        help_text="Second level such as 1, 2, 3, 4"
    )

    section = models.CharField(
        max_length=10,
        blank=True,
        default='',
        help_text="Third level such as 1, 2, 3"
    )

    description = models.CharField(
        max_length=200,
        blank=True,
        help_text="Human-readable name (optional)"
    )

    purpose = models.CharField(
        max_length=20,
        choices=LocationPurpose.choices,
        default=LocationPurpose.DEVICE,
        help_text="What this location is used for"
    )

    max_size = models.CharField(
        max_length=10,
        choices=LocationMaxSize.choices,
        default=LocationMaxSize.SMALL,
        help_text="Maximum device size this location can hold"
    )

    notes = models.TextField(
        blank=True,
        default='',
        help_text="Free text notes about this location"
    )

    barcode = models.CharField(
        max_length=50,
        unique=True,
        blank=True,
        default='',
        help_text="Location barcode (unique, leave blank to use code)"
    )

    is_active = models.BooleanField(
        default=True,
        help_text="Available for use"
    )

    parent = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='children',
        help_text="For hierarchy (optional)"
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When location was added"
    )

    deactivated_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When decommissioned if applicable"
    )

    class Meta:
        ordering = ['zone', 'shelf', 'section']

    def save(self, *args, **kwargs):
        # If barcode is blank, copy code into barcode
        if not self.barcode.strip():
            self.barcode = self.code
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.code} ({self.site.code})"


class LocationScan(models.Model):
    """
    LocationScan - Records every time a device is scanned to a location
    From specification: Audit trail for device movements
    """
    device = models.ForeignKey(
        "devices.Device",
        on_delete=models.CASCADE,
        related_name="location_scans",
        help_text="The device that was scanned"
    )

    from_location = models.ForeignKey(
        Location,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="scans_from",
        help_text="Previous location (null if first scan)"
    )

    to_location = models.ForeignKey(
        Location,
        on_delete=models.SET_NULL,
        null=True,
        related_name="scans_to",
        help_text="New location after scan"
    )

    scanned_by = models.ForeignKey(
        "auth.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="Staff member who performed the scan"
    )

    notes = models.TextField(
        blank=True,
        help_text="Optional note about the move"
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When the scan occurred"
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        to = self.to_location.code if self.to_location else "(unknown)"
        from_loc = self.from_location.code if self.from_location else "(none)"
        return f"{self.device.inventory_number}: {from_loc} → {to}"

