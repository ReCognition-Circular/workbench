from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.db import models
from devices.models import Device
from workflow.models import Stage


@login_required
def device_list(request):
    """Device list page with filters."""
    devices_qs = Device.objects.select_related("stage", "location", "donor").all()

    search = request.GET.get("search", "")
    stage_filter = request.GET.get("stage", "")
    grade_filter = request.GET.get("grade", "")

    if search:
        devices_qs = devices_qs.filter(
            models.Q(inventory_number__icontains=search)
            | models.Q(serial_number__icontains=search)
        )

    if stage_filter:
        devices_qs = devices_qs.filter(stage__code=stage_filter)

    if grade_filter:
        devices_qs = devices_qs.filter(grade=grade_filter)

    devices_qs = devices_qs.order_by("-created_at")

    stages = Stage.objects.all().order_by("sequence")

    devices = []
    for d in devices_qs:
        devices.append({
            "id": d.id,
            "inventory_number": d.inventory_number,
            "serial_number": d.serial_number,
            "device_type": d.device_type,
            "grade": d.grade,
            "wipe_status": d.wipe_status,
            "parts_status": d.parts_status,
            "stage_name": d.stage.name if d.stage else "-",
            "location_code": d.location.code if d.location else None,
            "updated_at": d.updated_at,
        })

    return render(request, "device_list.html", {
        "devices": devices,
        "stages": stages,
        "search": search,
        "stage_filter": stage_filter,
        "grade_filter": grade_filter,
    })


@login_required
def device_detail(request, pk):
    """Device detail page with stage transition buttons."""
    device = get_object_or_404(
        Device.objects.select_related("stage", "location", "donor", "device_specification"),
        pk=pk,
    )

    # Get available transitions
    available_stages = []
    if device.stage:
        available_stages = device.stage.allowed_next_stages.all().order_by("sequence")

    stages = Stage.objects.all().order_by("sequence")

    return render(request, "device_detail.html", {
        "device": device,
        "available_stages": available_stages,
        "stages": stages,
    })


@login_required
def scan_page(request):
    """Scan page for barcode reader workflow."""
    return render(request, "scan.html")
