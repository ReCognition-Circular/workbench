"""Calculation engine and report generation for environmental reports."""
import json
import urllib.request
from decimal import Decimal

from devices.models import Allocation, Device, FulfilmentRequest
from donations.models import DonationPledge

from .constants import (
    BOAVIZTA_TERMINAL_URL,
    IMPACT_CATEGORIES,
    TERMINAL_SLUG,
    METHODOLOGY_VERSION,
)
from .models import EnvironmentalReport


CATEGORY_KEYS = [key for key, *_ in IMPACT_CATEGORIES]


def fetch_terminal_impacts(slug):
    """Return the manufacturing ("embedded") impacts for a terminal archetype.

    Returns a dict {category_key: float} for the six reported categories.
    """
    criteria = "&".join(f"criteria={key}" for key in CATEGORY_KEYS)
    url = f"{BOAVIZTA_TERMINAL_URL.format(slug=slug)}?{criteria}"
    request = urllib.request.Request(
        url,
        method="POST",
        data=b"{}",
        headers={"Content-Type": "application/json", "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            data = json.load(response)
    except Exception as exc:
        raise ValueError(
            f"Could not fetch environmental impact data from Boavizta for {slug!r}: {exc}"
        ) from exc

    impacts = {}
    for key in CATEGORY_KEYS:
        impacts[key] = data["impacts"][key]["embedded"]["value"]
    return impacts


def compute_batch(devices):
    """Sum manufacturing impacts across a queryset of devices.

    Returns a dict with totals, breakdown (per type), per-type factors,
    per-device rows and excluded devices.
    """
    factors = {}
    breakdown = {}
    rows = []
    excluded = []

    for device in devices.order_by("inventory_number"):
        slug = TERMINAL_SLUG.get(device.device_type)
        if slug is None:
            excluded.append(
                {
                    "inventory_number": device.inventory_number,
                    "device_type": device.device_type,
                }
            )
            continue

        if device.device_type not in factors:
            factors[device.device_type] = fetch_terminal_impacts(slug)

        impacts = factors[device.device_type]
        entry = breakdown.setdefault(
            device.device_type,
            {"count": 0, "subtotals": {key: 0.0 for key in CATEGORY_KEYS}},
        )
        entry["count"] += 1
        for key in CATEGORY_KEYS:
            entry["subtotals"][key] += impacts[key]

        rows.append(
            {
                "inventory_number": device.inventory_number,
                "serial_number": device.serial_number,
                "device_type": device.device_type,
                "gwp_kg": impacts["gwp"],
            }
        )

    totals = {key: 0.0 for key in CATEGORY_KEYS}
    for entry in breakdown.values():
        for key in CATEGORY_KEYS:
            totals[key] += entry["subtotals"][key]

    # Round to remove floating-point noise (e.g. 0.10319999... -> 0.1032).
    for entry in breakdown.values():
        entry["subtotals"] = {key: round(value, 6) for key, value in entry["subtotals"].items()}
    totals = {key: round(value, 6) for key, value in totals.items()}

    return {
        "totals": totals,
        "breakdown": breakdown,
        "factors": factors,
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
        if fr.status not in ("READY", "DISPATCHED", "COMPLETE"):
            raise ValueError(
                f"Order report requires status READY, DISPATCHED or COMPLETE (got {fr.status})."
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
        total_gwp_kg=Decimal(f"{result['totals']['gwp']:.2f}"),
        breakdown_json={
            "totals": result["totals"],
            "breakdown": result["breakdown"],
            "factors": result["factors"],
            "rows": result["rows"],
            "excluded": result["excluded"],
        },
        constants_json={
            "terminal_slug": TERMINAL_SLUG,
            "factors": result["factors"],
        },
        methodology_version=METHODOLOGY_VERSION,
        generated_by=user,
    )
    return report
