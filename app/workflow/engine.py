from locations.models import LocationScan
from workflow.models import StageTransition


def process_location_scan(device, location, user):
    """
    Called when a device is scanned into a location.
    
    1. Always updates the device's current location.
    2. Logs the scan in LocationScan.
    3. If location.triggers_stage is set, attempts a stage transition
       validated against the device's current Stage.allowed_next.
    """
    previous_location = device.location
    device.location = location
    device.save(update_fields=['location'])

    LocationScan.objects.create(
        device=device,
        from_location=previous_location,
        to_location=location,
        scanned_by=user,
    )

    result = {
        'location_changed': True,
        'stage_changed': False,
        'new_stage': None,
    }

    if location.triggers_stage:
        try:
            target_stage = Stage.objects.get(code=location.triggers_stage)
        except Stage.DoesNotExist:
            result['warning'] = f"Stage '{location.triggers_stage}' not found"
            return result

        if target_stage in device.stage.allowed_next_stages.all():
            previous_stage = device.stage
            device.stage = target_stage
            device.save(update_fields=['stage'])

            StageTransition.objects.create(
                device=device,
                from_stage=previous_stage,
                to_stage=target_stage,
                triggered_by=user,
                trigger_type='LOCATION_SCAN',
            )

            result['stage_changed'] = True
            result['new_stage'] = target_stage.code
        else:
            result['warning'] = (
                f"Transition from {device.stage.code} "
                f"to {target_stage.code} not allowed"
            )

    return result
