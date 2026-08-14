"""Calculation engine and report generation for environmental reports."""
from decimal import Decimal

from devices.models import Allocation, Device, FulfilmentRequest
from donations.models import DonationPledge

from .constants import BOAVIZTA_TERMINAL_GWP_KG, METHODOLOGY_VERSION
from .models import EnvironmentalReport


def compute_batch(devices):
    """Sum manufacturing GWP across a queryset of devices.

    Returns a dict with total_gwp_kg, breakdown (per type), rows and excluded.
    """
    breakdown = {}
    rows = []
    excluded = []
    for d in devices.order_by("inventory_number"):
        kg = BOAVIZTA_TERMINAL_GWP_KG.get(d.device_type)
        if kg is None:
            excluded.append(
                {"inventory_number": d.inventory_number, "device_type": d.device_type}
            )
            continue
        breakdown[d.device_type] = breakdown.get(d.device_type, 0) + 1
        rows.append(
            {
                "inventory_number": d.inventory_number,
                "serial_number": d.serial_number,
                "device_type": d.device_type,
                "gwp_kg": kg,
            }
        )

    total = round(sum(BOAVIZTA_TERMINAL_GWP_KG[t] * n for t, n in breakdown.items()), 2)
    breakdown_out = {
        t: {"count": n, "subtotal_kg": BOAVIZTA_TERMINAL_GWP_KG[t] * n}
        for t, n in breakdown.items()
    }
    return {
        "total_gwp_kg": total,
        "breakdown": breakdown_out,
        "rows": rows,
        "excluded": excluded,
    }


def generate_report(kind, anchor_id, user=None):
    """Create an EnvironmentalReport for an order or donation anchor."""
    if kind not in EnvironmentalReport.Kind.values:
        raise ValueError(f"Unknown kind {kind!r}; use 'ORDER' or 'DONATION'.")

    fulfilment_request = None
    donation_pledge = None

    if kind == "ORDER":
        fr = FulfilmentRequest.objects.get(pk=anchor_id)
        if fr.status not in ("READY", "COMPLETE"):
            raise ValueError(
                f"Order report requires status READY or COMPLETE (got {fr.status})."
            )
        device_ids = Allocation.objects.filter(
            fulfilment_request=fr,
            status__in=("RESERVED", "DISPATCHED"),
        ).values_list("device_id", flat=True)
        devices = Device.objects.filter(pk__in=device_ids)
        prepared_for = fr.recipient.name if fr.recipient_id else ""
        fulfilment_request = fr
    else:  # DONATION
        pledge = DonationPledge.objects.get(pk=anchor_id)
        if pledge.status not in ("PARTIAL", "COMPLETE"):
            raise ValueError(
                f"Donation report requires status PARTIAL or COMPLETE (got {pledge.status})."
            )
        devices = pledge.devices.all()
        prepared_for = pledge.donor_name
        donation_pledge = pledge

    result = compute_batch(devices)

    report = EnvironmentalReport.objects.create(
        kind=kind,
        fulfilment_request=fulfilment_request,
        donation_pledge=donation_pledge,
        prepared_for=prepared_for,
        device_count=len(result["rows"]),
        excluded_count=len(result["excluded"]),
        total_gwp_kg=Decimal(str(result["total_gwp_kg"])),
        breakdown_json={
            "breakdown": result["breakdown"],
            "rows": result["rows"],
            "excluded": result["excluded"],
        },
        constants_json=dict(BOAVIZTA_TERMINAL_GWP_KG),
        methodology_version=METHODOLOGY_VERSION,
        generated_by=user,
    )
    return report
