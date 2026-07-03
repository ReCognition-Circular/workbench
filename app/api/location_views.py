"""
Location resolution and device scanning endpoints for destination-first workflow.
"""
import json
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from locations.models import Location
from devices.models import Device
from workflow.engine import process_location_scan


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def location_resolve(request):
    """Resolve a location by code or barcode.
    
    GET /api/locations/resolve/?code=MH18D02
    
    Returns location code, description, triggers_stage, and is_active.
    """
    code = request.query_params.get("code", "").strip()
    if not code:
        return JsonResponse({"error": "code parameter is required"}, status=400)
    
    location = (
        Location.objects.filter(code__iexact=code).first()
        or Location.objects.filter(barcode__iexact=code).first()
    )
    
    if not location:
        return JsonResponse({"error": f"Location '{code}' not found"}, status=404)
    
    return JsonResponse({
        "code": location.code,
        "description": location.description or "",
        "triggers_stage": location.triggers_stage or "",
        "is_active": location.is_active,
    })


@csrf_exempt
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def scan_device_to_location(request, code, inventory):
    """Scan a device into a location — triggers stage transition if configured.
    
    POST /api/locations/{code}/scan-device/{inventory}/
    """
    location = get_object_or_404(Location, code__iexact=code)
    device = get_object_or_404(Device, inventory_number=inventory)
    
    result = process_location_scan(
        device=device,
        location=location,
        user=request.user if request.user.is_authenticated else None,
    )
    
    return JsonResponse({
        "inventory_number": device.inventory_number,
        "location_code": location.code,
        "location_description": location.description or "",
        "message": result.get("message", ""),
        "location_changed": result.get("location_changed", False),
        "stage_changed": result.get("stage_changed", False),
        "new_stage": result.get("new_stage"),
    })
