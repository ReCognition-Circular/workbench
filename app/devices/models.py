from django.db import models
from django.utils.text import slugify
from locations.models import Location
from workflow.models import Stage
from donors.models import Donor
from django.conf import settings

class Manufacturer(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

class DeviceType(models.TextChoices):
    LAPTOP = "LAPTOP", "Laptop"
    DESKTOP = "DESKTOP", "Desktop"
    ALL_IN_ONE = "ALL_IN_ONE", "All-in-One"
    TABLET = "TABLET", "Tablet"
    SERVER = "SERVER", "Server"
    OTHER = "OTHER", "Other"


class OwnershipType(models.TextChoices):
    DONATION = "DONATION", "Ownership transfers to ReCognition"
    RAAS = "RAAS", "Refurb-as-a-Service (ownership stays with donor)"
    LEASE_ASSET = "LEASE_ASSET", "ReCognition-owned asset for leasing"
    INTERNAL = "INTERNAL", "Internal use device"


class Grade(models.TextChoices):
    A = "A", "Grade A - Excellent"
    B = "B", "Grade B - Good"
    C = "C", "Grade C - Fair"
    D = "D", "Grade D - Poor"
    BER = "BER", "Beyond Economic Repair"
    UNGRADED = "UNGRADED", "Not yet graded"
class WipeStatus(models.TextChoices):
    DONOR_WIPED = 'DONOR_WIPED', "Donor confirmed pre-wiped"
    NO_STORAGE = 'NO_STORAGE', "No storage media present"
    PENDING = 'PENDING', "Needs wiping"
    PASS = 'PASS', "Wipe completed successfully"
    FAIL = 'FAIL', "Wipe attempted but failed"


class PartsStatus(models.TextChoices):
    UNKNOWN = 'UNKNOWN', "Not known"
    NOT_NEEDED = 'NOT_NEEDED', "No parts required"
    REQUESTED = 'REQUESTED', "Part requested"
    ORDERED = 'ORDERED', "Ordered"
    RECEIVED = 'RECEIVED', "Received"
    FITTED = 'FITTED', "Fitted"

class StorageType(models.TextChoices):
    HDD = "HDD", "HDD"
    SSD = "SSD", "SSD"
    NVME = "NVME", "NVMe"
    EMMC = "EMMC", "eMMC"
    UNKNOWN = "UNKNOWN", "Unknown"

class AllocationIntent(models.TextChoices):
    UNDECIDED = 'UNDECIDED', 'Undecided'
    SALE = 'SALE', 'Sale'
    DEVICE_BANK = 'DEVICE_BANK', 'Device Bank'
    RECYCLING = 'RECYCLING', 'Recycling'
    RESERVED = 'RESERVED', 'Reserved'
    OTHER = 'OTHER', 'Other'

class AllocationType(models.TextChoices):
    SALE = 'SALE', 'Sale'
    LEASE = 'LEASE', 'Lease'
    CHARITY_DONATION = 'CHARITY_DONATION', 'Charity Donation'
    RECYCLING = 'RECYCLING', 'Recycling'
    RAAS_RETURN = 'RAAS_RETURN', 'RaaS Return'
    INTERNAL_USE = 'INTERNAL_USE', 'Internal Use'
    TRAINING = 'TRAINING', 'Training'


class AllocationStatus(models.TextChoices):
    RESERVED = 'RESERVED', 'Reserved'
    DISPATCHED = 'DISPATCHED', 'Dispatched'
    CANCELLED = 'CANCELLED', 'Cancelled'


class FulfilmentStatus(models.TextChoices):
    PENDING = 'PENDING', 'Pending — awaiting allocation'
    IN_PROGRESS = 'IN_PROGRESS', 'In Progress — devices being allocated'
    READY = 'READY', 'Ready — all devices picked and awaiting dispatch'
    COMPLETE = 'COMPLETE', 'Complete'
    CANCELLED = 'CANCELLED', 'Cancelled'

class Recipient(models.Model):
    name = models.CharField(max_length=200)
    recipient_type = models.CharField(
        max_length=20,
        choices=[
            ('BUSINESS', 'Business'),
            ('CHARITY', 'Charity'),
            ('SCHOOL', 'School'),
            ('INDIVIDUAL', 'Individual'),
            ('INTERNAL', 'Internal'),
        ],
    )
    erpnext_customer_id = models.CharField(max_length=50, blank=True)
    contact_name = models.CharField(max_length=200, blank=True)
    contact_email = models.EmailField(blank=True)
    contact_phone = models.CharField(max_length=50, blank=True)
    address = models.TextField(blank=True)

    def __str__(self):
        return self.name

class Allocation(models.Model):
    """Links a Device to a Recipient with a specific purpose and status."""
    device = models.ForeignKey(
        'Device', on_delete=models.CASCADE, related_name="allocations"
    )
    status = models.CharField(
        max_length=20,
        choices=[
            ('RESERVED', 'Reserved'),
            ('DISPATCHED', 'Dispatched'),
            ('CANCELLED', 'Cancelled'),
        ],
        default='RESERVED',
    )
    allocation_type = models.CharField(
        max_length=20,
        choices=[
            ('SALE', 'Sale'),
            ('LEASE', 'Lease'),
            ('CHARITY_DONATION', 'Charity Donation'),
            ('RECYCLING', 'Recycling'),
            ('RAAS_RETURN', 'RaaS Return'),
            ('INTERNAL_USE', 'Internal Use'),
            ('TRAINING', 'Training'),
        ],
    )
    recipient = models.ForeignKey(
        'Recipient', on_delete=models.SET_NULL, null=True, blank=True
    )
    fulfilment_request = models.ForeignKey(
        'FulfilmentRequest', on_delete=models.SET_NULL, null=True, blank=True
    )

    erpnext_reference = models.CharField(
        max_length=100, blank=True,
        help_text="Sales Order ID or other ERPNext reference"
    )
    grant_reference = models.CharField(
        max_length=50, blank=True,
        help_text="ERPNext grant/funding reference (if grant-funded)"
    )
    erpnext_dn_reference = models.CharField(
    max_length=50, blank=True,
    help_text="ERPNext Delivery Note name (e.g. DN-001) — for reconciliation"
)
    price_pounds = models.DecimalField(max_digits=8, decimal_places=2, default=0)

    allocated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True
    )
    allocated_at = models.DateTimeField(auto_now_add=True)
    dispatched_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancel_reason = models.TextField(blank=True)
    target_ready_by = models.DateField(
        null=True, blank=True,
        help_text="Target date for devices to be ready for dispatch"
    )

    def __str__(self):
        return f"{self.device} → {self.recipient} ({self.get_status_display()})"


