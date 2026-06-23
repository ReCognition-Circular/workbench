from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.db import models
from devices.models import Device
from workflow.models import Stage
from donations.models import DonationPledge
from devices.models import DeviceSpecification, Manufacturer
from devices.utils import generate_manual_inventory_number

@login_required
def device_list(request):
    """Device list page with filters."""
    devices_qs = Device.objects.select_related("stage", "location", "donor", "device_specification").all()

    search = request.GET.get("search", "")
    stage_filter = request.GET.get("stage", "")
    grade_filter = request.GET.get("grade", "")
    wipe_filter = request.GET.get("wipe", "")
    parts_filter = request.GET.get("parts", "")
    win11_filter = request.GET.get("win11", "")

    if search:
        devices_qs = devices_qs.filter(
            models.Q(inventory_number__icontains=search)
            | models.Q(serial_number__icontains=search)
        )

    if stage_filter:
        devices_qs = devices_qs.filter(stage__code=stage_filter)

    if grade_filter:
        devices_qs = devices_qs.filter(grade=grade_filter)

    if wipe_filter:
        devices_qs = devices_qs.filter(wipe_status=wipe_filter)

    if parts_filter:
        devices_qs = devices_qs.filter(parts_status=parts_filter)
   
    if win11_filter:
        devices_qs = devices_qs.filter(win11_compatible=win11_filter)

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
            "manufacturer": d.device_specification.manufacturer if d.device_specification else "-",
            "model_name": d.device_specification.model_name if d.device_specification else "-",
            "win11_compatible": d.win11_compatible,
            "allocation_intent": d.allocation_intent,
        })

    return render(request, "device_list.html", {
        "devices": devices,
        "stages": stages,
        "search": search,
        "stage_filter": stage_filter,
        "grade_filter": grade_filter,
        "wipe_filter": wipe_filter,
        "parts_filter": parts_filter,
        "win11_filter": win11_filter,
        "pending_pledges": DonationPledge.objects.filter(status="PENDING").count(),
    })


@login_required
def device_detail(request, pk):
    """Device detail page with stage transition modal."""
    device = get_object_or_404(
        Device.objects.select_related("stage", "location", "donor", "device_specification"),
        pk=pk,
    )
    stages = Stage.objects.all().order_by("sequence")

    default_next_stage = None
    if device.stage:
        default_next_stages = device.stage.allowed_next_stages.all().order_by("sequence")
        if default_next_stages.exists():
            default_next_stage = default_next_stages.first()

    return render(request, "device_detail.html", {
        "device": device,
        "stages": stages,
        "default_next_stage": default_next_stage,
    })


@login_required
def device_edit(request, pk):
    """Device edit page."""
    device = get_object_or_404(
        Device.objects.select_related("stage", "location", "device_specification"),
        pk=pk,
    )
    return render(request, "device_edit.html", {"device": device})

    
    if request.method == "POST":
        # Capture form fields from POST data
        device.grade = request.POST.get("grade", device.grade)
        device.wipe_status = request.POST.get("wipe_status", device.wipe_status)
        device.wipe_notes = request.POST.get("wipe_notes", device.wipe_notes)
        device.parts_status = request.POST.get("parts_status", device.parts_status)
        device.parts_notes = request.POST.get("parts_notes", device.parts_notes)
        device.parts_cost_pounds = request.POST.get("parts_cost_pounds") or 0
        device.notes = request.POST.get("notes", device.notes)
        device.allocation_intent = request.POST.get("allocation_intent", device.allocation_intent)
        device.market_value_pounds = request.POST.get("market_value_pounds") or None
        
        # Update DeviceSpecification fields if present
        if device.device_specification:
            spec = device.device_specification
            spec.manufacturer = request.POST.get("manufacturer", spec.manufacturer)
            spec.model_name = request.POST.get("model_name", spec.model_name)
            spec.model_number = request.POST.get("model_number", spec.model_number)
            spec.processor = request.POST.get("processor", spec.processor)
            spec.memory_gb = request.POST.get("memory_gb") or None
            spec.storage_type = request.POST.get("storage_type", spec.storage_type)
            spec.storage_size_gb = request.POST.get("storage_size_gb") or None
            spec.save()
        
        device.save()
        return redirect(f"/devices/{device.pk}/?saved=1")
        
    
    return render(request, "device_edit.html", {"device": device})

@login_required
def scan_page(request):
    """Scan page for barcode reader workflow."""
    return render(request, "scan.html")


