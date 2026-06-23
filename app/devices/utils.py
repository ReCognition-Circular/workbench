"""Utility functions for device management."""

from django.utils import timezone


MANUAL_PREFIX = "7"
FOG_PREFIX = "6"


def generate_manual_inventory_number():
    """Generate the next inventory number for a manually-entered device.
    
    Format: 7MMDDXXXX
    - 7 = manual source prefix
    - MMDD = month + day (e.g. 0616 for 16 June)
    - XXXX = sequential number, resets daily (0001-9999)
    
    Uses a direct max() query on existing inventory numbers
    for today to determine the next sequence number.
    """
    from devices.models import Device

    now = timezone.now()
    date_prefix = f"{now.month:02d}{now.day:02d}"
    today_pattern = f"{MANUAL_PREFIX}{date_prefix}%"

    # Find the highest sequence number used today for manual entries
    max_inv = (
        Device.objects
        .filter(inventory_number__startswith=f"{MANUAL_PREFIX}{date_prefix}")
        .order_by("-inventory_number")
        .values_list("inventory_number", flat=True)
        .first()
    )

    if max_inv:
        # Extract last 4 digits and increment
        next_seq = int(max_inv[-4:]) + 1
    else:
        next_seq = 1

    if next_seq > 9999:
        raise RuntimeError(
            f"Manual inventory sequence exhausted for {date_prefix}. "
            f"Maximum 9999 devices per day."
        )

    return f"{MANUAL_PREFIX}{date_prefix}{next_seq:04d}"