class FulfilmentRequest(models.Model):
    """A request to fulfil — comes from ERPNext Sales Order."""
    erpnext_order_id = models.CharField(max_length=50, unique=True)
    erpnext_order_url = models.URLField(blank=True)
    quantity = models.IntegerField(default=0, help_text="Number of devices requested")

    recipient = models.ForeignKey(
        'Recipient', on_delete=models.SET_NULL, null=True
    )

    summary = models.CharField(
        max_length=200,
        help_text="e.g. '50 Laptops Grade A for Acme Corp'"
    )
    target_date = models.DateField(null=True, blank=True)

    delivery_method = models.CharField(
        max_length=20,
        choices=[
            ('COLLECTION', 'Collection'),
            ('DELIVERY', 'Delivery'),
        ],
        default='COLLECTION',
    )
    delivery_address = models.TextField(blank=True)
    delivery_scheduled_date = models.DateField(null=True, blank=True)
    requested_spec = models.JSONField(
    blank=True, default=dict,
    help_text="Structured spec criteria promised to the customer. "
              "e.g. {'type': 'LAPTOP', 'grade': 'A', 'min_memory_gb': 8}"
)

    status = models.CharField(
        max_length=20,
        choices=[
            ('PENDING', 'Pending — awaiting allocation'),
            ('IN_PROGRESS', 'In Progress — devices being allocated'),
            ('READY', 'Ready — all devices picked and awaiting dispatch'),
            ('COMPLETE', 'Complete'),
            ('CANCELLED', 'Cancelled'),
        ],
        default='PENDING',
    )

    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.summary or self.erpnext_order_id

class SpecSource(models.TextChoices):
    FOG = "FOG", "FOG auto-detected"
    CEDAR = "CEDAR", "Cedar audit"
    MANUAL = "MANUAL", "Entered manually"


