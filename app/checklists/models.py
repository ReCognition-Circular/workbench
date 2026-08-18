from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models


class ChecklistTemplate(models.Model):
    """A reusable checklist definition (e.g. 'Check-In', 'Refurb', 'QA')."""

    code = models.CharField(max_length=50, unique=True, help_text="Slug: check-in, refurb, qa")
    name = models.CharField(max_length=100, help_text="Display name")
    version = models.IntegerField(default=1)
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["code"]

    def __str__(self):
        return f"{self.name} v{self.version}"


class ChecklistTemplateItem(models.Model):
    """A single question / row inside a template."""

    class ItemType(models.TextChoices):
        PASS_FAIL = "PASS_FAIL", "Pass / Fail"
        YES_NO = "YES_NO", "Yes / No"
        DONE_NOT_DONE = "DONE_NOT_DONE", "Done / Not Done"
        SELECT = "SELECT", "Select (dropdown)"
        TEXT = "TEXT", "Text"

    class AutoSource(models.TextChoices):
        CEDAR_TEST = "CEDAR_TEST", "Cedar diagnostic test"
        DEVICE_SPEC = "DEVICE_SPEC", "Device specification"
        DATAWIPE_RECORD = "DATAWIPE_RECORD", "Data-wipe record"
        REFURB_STATUS = "REFURB_STATUS", "Refurb status"

    class WeightTier(models.IntegerChoices):
        TIER_0_CRITICAL = 0, "Tier 0 — Critical (10 pts)"
        TIER_1_MAJOR = 1, "Tier 1 — Major (5 pts)"
        TIER_2_MODERATE = 2, "Tier 2 — Moderate (3 pts)"
        TIER_3_LOW = 3, "Tier 3 — Low (1 pt)"

    template = models.ForeignKey(
        ChecklistTemplate,
        on_delete=models.CASCADE,
        related_name="items",
    )
    order_number = models.IntegerField(help_text="Display sequence within the template")
    section_label = models.CharField(max_length=100, help_text="Grouping header, e.g. 'Physical Track', 'BIOS'")
    label = models.CharField(max_length=255, help_text="Text shown to the technician")
    item_type = models.CharField(max_length=20, choices=ItemType.choices, default=ItemType.PASS_FAIL)
    options = models.JSONField(null=True, blank=True, help_text="Options for SELECT type, e.g. ['Win 11','Ubuntu']")
    is_auto_populated = models.BooleanField(default=False, help_text="Filled by system, not technician")
    auto_source = models.CharField(
        max_length=50, null=True, blank=True, choices=AutoSource.choices,
        help_text="Where the auto-value comes from",
    )
    cedar_component_key = models.CharField(
        max_length=100, null=True, blank=True,
        help_text="Key in Cedar test_results JSON, e.g. 'Motherboard'",
    )
    weight_tier = models.IntegerField(
        null=True, blank=True, choices=WeightTier.choices,
        help_text="Tier used in auto-grade calculation for Cedar failures",
    )
    photo_required = models.BooleanField(default=False)
    max_photos = models.IntegerField(default=0, help_text="Max photos for this item (0-3 for defects)")
    generates_defect = models.BooleanField(default=False, help_text="Auto-create Defect record on FAIL response")

    defect_trigger_value = models.CharField(
        max_length=10,
        blank=True,
        null=True,
        choices=[("FAIL", "Fail"), ("YES", "Yes"), ("NO", "No")],
        help_text="Response value that creates a Defect. Blank = never creates a defect.",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["template", "order_number"]
        unique_together = [["template", "order_number"]]

    def __str__(self):
        return f"[{self.template.code}] {self.section_label} → {self.label}"


class ChecklistInstance(models.Model):
    """One filled-out checklist for one device at one stage."""

    class Status(models.TextChoices):
        IN_PROGRESS = "IN_PROGRESS", "In Progress"
        COMPLETE = "COMPLETE", "Complete"

    device = models.ForeignKey(
        "devices.Device",
        on_delete=models.CASCADE,
        related_name="checklist_instances",
    )
    template = models.ForeignKey(
        ChecklistTemplate,
        on_delete=models.PROTECT,
        related_name="instances",
    )
    stage = models.ForeignKey(
        "workflow.Stage",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="checklist_instances",
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.IN_PROGRESS)
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    started_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="started_checklists",
    )
    completed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="completed_checklists",
    )

    class Meta:
        unique_together = [["device", "template"]]

    def __str__(self):
        return f"{self.template.code} — {self.device.inventory_number} ({self.status})"