@login_required
@login_required
def manual_device_create(request):
    """Guarded manual device entry for devices that cannot PXE boot."""
    from django.utils import timezone
    from workflow.models import Stage

    manufacturers = Manufacturer.objects.all().order_by("name")
    inventory_number = generate_manual_inventory_number()
    error = None

    if request.method == "POST":
        manufacturer = request.POST.get("manufacturer", "").strip()
        model_name = request.POST.get("model_name", "").strip()
        model_number = request.POST.get("model_number", "").strip()
        serial_number = request.POST.get("serial_number", "").strip()
        processor = request.POST.get("processor", "").strip()
        memory_gb = request.POST.get("memory_gb", "").strip()
        storage_type = request.POST.get("storage_type", "UNKNOWN")
        storage_size_gb = request.POST.get("storage_size_gb", "").strip()
        reason = request.POST.get("reason", "").strip()
        confirmed = request.POST.get("confirmed_pxe_failure") == "yes"

        # Validation
        if not confirmed:
            error = "You must confirm that the device cannot PXE boot."
        elif not manufacturer:
            error = "Manufacturer is required."
        elif not model_name:
            error = "Model name is required."
        elif not serial_number:
            error = "Serial number is required."
        elif not reason:
            error = "Please explain why this device cannot PXE boot."
        else:
            # Check for duplicate serial number
            if Device.objects.filter(serial_number=serial_number).exists():
                error = f"A device with serial number '{serial_number}' already exists."
            elif DeviceSpecification.objects.filter(serial_number=serial_number).exists():
                error = f"A device specification with serial number '{serial_number}' already exists."
            else:
                try:
                    from django.db import transaction

                    with transaction.atomic():
                        # Create the specification
                        spec = DeviceSpecification.objects.create(
                            manufacturer=manufacturer,
                            model_name=model_name,
                            model_number=model_number,
                            serial_number=serial_number,
                            processor=processor,
                            memory_gb=int(memory_gb) if memory_gb else None,
                            storage_type=storage_type,
                            storage_size_gb=int(storage_size_gb) if storage_size_gb else None,
                            source="MANUAL",
                        )

                        # Get RECEIVED stage
                        received_stage = Stage.objects.get(code="RECEIVED")

                        # Create the device
                        device = Device.objects.create(
                            inventory_number=inventory_number,
                            serial_number=serial_number,
                            device_specification=spec,
                            stage=received_stage,
                        )

                    return redirect(f"/devices/{device.pk}/?created=manual")

                except Exception as e:
                    error = f"Failed to create device: {str(e)}"

    return render(request, "manual/create.html", {
        "manufacturers": manufacturers,
        "inventory_number": inventory_number,
        "error": error,
    })
def dashboard(request):
    """Dashboard with stats and stage counts."""
    from devices.models import Device
    from workflow.models import Stage
    from datetime import datetime, timedelta

    now = datetime.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    total_devices = Device.objects.count()
    today_intake = Device.objects.filter(created_at__gte=today_start).count()
    awaiting_parts = Device.objects.filter(parts_status='ORDERED').count()
    ready_to_dispatch = Device.objects.filter(stage__code='AWAITING_DISPATCH').count()

    stages = Stage.objects.all().order_by('sequence')
    max_count = 1
    stage_counts = {}
    for stage in stages:
        count = Device.objects.filter(stage=stage).count()
        stage_counts[stage.code] = count
        if count > max_count:
            max_count = count

    devices_by_stage = []
    for stage in stages:
        count = stage_counts.get(stage.code, 0)
        percent = (count / max_count * 100) if max_count > 0 else 0
        devices_by_stage.append({
            'stage_code': stage.code,
            'stage_name': stage.name,
            'count': count,
            'percent': percent,
        })

    seven_days_ago = now - timedelta(days=7)
    stalled_qs = Device.objects.filter(
        updated_at__lte=seven_days_ago
    ).exclude(
        stage__code__in=['DISPATCHED', 'DONATED', 'RECYCLED']
    ).select_related('stage')

    stalled_list = []
    for d in stalled_qs:
        if d.updated_at:
            days = (now - d.updated_at).days
            if days >= 7:
                stalled_list.append({
                    'id': d.id,
                    'inventory_number': d.inventory_number,
                    'stage_name': d.stage.name if d.stage else 'None',
                    'days_in_stage': days,
                })

    return render(request, 'dashboard.html', {
        'total_devices': total_devices,
        'today_intake': today_intake,
        'awaiting_parts': awaiting_parts,
        'ready_to_dispatch': ready_to_dispatch,
        'devices_by_stage': devices_by_stage,
        'stalled_devices': stalled_list,
    })

@login_required
def stock_available_page(request):
    """Stock available page (front-end for Sales Manager)."""
    return render(request, "stock/available.html")