class DeviceSpecification(models.Model):
    manufacturer = models.CharField(max_length=100, blank=True)
    model_name = models.CharField(max_length=200, blank=True)
    model_number = models.CharField(max_length=100, blank=True)
    serial_number = models.CharField(max_length=100, blank=True, unique=True)
    processor = models.CharField(max_length=200, blank=True)
    memory_gb = models.IntegerField(null=True, blank=True)
    storage_type = models.CharField(
        max_length=20, choices=StorageType.choices, default=StorageType.UNKNOWN
    )
    storage_size_gb = models.IntegerField(null=True, blank=True)
    # Upgrade tracking (FOG path devices — original spec from GLPI stays untouched)
    memory_gb_upgraded = models.IntegerField(null=True, blank=True)
    storage_size_gb_upgraded = models.IntegerField(null=True, blank=True)
    processor_upgraded = models.CharField(max_length=200, blank=True)
    source = models.CharField(
        max_length=20, choices=SpecSource.choices, default=SpecSource.FOG
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.manufacturer} {self.model_name} ({self.serial_number})"


class Device(models.Model):
    inventory_number = models.CharField(max_length=50, unique=True)
    serial_number = models.CharField(max_length=100, unique=True, blank=True)

    # Device details
    device_type = models.CharField(
        max_length=20, choices=DeviceType.choices, default=DeviceType.LAPTOP
    )
    ownership_type = models.CharField(
        max_length=20, choices=OwnershipType.choices, default=OwnershipType.DONATION
    )
    grade = models.CharField(
        max_length=20, choices=Grade.choices, default=Grade.UNGRADED
    )
    grade = models.CharField(
        max_length=20, choices=Grade.choices, default=Grade.UNGRADED
    )

    # Wipe status
    wipe_status = models.CharField(
        max_length=20, choices=WipeStatus.choices, default=WipeStatus.PENDING
    )
    wipe_notes = models.TextField(blank=True)

    # Parts tracking
    parts_status = models.CharField(
        max_length=20, choices=PartsStatus.choices, default=PartsStatus.UNKNOWN
    )
    parts_notes = models.TextField(blank=True)
    # Relationships
    parts_cost_pounds = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    # Upgrade tracking — fitted components different from original spec
    memory_gb_upgraded = models.IntegerField(null=True, blank=True)
    storage_size_gb_upgraded = models.IntegerField(null=True, blank=True)
    processor_upgraded = models.CharField(max_length=200, blank=True) 

    # Allocation / stock intent
    allocation_intent = models.CharField(
        max_length=20,
        choices=AllocationIntent.choices,
        default=AllocationIntent.UNDECIDED,
    )
    market_value_pounds = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True,
        help_text="Manual estimated market value (£)"
    )
    
    device_specification = models.OneToOneField(
        DeviceSpecification,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="device",
    )
    reserved_for_name = models.CharField(
        max_length=200, blank=True,
        help_text="Organisation/person this device is reserved for"
    )
    location = models.ForeignKey(
        Location, on_delete=models.SET_NULL, null=True, blank=True, related_name="devices"
    )
    stage = models.ForeignKey(
        Stage, on_delete=models.SET_NULL, null=True, blank=True, related_name="devices"
    )
    donor = models.ForeignKey(
        Donor, on_delete=models.SET_NULL, null=True, blank=True, related_name="devices"
    )

    donation_pledge = models.ForeignKey(
        "donations.DonationPledge",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="devices",
    )
    # Windows 11 compatibility
    win11_compatible = models.CharField(
        max_length=10,
        choices=[
            ('YES', 'Yes'),
            ('NO', 'No'),
            ('UNKNOWN', 'Unknown'),
        ],
        default='UNKNOWN',
    )
    # Tracking
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        # Auto-calculate Windows 11 compatibility from processor spec
        if self.device_specification and self.device_specification.processor:
            from devices.win11_check import determine_win11_compatible
            self.win11_compatible = determine_win11_compatible(
                self.device_specification.processor
            )
        super().save(*args, **kwargs)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.inventory_number} ({self.serial_number})"
class InventorySequence(models.Model):
    """Atomic sequence counter for inventory number generation.
    
    Resets daily. Uses PostgreSQL row-level locking to guarantee
    no gaps and no duplicates under concurrent access.
    """
    date_prefix = models.CharField(max_length=4)  # MMDD format
    current_number = models.IntegerField(default=0)
    last_updated = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['date_prefix']
        ordering = ['-date_prefix']
    
    def __str__(self):
        return f"{self.date_prefix}: {self.current_number:04d}"
