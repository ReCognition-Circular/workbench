"""Views for generating and downloading environmental impact reports."""
import os

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect

from devices.models import FulfilmentRequest
from donations.models import DonationPledge

from .pdf import generate_pdf
from .services import generate_report
from .models import EnvironmentalReport


def _existing_order_report(fr):
    return (
        EnvironmentalReport.objects.filter(fulfilment_request=fr)
        .order_by("-generated_at")
        .first()
    )


def _existing_donation_report(pledge):
    return (
        EnvironmentalReport.objects.filter(donation_pledge=pledge)
        .order_by("-generated_at")
        .first()
    )


def _pdf_response(report):
    if not report.pdf_file:
        generate_pdf(report)
    filename = os.path.basename(report.pdf_file.name) or f"environmental_report_{report.pk}.pdf"
    response = HttpResponse(report.pdf_file.read(), content_type="application/pdf")
    response["Content-Disposition"] = f'inline; filename="{filename}"'
    return response


@login_required
def order_report(request, pk):
    """Generate (or reuse) and download the environmental report for an order."""
    fr = get_object_or_404(FulfilmentRequest, pk=pk)
    report = _existing_order_report(fr)
    if report is None:
        try:
            report = generate_report("ORDER", fr.pk, user=request.user)
        except ValueError as exc:
            messages.error(request, str(exc))
            return redirect("fr_detail", pk=fr.pk)
    return _pdf_response(report)


@login_required
def donation_report(request, reference):
    """Generate (or reuse) and download the environmental report for a pledge."""
    pledge = get_object_or_404(DonationPledge, reference_number=reference)
    report = _existing_donation_report(pledge)
    if report is None:
        try:
            report = generate_report("DONATION", pledge.pk, user=request.user)
        except ValueError as exc:
            messages.error(request, str(exc))
            return redirect("pledge_detail", reference=pledge.reference_number)
    return _pdf_response(report)


def donor_environmental_report(request):
    """Public page — donor downloads the environmental impact report for a pledge."""
    reference = request.GET.get("reference", "").strip()
    if not reference:
        return HttpResponse("Missing pledge reference.", status=400)

    try:
        pledge = DonationPledge.objects.get(reference_number=reference)
    except DonationPledge.DoesNotExist:
        return HttpResponse("Pledge reference not found.", status=404)

    report = _existing_donation_report(pledge)
    if report is None:
        try:
            report = generate_report("DONATION", pledge.pk, user=None)
        except ValueError as exc:
            return HttpResponse(str(exc), status=400)

    if not report.pdf_file:
        generate_pdf(report)

    filename = f"{pledge.reference_number}_environmental_impact_report.pdf"
    response = HttpResponse(report.pdf_file.read(), content_type="application/pdf")
    response["Content-Disposition"] = f'inline; filename="{filename}"'
    return response


def order_environmental_report(request):
    """Public page — customer downloads the environmental impact report for an order."""
    order_id = request.GET.get("order_id", "").strip()
    if not order_id:
        return HttpResponse("Missing order reference.", status=400)

    try:
        fr = FulfilmentRequest.objects.get(erpnext_order_id__iexact=order_id)
    except FulfilmentRequest.DoesNotExist:
        return HttpResponse("Order reference not found.", status=404)

    report = _existing_order_report(fr)
    if report is None:
        try:
            report = generate_report("ORDER", fr.pk, user=None)
        except ValueError as exc:
            return HttpResponse(str(exc), status=400)

    if not report.pdf_file:
        generate_pdf(report)

    filename = f"{fr.erpnext_order_id}_environmental_impact_report.pdf"
    response = HttpResponse(report.pdf_file.read(), content_type="application/pdf")
    response["Content-Disposition"] = f'inline; filename="{filename}"'
    return response
