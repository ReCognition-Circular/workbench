from django.db.models.signals import post_save
from django.dispatch import receiver
import logging

from wipe.models import DataWipeRecord
from devices.models import Device
from checklists.models import (
    ChecklistInstance,
    ChecklistItemResponse,
    ChecklistTemplateItem,
    Defect,
)

logger = logging.getLogger(__name__)

# Cedar Pass/Fail text → boolean mapping
PASS_VALUES = {"pass", "passed", "true", "yes", "ok"}
FAIL_VALUES = {"fail", "failed", "false", "no", "error"}


def _parse_result(result_str):
    """Convert Cedar result string to (value, is_fail) tuple."""
    if not result_str:
        return None, False
    r = result_str.strip().lower()
    if r in PASS_VALUES:
        return True, False
    if r in FAIL_VALUES:
        return False, True
    return None, False


def _extract_details(test_data):
    """Extract human-readable details from Cedar test data.
    Handles comments as string, list, or absent.
    Also extracts battery health from sub-batteries.
    """
    parts = []

    # Comments — can be string (most common) or list (e.g. processor)
    comments = test_data.get("comments", "")
    if isinstance(comments, list):
        comments = "; ".join(str(c) for c in comments)
    comments = comments.strip() if isinstance(comments, str) else ""
    if comments:
        parts.append(comments)

    # Battery health from sub-batteries (the "batteries" array)
    for battery in test_data.get("batteries", []):
        health = battery.get("health", "")
        if health and health not in comments:
            parts.append(f"Health = {health}")

    return "; ".join(parts) if parts else ""


@receiver(post_save, sender=DataWipeRecord)
def cedar_checklist_hook(sender, instance, created, **kwargs):
    """Auto-fill Cedar track checklist from DataWipeRecord.json_data."""
    if not created:
        return
    if not instance.json_data:
        return

    device = instance.device
    if device.stage.code != "CHECK_IN":
        return

    audit = instance.json_data.get("audit", {})
    if not audit:
        logger.info(f"DWR {instance.id}: no audit section, skipping")
        return

    try:
        from checklists.models import ChecklistTemplate
        template = ChecklistTemplate.objects.get(code="check-in")
    except Exception:
        logger.warning("Check-in template not found")
        return

    instance_obj, _ = ChecklistInstance.objects.get_or_create(
        device=device,
        template=template,
        stage=device.stage,
        defaults={"status": "IN_PROGRESS",
                  "started_at": __import__("datetime").datetime.now()},
    )

    # Case-insensitive lookup of audit keys
    audit_lower = {k.lower(): v for k, v in audit.items()}

    cedar_items = ChecklistTemplateItem.objects.filter(
        template=template,
        section_label="Cedar Track",
        cedar_component_key__isnull=False,
    )

    filled = 0
    defects = 0

    for item in cedar_items:
        key = item.cedar_component_key  # e.g. "battery", "motherboard"
        test_data = audit_lower.get(key.lower()) if key else None

        if test_data is None:
            value = None
            is_fail = False
            notes = "Not present in Cedar report"
        else:
            result_str = test_data.get("result", "")
            value, is_fail = _parse_result(result_str)
            notes = _extract_details(test_data)

        response, _ = ChecklistItemResponse.objects.update_or_create(
            instance=instance_obj,
            template_item=item,
            defaults={"value": value, "notes": notes},
        )
        filled += 1

        if is_fail:
            desc = f"{item.label}: {notes}" if notes else item.label
            Defect.objects.get_or_create(
                device=device,
                source_type=Defect.SourceType.CEDAR_TEST,
                source_item=item,
                defaults={
                    "checklist_response": response,
                    "generates_refurb_item": True,
                    "resolution_status": Defect.ResolutionStatus.OPEN,
                    "description": desc,
                },
            )
            defects += 1

    logger.info(
        f"Cedar hook: {device.inventory_number} — "
        f"{filled} responses, {defects} defects"
    )

