from locations.models import LocationScan
from workflow.models import StageTransition, Stage
from checklists.models import ChecklistInstance


# Stages that, when exited, require their checklist to be COMPLETE
# (soft gate — the move is allowed, but flagged on the device).
SOFT_GATE_STAGE_TO_TEMPLATE = {
    "CHECK_IN": "check-in",
    "REFURB_IN_PROGRESS": "refurb",
}

QA_STAGE = "QA"
AWAITING_DISPATCH = "AWAITING_DISPATCH"


def _checklist_complete(device, template_code):
    """True if the device has a COMPLETE checklist instance for the template slug."""
    return ChecklistInstance.objects.filter(
        device=device,
        template__code=template_code,
        status=ChecklistInstance.Status.COMPLETE,
    ).exists()


def validate_stage_transition(device, target_stage):
    """
    Shared transition gate used by both location scans and the
    /api/devices/{id}/transition/ endpoint.

    Returns (allowed, warning_stage, block_reason):
      - allowed=False  -> block the transition (block_reason set).
      - allowed=True   -> proceed; warning_stage set if a soft gate
                          was skipped and should be flagged on the device.
    """
    current = device.stage

    # 1. allowed_next enforcement
    if current is not None and not current.allowed_next_stages.filter(pk=target_stage.pk).exists():
        return False, None, f"Transition from {current.code} to {target_stage.code} not allowed"

    # 2. Hard gate: QA -> AWAITING_DISPATCH requires qa_status == PASS
    if (
        current is not None
        and current.code == QA_STAGE
        and target_stage.code == AWAITING_DISPATCH
        and device.qa_status != "PASS"
    ):
        return False, None, "QA not complete — qa_status must be PASS to move to AWAITING_DISPATCH"

    # 3. Soft gate: leaving CHECK_IN / REFURB_IN_PROGRESS without its checklist
    warning_stage = None
    if current is not None:
        template_code = SOFT_GATE_STAGE_TO_TEMPLATE.get(current.code)
        if template_code and not _checklist_complete(device, template_code):
            warning_stage = current.code

    return True, warning_stage, None


def process_location_scan(device, location, user):
    """
    Called when a device is scanned into a location.

    1. Always updates the device's current location.
    2. Logs the scan in LocationScan.
    3. If location.triggers_stage is set, attempts a stage transition
       validated by validate_stage_transition().
    """
    previous_location = device.location
    device.location = location
    device.save(update_fields=["location"])

    LocationScan.objects.create(
        device=device,
        from_location=previous_location,
        to_location=location,
        scanned_by=user,
    )

    result = {
        "location_changed": True,
        "stage_changed": False,
        "new_stage": None,
    }

    if location.triggers_stage:
        try:
            target_stage = Stage.objects.get(code=location.triggers_stage)
        except Stage.DoesNotExist:
            result["warning"] = f"Stage '{location.triggers_stage}' not found"
            return result

        allowed, warning_stage, block_reason = validate_stage_transition(device, target_stage)

        if not allowed:
            result["warning"] = block_reason
            return result

        previous_stage = device.stage
        device.stage = target_stage
        update_fields = ["stage"]

        if warning_stage:
            device.checklist_warning = True
            device.checklist_warning_stage = warning_stage
            update_fields += ["checklist_warning", "checklist_warning_stage"]

        device.save(update_fields=update_fields)

        StageTransition.objects.create(
            device=device,
            from_stage=previous_stage,
            to_stage=target_stage,
            transitioned_by=user,
            notes="LOCATION_SCAN",
        )

        result["stage_changed"] = True
        result["new_stage"] = target_stage.code

        if warning_stage:
            result["warning"] = (
                f"Checklist for {warning_stage} not complete — warning set on device"
            )

    return result