class ChecklistItemResponse(models.Model):
    """A single answer to one checklist item, auto-saved on every toggle."""

    instance = models.ForeignKey(
        ChecklistInstance,
        on_delete=models.CASCADE,
        related_name="responses",
    )
    template_item = models.ForeignKey(
        ChecklistTemplateItem,
        on_delete=models.PROTECT,
        related_name="responses",
    )
    value = models.JSONField(null=True, blank=True, help_text="Boolean, string, or null")
    notes = models.TextField(blank=True)
    responded_at = models.DateTimeField(auto_now=True)
    responded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
    )

    class Meta:
        unique_together = [["instance", "template_item"]]

    def __str__(self):
        return f"{self.template_item.label}: {self.value}"


class Defect(models.Model):
    """Bridges check-in findings to refurb work. Stored records, not a view."""

    class SourceType(models.TextChoices):
        CHECKIN_PHYSICAL = "CHECKIN_PHYSICAL", "Check-in — Physical Track"
        CEDAR_TEST = "CEDAR_TEST", "Check-in — Cedar Test"

    class ResolutionStatus(models.TextChoices):
        OPEN = "OPEN", "Open"
        IN_PROGRESS = "IN_PROGRESS", "In Progress"
        FIXED = "FIXED", "Fixed"
        WONT_FIX = "WONT_FIX", "Won't Fix"
        DEFERRED = "DEFERRED", "Deferred"

    device = models.ForeignKey(
        "devices.Device",
        on_delete=models.CASCADE,
        related_name="defects",
    )
    source_type = models.CharField(max_length=20, choices=SourceType.choices)
    source_item = models.ForeignKey(
        ChecklistTemplateItem,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        help_text="Which template item generated this defect",
    )
    checklist_response = models.ForeignKey(
        ChecklistItemResponse,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="generated_defects",
        help_text="Response at check-in stage that triggered this defect",
    )
    resolution_response = models.ForeignKey(
        ChecklistItemResponse,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="resolved_defects",
        help_text="Response at refurb stage that resolved this defect",
    )
    repair_task = models.ForeignKey(
        "devices.RepairTask",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="linked_defects",
    )
    generates_refurb_item = models.BooleanField(
        default=True,
        help_text="Auto-include in Refurb checklist Section 4",
    )
    resolution_status = models.CharField(
        max_length=20,
        choices=ResolutionStatus.choices,
        default=ResolutionStatus.OPEN,
    )
    description = models.TextField(blank=True)
    resolution_notes = models.TextField(
        blank=True,
        help_text="Reason for Won't Fix or Deferred resolution"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Defect #{self.id} — {self.device.inventory_number} ({self.source_type}: {self.resolution_status})"


class DevicePhoto(models.Model):
    """Photo attached to any checklist-related object via GenericForeignKey."""

    class PhotoType(models.TextChoices):
        BEFORE = "BEFORE", "Before"
        AFTER = "AFTER", "After"
        EXIT_TOP = "EXIT_TOP", "Exit — Top Cover"
        EXIT_BOTTOM = "EXIT_BOTTOM", "Exit — Bottom"
        EXIT_SCREEN = "EXIT_SCREEN", "Exit — Screen"
        EXIT_KEYBOARD = "EXIT_KEYBOARD", "Exit — Keyboard"
        BOOT = "BOOT", "Boot"
        DAMAGE_DETAIL = "DAMAGE_DETAIL", "Damage Detail"

    # The device this photo ultimately belongs to
    device = models.ForeignKey(
        "devices.Device",
        on_delete=models.CASCADE,
        related_name="photos",
    )

    # GenericForeignKey — photo can belong to a Response, Defect, or Instance
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, null=True, blank=True)
    object_id = models.PositiveIntegerField(null=True, blank=True)
    content_object = GenericForeignKey("content_type", "object_id")

    photo_type = models.CharField(max_length=20, choices=PhotoType.choices)
    image = models.ImageField(upload_to="device_photos/%Y/%m/")
    notes = models.TextField(blank=True)
    captured_at = models.DateTimeField(auto_now_add=True)
    captured_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
    )

    class Meta:
        ordering = ["-captured_at"]

    def __str__(self):
        return f"{self.get_photo_type_display()} — {self.device.inventory_number}"

