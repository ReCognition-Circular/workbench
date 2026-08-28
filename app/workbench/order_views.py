"""Public customer order portal — track an order and download its certificates."""
import io
import zipfile
from pathlib import Path

from django.http import HttpResponse
from django.shortcuts import render

from devices.models import Allocation, Device, FulfilmentRequest
from wipe.models import AuditRecord
from wipe.pdf_generator import generate_audit_certificate


def _ensure_audit_pdf(device, audit):
    """Generate the audit certificate PDF if it has not been generated yet."""
    if not audit.certificate_file:
        audit.certificate_file.name = f"audit_certs/{device.inventory_number}_audit.pdf"
    path = Path(audit.certificate_file.path)
    if not path.exists():
        generate_audit_certificate(device, audit)
        audit.save(update_fields=["certificate_file"])
    return path


def order_certs(request):
    """Public page — customer enters an order reference, sees status and downloads certs."""
    fr = None
    devices = []
    error = None
    download_error = None

    if request.method == "POST":
        order_id = request.POST.get("order_id", "").strip()
        if order_id:
            try:
                fr = FulfilmentRequest.objects.select_related("recipient").get(
                    erpnext_order_id__iexact=order_id
                )
                device_ids = Allocation.objects.filter(
                    fulfilment_request=fr,
                    status__in=("RESERVED", "DISPATCHED"),
                ).values_list("device_id", flat=True)
                devices = list(
                    Device.objects.filter(pk__in=device_ids)
                    .select_related("device_specification", "latest_audit", "initial_audit")
                    .order_by("inventory_number")
                )
                for d in devices:
                    audit = d.latest_audit or d.initial_audit
                    if audit is None:
                        audit = AuditRecord.objects.filter(device=d).order_by("-created_at").first()
                    d.audit_cert = audit
            except FulfilmentRequest.DoesNotExist:
                error = "Order reference not found. Please check and try again."
        else:
            error = "Please enter an order reference number."

        if fr and request.POST.get("download") == "all":
            audits = [(d, d.audit_cert) for d in devices if getattr(d, "audit_cert", None) is not None]
            if audits:
                buf = io.BytesIO()
                with zipfile.ZipFile(buf, "w") as zf:
                    for d, audit in audits:
                        path = _ensure_audit_pdf(d, audit)
                        if path.exists():
                            zf.write(str(path), f"{d.inventory_number}_audit_cert.pdf")
                buf.seek(0)
                response = HttpResponse(buf.read(), content_type="application/zip")
                response["Content-Disposition"] = (
                    f'attachment; filename="{fr.erpnext_order_id}_audit_certs.zip"'
                )
                return response
            download_error = "No audit certificates are available for this order yet."

    has_audit_certs = any(getattr(d, "audit_cert", None) is not None for d in devices)
    return render(request, "order_certs.html", {
        "fr": fr,
        "devices": devices,
        "has_audit_certs": has_audit_certs,
        "error": error,
        "download_error": download_error,
    })
