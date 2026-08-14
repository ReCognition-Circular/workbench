"""Environmental impact report PDF generation."""
from pathlib import Path

from django.core.files.base import ContentFile
from django.template import Context, Engine
from weasyprint import HTML

from .constants import BOAVIZTA_TERMINAL_GWP_KG

TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "template" / "pdf"
LOGO_PATH = Path(__file__).resolve().parent.parent / "core" / "static" / "core" / "Logo.svg"
TEMPLATE_NAME = "environmental_report.html"


def _load_template():
    return (TEMPLATE_DIR / TEMPLATE_NAME).read_text(encoding="utf-8")


def _logo_url():
    return LOGO_PATH.as_uri() if LOGO_PATH.exists() else ""


def _render_html(context):
    engine = Engine(dirs=[str(TEMPLATE_DIR)])
    template = engine.from_string(_load_template())
    return template.render(Context(context))


def generate_pdf(report):
    """Render the report HTML and attach the resulting PDF to `report`."""
    data = report.breakdown_json or {}
    breakdown = data.get("breakdown", {})

    breakdown_items = [
        {
            "device_type": device_type,
            "count": values.get("count", 0),
            "per_unit_kg": BOAVIZTA_TERMINAL_GWP_KG.get(device_type, 0),
            "subtotal_kg": values.get("subtotal_kg", 0),
        }
        for device_type, values in breakdown.items()
    ]

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
        "report": report,
        "kind_display": kind_display,
        "batch_label": batch_label,
        "batch_ref": batch_ref,
        "breakdown_items": breakdown_items,
        "rows": data.get("rows", []),
        "excluded": data.get("excluded", []),
        "generated_by_name": generated_by_name,
    }

    html_string = _render_html(context)
    pdf_bytes = HTML(string=html_string, base_url=str(TEMPLATE_DIR)).write_pdf()

    filename = f"environmental_report_{report.pk}.pdf"
    report.pdf_file.save(filename, ContentFile(pdf_bytes), save=True)
    return report
