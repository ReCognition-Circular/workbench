from django.db import models
from locations.models import Location
from workflow.models import Stage
from donors.models import Donor


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
        max_length=20, choices=PartsStatus.choices, default=PartsStatus.NOT_NEEDED
    )
    parts_notes = models.TextField(blank=True)
    # Relationships
    parts_cost_pounds = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    # Upgrade tracking — fitted components different from original spec
    memory_gb_upgraded = models.IntegerField(null=True, blank=True)
    storage_size_gb_upgraded = models.IntegerField(null=True, blank=True)
    processor_upgraded = models.CharField(max_length=200, blank=True) 
    
    device_specification = models.OneToOneField(
        DeviceSpecification,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="device",
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

    # Tracking
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.inventory_number} ({self.serial_number})"
