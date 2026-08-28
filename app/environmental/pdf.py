"""Environmental impact report PDF generation."""
from pathlib import Path

from django.core.files.base import ContentFile
from django.template import Context, Engine
from weasyprint import HTML

from .constants import IMPACT_CATEGORIES

TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "template" / "pdf"
LOGO_PATH = Path(__file__).resolve().parent.parent / "core" / "static" / "core" / "Logo.svg"
LETTERHEAD_PATH = Path(__file__).resolve().parent.parent / "core" / "static" / "core" / "letterhead.png"
TEMPLATE_NAME = "environmental_report.html"

CATEGORY_KEYS = [key for key, *_ in IMPACT_CATEGORIES]

# Display decimals: per-unit vs total.
CATEGORY_DECIMALS = {
    "gwp": 1, "adpe": 4, "ir": 1, "odp": 6, "ap": 2, "ept": 2,
}
CATEGORY_TOTAL_DECIMALS = {
    "gwp": 0, "adpe": 4, "ir": 0, "odp": 6, "ap": 2, "ept": 2,
}
CATEGORY_THOUSANDS = {"gwp", "ir"}


def _load_template():
    return (TEMPLATE_DIR / TEMPLATE_NAME).read_text(encoding="utf-8")


def _logo_url():
    return LOGO_PATH.as_uri() if LOGO_PATH.exists() else ""


def _letterhead_url():
    return LETTERHEAD_PATH.as_uri() if LETTERHEAD_PATH.exists() else ""


def _fmt(value, key, total=False):
    if value is None:
        return "&mdash;"
    decimals = CATEGORY_TOTAL_DECIMALS[key] if total else CATEGORY_DECIMALS[key]
    v = round(float(value), decimals)
    if key in CATEGORY_THOUSANDS:
        return f"{v:,.{decimals}f}"
    return f"{v:.{decimals}f}"


def _render_html(context):
    engine = Engine(dirs=[str(TEMPLATE_DIR)])
    template = engine.from_string(_load_template())
    return template.render(Context(context))


def generate_pdf(report):
    """Render the report HTML and attach the resulting PDF to `report`."""
    data = report.breakdown_json or {}
    totals = data.get("totals", {})
    breakdown = data.get("breakdown", {})
    factors = data.get("factors", {})

    device_types = list(breakdown.keys())

    # Multi-criteria table: one row per category.
    table_rows = []
    for key, name, unit, description in IMPACT_CATEGORIES:
        table_rows.append(
            {
                "label": f"{name} ({unit})",
                "cells": [_fmt(factors[t].get(key), key) for t in device_types],
                "total": _fmt(totals.get(key), key, total=True),
            }
        )

    # Per-type summary (count + carbon).
    type_summary = []
    for t in device_types:
        type_summary.append(
            {
                "device_type": t,
                "count": breakdown[t]["count"],
                "gwp_per_unit": _fmt(factors[t].get("gwp"), "gwp"),
                "gwp_subtotal": _fmt(breakdown[t]["subtotals"].get("gwp"), "gwp", total=True),
            }
        )

    total_gwp = float(totals.get("gwp") or 0)
    headline = {
        "kg": _fmt(total_gwp, "gwp", total=True),
        "tonnes": f"{total_gwp / 1000:.1f}",
    }

    rows = []
    for r in data.get("rows", []):
        rows.append(
            {
                "inventory_number": r.get("inventory_number"),
                "serial_number": r.get("serial_number"),
                "device_type": r.get("device_type"),
                "gwp_kg": _fmt(r.get("gwp_kg"), "gwp"),
            }
        )

    excluded = data.get("excluded", [])

    if report.kind == report.Kind.ORDER:
        kind_display = "Fulfilment request"
        batch_label = "Order reference"
        if report.fulfilment_request:
            batch_ref = report.fulfilment_request.erpnext_order_id or f"FR-{report.fulfilment_request.pk}"
        else:
            batch_ref = "&mdash;"
    else:
        kind_display = "Donation pledge"
        batch_label = "Donation reference"
        if report.donation_pledge:
            batch_ref = report.donation_pledge.reference_number or f"Pledge-{report.donation_pledge.pk}"
        else:
            batch_ref = "&mdash;"

    if report.generated_by:
        generated_by_name = report.generated_by.get_full_name() or report.generated_by.username
    else:
        generated_by_name = "&mdash;"

    context = {
        "logo_url": _logo_url(),
        "letterhead_url": _letterhead_url(),
        "report": report,
        "kind_display": kind_display,
        "batch_label": batch_label,
        "batch_ref": batch_ref,
        "device_types": device_types,
        "table_rows": table_rows,
        "type_summary": type_summary,
        "headline": headline,
        "rows": rows,
        "excluded": excluded,
        "generated_by_name": generated_by_name,
    }

    html_string = _render_html(context)
    pdf_bytes = HTML(string=html_string, base_url=str(TEMPLATE_DIR)).write_pdf()

    filename = f"environmental_report_{report.pk}.pdf"
    report.pdf_file.save(filename, ContentFile(pdf_bytes), save=True)
