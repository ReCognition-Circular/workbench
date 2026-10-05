from django.views.generic import TemplateView
from rest_framework.test import APIRequestFactory
from rest_framework.authentication import SessionAuthentication
import logging

logger = logging.getLogger(__name__)
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework import viewsets, mixins, status, filters
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.views import APIView
from django.shortcuts import redirect
import django_filters
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Q, Sum, Count

from devices.models import Device, Allocation, DeviceSpecification, AllocationIntent, Recipient, FulfilmentRequest
from django.db.models import Sum
from locations.models import Location, Site
from workflow.models import Stage
from donors.models import Donor
from devices.models import InventorySequence
from django.utils import timezone
from django.conf import settings
from integrations.erpnext_client import ERPNextClient, ERPNextClientError
from integrations.models import IntegrationLog
from integrations.cedar_api import search_erasure_certificates, search_asset_certificates, search_asset_certificates_by_serials, CedarAPIError
from wipe.models import DataWipeRecord, AuditRecord
from wipe.pdf_generator import generate_wipe_certificate, generate_audit_certificate
from .serializers import (
    CustomerSerializer,    
    DeviceSerializer,
    DeviceListSerializer,
    LocationSerializer,
    StageSerializer,
    DonorSerializer,
    SiteSerializer,
    DeviceLocationUpdateSerializer,
    StockOverviewSerializer,
    StockAvailableSerializer,
    RecipientSerializer,
    RecipientDetailSerializer,
    AllocationOnRecipientSerializer,
    FulfilmentRequestOnRecipientSerializer,
    FulfilmentRequestListSerializer,
    FulfilmentRequestDetailSerializer,
)
from rest_framework.authentication import TokenAuthentication
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from locations.models import Location
from devices.models import Device
from checklists.views import fill_cedar_track
from integrations.services import create_stock_entry

class DeviceFilter(django_filters.FilterSet):
    """Custom filter set for DeviceViewSet supporting related model fields."""
    manufacturer = django_filters.CharFilter(
        field_name="device_specification__manufacturer",
        lookup_expr="icontains",
    )
    model_number = django_filters.CharFilter(
        field_name="device_specification__model_number",
        lookup_expr="icontains",
    )
    model_name = django_filters.CharFilter(
        field_name="device_specification__model_name",
        lookup_expr="icontains",
    )
    location_code = django_filters.CharFilter(
        field_name="location__code",
        lookup_expr="icontains",
    )
    location_id = django_filters.NumberFilter(
        field_name="location__id",
        lookup_expr="exact",
    )
    
    class Meta:
        model = Device
        fields = {
            "device_type": ["exact"],
            "initial_grade": ["exact"],
            "final_grade": ["exact"],
      "ownership_type": ["exact"],

            "donor__id": ["exact"],
            "created_at": ["gte", "lte"],
            "allocation_intent": ["exact"],
        }


class DeviceViewSet(
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.ListModelMixin,
    viewsets.GenericViewSet,
):
    permission_classes = [AllowAny]
    authentication_classes = [SessionAuthentication]

    queryset = Device.objects.select_related(
        "device_specification", "location", "stage", "donor"
    ).all()
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = DeviceFilter
    search_fields = [
        "inventory_number",
        "serial_number",
        "notes",
        "device_specification__manufacturer",
        "device_specification__model_name",
        "device_specification__model_number",
    ]
    ordering_fields = [
        "created_at",
        "updated_at",
        "inventory_number",
    ]
    ordering = ["-created_at"]

    def get_serializer_class(self):
        if self.action == "list":
            return DeviceListSerializer
        return DeviceSerializer
    def perform_create(self, serializer):
        """Create device and run serial matching against ExpectedDevice."""
        serial_number = serializer.validated_data.get("serial_number", "")

        device = serializer.save()

        if serial_number:
            from donations.models import ExpectedDevice
            match = ExpectedDevice.objects.filter(
                serial_number=serial_number,
                status="EXPECTED",
            ).first()
            if match:
                device.donation_pledge = match.donation_pledge
                device.save(update_fields=["donation_pledge"])
                match.matched_device = device
                match.status = "RECEIVED"
                match.save(update_fields=["matched_device", "status"])

                # If donor confirmed storage removed/already wiped, flag the device
                if match.donation_pledge.storage_removed:
                    device.wipe_status = "DONOR_WIPED"
                    device.save(update_fields=["wipe_status"])

        # Auto-transition: RECEIVED → CHECK_IN (FOG/n8n devices land at RECEIVED)
        if device.stage and device.stage.code == 'RECEIVED':
            from workflow.models import Stage
            check_in = Stage.objects.get(code='CHECK_IN')
            device.stage = check_in
            device.save(update_fields=['stage'])
        
    def update(self, request, *args, **kwargs):
        """Override update to redirect if coming from a form POST."""
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)

        # If this is a form POST (not JSON), redirect to the device detail page
        if request.content_type and 'form' in request.content_type:
            return redirect(f'/devices/{instance.id}/')

        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def update_location(self, request, pk=None):
        """Scan a device to a location — triggers stage transition if configured."""
        from workflow.engine import process_location_scan

        device = self.get_object()
        serializer = DeviceLocationUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        location = Location.objects.get(
            code=serializer.validated_data["location_code"]
        )   

        result = process_location_scan(
            device=device,
            location=location,
            user=request.user if request.user.is_authenticated else None,
        )

        if request.content_type and 'form' in request.content_type:
            return redirect(f'/devices/{device.id}/')

        return Response(DeviceSerializer(device).data, status=status.HTTP_200_OK)


    @action(detail=True, methods=["post"])
    def transition(self, request, pk=None):
        """Move device to a stage, validated by the shared workflow gate."""
        from workflow.engine import validate_stage_transition
        from workflow.models import Stage, StageTransition

        device = self.get_object()
        from_stage = device.stage

        to_stage_code = request.data.get("to_stage_code")
        notes = request.data.get("notes", "")

        if not to_stage_code:
            return Response(
                {"error": "to_stage_code is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            to_stage = Stage.objects.get(code=to_stage_code)
        except Stage.DoesNotExist:
            return Response(
                {"error": f"Stage '{to_stage_code}' not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        allowed, warning_stage, block_reason = validate_stage_transition(device, to_stage)

        if not allowed:
            return Response(
                {"error": block_reason},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Update device stage (+ soft-gate warning flag)
        device.stage = to_stage
        update_fields = ["stage"]

        if warning_stage:
            device.checklist_warning = True
            device.checklist_warning_stage = warning_stage
            update_fields += ["checklist_warning", "checklist_warning_stage"]

        device.save(update_fields=update_fields)

        # Record the transition
        StageTransition.objects.create(
            device=device,
            from_stage=from_stage,
            to_stage=to_stage,
            transitioned_by=request.user if request.user.is_authenticated else None,
            notes=notes,
        )

        serializer = self.get_serializer(device)
        return Response(serializer.data, status=status.HTTP_200_OK)
    @action(detail=True, methods=["post"], url_path="sync-cedar")
    def sync_cedar(self, request, pk=None):
        """
        Pull Cedar Enterprise certificates for this device.
        Erasure certs match by drive serial; asset certs match by
        device serial (normalised variants), so audit sync works even
        when the device has no drive.
        """
        device = self.get_object()

        drive_serials = []
        spec = getattr(device, 'device_specification', None)
        if spec and spec.drive_serial:
            drive_serials = [s.strip() for s in spec.drive_serial.split(",") if s.strip()]

        results = {
            "erasure": {"found": 0, "pass": 0, "fail": 0, "drives": []},
            "asset": {"found": 0, "pass": 0, "fail": 0, "audits": []},
        }
        all_erasure_data = []

        # --- Erasure certificates (drive serial scope) ---
        for drive_sn in drive_serials:
            try:
                erasure_resp = search_erasure_certificates(drive_sn)
                certs = erasure_resp.get("certificates", {}).get("data", [])
                if certs:
                    results["erasure"]["found"] += len(certs)
                    all_erasure_data.extend(certs)
                    for cert in certs:
                        if _result_is_fail(_cert_field(cert, "result")):
                            results["erasure"]["fail"] += 1
                        else:
                            results["erasure"]["pass"] += 1
                results["erasure"]["drives"].append({
                    "serial": drive_sn,
                    "found": len(certs),
                })
            except CedarAPIError as e:
                results["erasure"]["drives"].append({"serial": drive_sn, "error": str(e)})

        # --- Asset certificates (device serial scope, normalised) ---
        try:
            asset_resp = search_asset_certificates_by_serials(
                _serial_variants(device.serial_number)
            )
            asset_certs = asset_resp.get("certificates", {}).get("data", [])
        except CedarAPIError as e:
            asset_certs = []
            results["asset"]["audits"].append({"error": str(e)})

        if asset_certs:
            results["asset"]["found"] = len(asset_certs)
            for cert in asset_certs:
                if _tests_have_fail(cert.get("tests")):
                    results["asset"]["fail"] += 1
                else:
                    results["asset"]["pass"] += 1

        else:
            # No erasure certificate was found. Only downgrade a status that
            # claims a Cedar-derived outcome (PASS/FAIL) AND only when we
            # actually queried at least one drive serial — otherwise we have
            # not proven the cert is absent, we simply did not look.
            #
            # Devices that legitimately have no Cedar cert are exempted:
            # donor-wiped, no storage media, not applicable, wiped externally.
            queried = [
                d for d in results["erasure"]["drives"]
                if d.get("serial") and not d.get("error")
            ]
            non_cedar_states = {
                "DONOR_WIPED",
                "NO_STORAGE",
                "N/A",
                "PENDING",
                "WIPED_EXTERNAL",
            }
            if queried and device.wipe_status not in non_cedar_states:
                logger.info(
                    "Cedar erasure sync: no cert for %s (drive serials queried: %s); "
                    "wipe_status %s -> PENDING",
                    device.inventory_number,
                    [d["serial"] for d in queried],
                    device.wipe_status,
                )
                device.wipe_status = "PENDING"
                device.save(update_fields=["wipe_status"])
        # --- Create/update DataWipeRecord from erasure results ---
        wipe_record = None
        if all_erasure_data:
            if any(_result_is_fail(_cert_field(c, "result", "Pass"))
                   for c in all_erasure_data):
                worst = "FAIL"
            else:
                worst = "PASS"

            first_cert = all_erasure_data[0]
            wipe_standard = _cert_field(first_cert, "standard", "")
            wipe_level = _cert_field(first_cert, "level", "")
            wipe_method = (
                f"{wipe_standard} {wipe_level}".strip() if wipe_level else wipe_standard
            )

            wipe_record, _ = DataWipeRecord.objects.update_or_create(
                device=device,
                certificate_type="ERASE",
                defaults={
                    "result": worst,
                    "wipe_standard": wipe_standard,
                    "wipe_method": wipe_method,
                    "json_data": {"erasure_results": all_erasure_data},
                    "notes": f"Synced from Cedar: {len(all_erasure_data)} drive(s)",
                },
            )
            device.wipe_status = worst
            device.save(update_fields=["wipe_status"])
            generate_wipe_certificate(device, wipe_record)

            if device.stage and device.stage.code == 'CHECK_IN':
                from checklists.models import (
                    ChecklistTemplate, ChecklistInstance,
                    ChecklistItemResponse, ChecklistTemplateItem,
                )
                try:
                    ct_checkin = ChecklistTemplate.objects.get(code='check-in')
                    instance, _ = ChecklistInstance.objects.get_or_create(
                        device=device,
                        template=ct_checkin,
                        defaults={'stage': device.stage, 'status': 'IN_PROGRESS'},
                    )
                    wipe_items = ChecklistTemplateItem.objects.filter(
                        template=ct_checkin,
                        auto_source='DATAWIPE_RECORD',
                    )
                    for wipe_item in wipe_items:
                        ChecklistItemResponse.objects.update_or_create(
                            instance=instance,
                            template_item=wipe_item,
                            defaults={
                                'value': (worst == 'PASS'),
                                'notes': f'Auto-filled from Cedar sync — {len(all_erasure_data)} drive(s)',
                            },
                        )
                except Exception as e:
                    logger.warning(f'Checklist auto-fill skipped: {e}')

        # --- Create/update AuditRecords from asset results ---
        asset_certs.sort(
            key=lambda item: (
                item.get("created_at")
                or item.get("id")
                or item.get("uuid")
                or ""
            )
        )

        audit_records_created = []
        initial_audit_record = None
        latest_audit_record = None

        for cert in asset_certs:
            cert_id = cert.get("id") or cert.get("uuid")
            result = "FAIL" if _tests_have_fail(cert.get("tests")) else "PASS"

            audit_record, _created = AuditRecord.objects.update_or_create(
                device=device,
                cedar_certificate_id=cert_id,
                defaults={
                    "result": result,
                    "test_results": cert,
                    "auditor": "Cedar Enterprise",
                    "notes": f"Device serial: {device.serial_number}",
                },
            )
            audit_records_created.append(audit_record)

            if initial_audit_record is None:
                initial_audit_record = audit_record
            latest_audit_record = audit_record
            try:
                audit_record.certificate_file.name = (
                    f"audit_certs/{device.inventory_number}_{audit_record.id}_audit.pdf"
                )
                generate_audit_certificate(device, audit_record)
                audit_record.save(update_fields=["certificate_file"])
            except Exception as e:
                logger.warning(f"Audit certificate generation skipped: {e}")

        if initial_audit_record:
            update_fields = []

            # initial_audit is frozen — set once, never overwritten
            if device.initial_audit is None:
                device.initial_audit = initial_audit_record
                device.initial_audit_status = "PASS" if initial_audit_record.result == "PASS" else "FAIL"
                update_fields.append("initial_audit_status")
                update_fields.append("initial_audit")

            device.latest_audit = latest_audit_record
            update_fields.append("latest_audit")

            # final_audit at QA: must be a cert NEWER than initial_audit
            if (
                device.stage
                and device.stage.code == "QA"
                and latest_audit_record
                and latest_audit_record.id != device.initial_audit_id
            ):
                device.final_audit = latest_audit_record
                device.final_audit_status = (
                    "PASS" if latest_audit_record.result == "PASS" else "FAIL"
                )
                update_fields += ["final_audit", "final_audit_status"]

            device.save(update_fields=update_fields)

            if device.stage and device.stage.code == "CHECK_IN":
                try:
                    fill_cedar_track(device, initial_audit_record.test_results or {})
                except Exception as e:
                    logger.warning(f"Cedar track auto-fill skipped: {e}")

        return Response({
            "device_id": device.id,
            "inventory_number": device.inventory_number,
            "drive_serials_queried": drive_serials,
            "erasure": {
                "found": results["erasure"]["found"],
                "pass": results["erasure"]["pass"],
                "fail": results["erasure"]["fail"],
                "wipe_record_id": wipe_record.id if wipe_record else None,
                "wipe_status": device.wipe_status,
            },
            "asset": {
                "found": results["asset"]["found"],
                "pass": results["asset"]["pass"],
                "fail": results["asset"]["fail"],
                "audit_record_ids": [a.id for a in audit_records_created],
                "audit_count": len(audit_records_created),
                "initial_audit_id": initial_audit_record.id if initial_audit_record else None,
                "latest_audit_id": latest_audit_record.id if latest_audit_record else None,
                "final_audit_id": device.final_audit_id,
            },
        })

    @action(detail=True, methods=["post"], url_path="set-erasure-exception")
    def set_erasure_exception(self, request, pk=None):
        """Grant or revoke an erasure exception for this device.

        An exception is permission, not evidence — it records that Cedar
        erasure is not required, and who decided that.

        POST {"action": "grant", "category": "...", "reason": "...", "note": "..."}
        POST {"action": "revoke"}
        """
        from devices.models import ErasureExceptionCategory, ErasureExceptionReason

        device = self.get_object()
        do = (request.data.get("action") or "").strip().lower()

        if do == "grant":
            category = (request.data.get("category") or "").strip()
            reason = (request.data.get("reason") or "").strip()
            note = (request.data.get("note") or "").strip()

            if category not in ErasureExceptionCategory.values:
                return Response(
                    {"error": "Invalid category. Use one of: "
                              + ", ".join(ErasureExceptionCategory.values)},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if reason not in ErasureExceptionReason.values:
                return Response(
                    {"error": "Invalid reason. Use one of: "
                              + ", ".join(ErasureExceptionReason.values)},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if reason == ErasureExceptionReason.OTHER and not note:
                return Response(
                    {"error": "A note is required when reason is OTHER."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            device.erasure_required = False
            device.erasure_exception_category = category
            device.erasure_exception_reason = reason
            device.erasure_exception_note = note
            device.erasure_exception_by = (
                request.user if getattr(request.user, "is_authenticated", False) else None
            )
            device.erasure_exception_at = timezone.now()
            device.save(update_fields=[
                "erasure_required",
                "erasure_exception_category",
                "erasure_exception_reason",
                "erasure_exception_note",
                "erasure_exception_by",
                "erasure_exception_at",
            ])
            return Response({
                "status": "granted",
                "erasure_required": False,
                "category": category,
                "reason": reason,
            })

        if do == "revoke":
            device.erasure_required = True
            device.erasure_exception_category = ""
            device.erasure_exception_reason = ""
            device.erasure_exception_note = ""
            device.erasure_exception_by = None
            device.erasure_exception_at = None
            device.save(update_fields=[
                "erasure_required",
                "erasure_exception_category",
                "erasure_exception_reason",
                "erasure_exception_note",
                "erasure_exception_by",
                "erasure_exception_at",
            ])
            return Response({"status": "revoked", "erasure_required": True})

        return Response(
            {"error": "action must be 'grant' or 'revoke'."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    @action(detail=True, methods=["post"], url_path="pat")
    def pat(self, request, pk=None):
        device = self.get_object()

        pat_status = (request.data.get("pat_status") or "").strip() or None
        if pat_status is not None and pat_status not in ("PASS", "FAIL", "N/A"):
            return Response(
                {"detail": "pat_status must be PASS, FAIL or N/A"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        pass_id = (request.data.get("pat_pass_id") or "").strip() or None
        justification = (request.data.get("pat_justification") or "").strip() or None

        device.pat_status = pat_status
        device.pat_pass_id = pass_id
        device.pat_justification = justification
        device.save(update_fields=["pat_status", "pat_pass_id", "pat_justification"])

        return Response(self.get_serializer(device).data)

    @action(detail=True, methods=["post"], url_path="override-gate")
    def override_gate(self, request, pk=None):
        """Record an exceptional approval to bypass a QA gate (audit trail only)."""
        device = self.get_object()
        gate = request.data.get("gate")
        justification = (request.data.get("justification") or "").strip()
        valid_gates = {"defects": "defects", "final_audit": "final_audit"}
        if gate not in valid_gates:
            return Response(
                {"error": "Invalid gate. Use 'defects' or 'final_audit'."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not justification:
            return Response(
                {"error": "Justification is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        from devices.models import GateOverride
        overridden_by = (
            request.user.username
            if getattr(request.user, "is_authenticated", False)
            else (request.data.get("overridden_by") or "")
        )
        override, _created = GateOverride.objects.update_or_create(
            device=device,
            gate=valid_gates[gate],
            defaults={
                "justification": justification,
                "overridden_by": overridden_by,
            },
        )
        return Response({
            "status": "overridden",
            "gate": gate,
            "override_id": override.id,
            "overridden_by": overridden_by,
        })

_FAIL_VALUES = {"fail", "failed", "false", "no", "not_passed", "error"}


def _result_is_fail(value):
    return str(value or "").strip().lower() in _FAIL_VALUES

def _serial_variants(serial):
    """Return uppercase serial variants with separators removed and 0/O, 1/I ambiguity swapped."""
    s = str(serial or "").strip().upper()
    if not s:
        return []
    # Also try a separator-stripped form: 'R9-0HRCQD' -> 'R90HRCQD'
    base = s.replace("-", "").replace(" ", "").replace("_", "")
    seeds = {s, base}
    variants = set()
    for seed in seeds:
        variants.update({
            seed,
            seed.replace("0", "O"),
            seed.replace("O", "0"),
            seed.replace("1", "I"),
            seed.replace("I", "1"),
            seed.replace("0", "O").replace("1", "I"),
            seed.replace("O", "0").replace("I", "1"),
        })
    return sorted(variants)

def _cert_field(cert, field, default=None):
    """Read a Cedar field from metadata.report.process, falling back to top-level."""
    proc = ((cert or {}).get("metadata") or {}).get("report", {}).get("process", {}) or {}
    val = proc.get(field)
    if val not in (None, ""):
        return val
    return (cert or {}).get(field, default)


def _tests_have_fail(tests):
    """True if any flat or nested `result` in Cedar's `tests` payload is failing."""
    def scan(node):
        if isinstance(node, dict):
            if "result" in node and _result_is_fail(node.get("result")):
                return True
            for v in node.values():
                if scan(v):
                    return True
        elif isinstance(node, list):
            for v in node:
                if scan(v):
                    return True
        return False
    return scan(tests or {})

class LocationViewSet(viewsets.ModelViewSet):
    queryset = Location.objects.select_related("site").all()
    serializer_class = LocationSerializer
    authentication_classes = [SessionAuthentication]
    permission_classes = [AllowAny]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = {
        "site__code": ["exact"],
        "is_active": ["exact"],
    }
    search_fields = ["code", "description"]


class StageViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Stage.objects.all()
    serializer_class = StageSerializer
    authentication_classes = [SessionAuthentication]
    permission_classes = [AllowAny]


class DonorViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Donor.objects.all()
    serializer_class = DonorSerializer
    authentication_classes = [SessionAuthentication]
    permission_classes = [AllowAny]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = {
        "status": ["exact"],
    }
    search_fields = ["name", "email"]


class SiteViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Site.objects.all()
    serializer_class = SiteSerializer
    authentication_classes = [SessionAuthentication]
    permission_classes = [AllowAny]
class StockOverviewView(APIView):
    """Returns aggregated stock overview data for the Coordinator dashboard."""

    authentication_classes = [SessionAuthentication]
    permission_classes = [AllowAny]

    def get(self, request):
        total_devices = Device.objects.count()

        # Available for sale: stage=READY, intent=UNDECIDED or SALE, no active RESERVED allocation
        available_for_sale = Device.objects.filter(
            stage__code="AWAITING_DISPATCH",
            allocation_intent__in=["UNDECIDED", "FOR_SALE"],
        ).exclude(
            allocations__status__in=["RESERVED", "DISPATCHED"]
        ).count()

        # Available for device bank: stage=READY, intent=DEVICE_BANK, no active RESERVED allocation
        available_for_device_bank = Device.objects.filter(
            stage__code="AWAITING_DISPATCH",
            allocation_intent="DEVICE_BANK",
        ).exclude(
            allocations__status__in=["RESERVED", "DISPATCHED"]
        ).count()

        # Reserved: linked to any active Allocation
        reserved = Device.objects.filter(
            allocations__status__in=["RESERVED", "DISPATCHED"]
        ).distinct().count()

        # In pipeline: not READY and not allocated
        in_pipeline = total_devices - available_for_sale - available_for_device_bank - reserved

        # Valuation: sum of market_value_pounds
        available_ids = Device.objects.filter(
            stage__code="AWAITING_DISPATCH",
            allocation_intent__in=["UNDECIDED", "FOR_SALE"],
        ).exclude(
            allocations__status__in=["RESERVED", "DISPATCHED"]
        ).values_list("id", flat=True)

        reserved_ids = Device.objects.filter(
            allocations__status__in=["RESERVED", "DISPATCHED"]
        ).values_list("id", flat=True)

        valuation_available = (
            Device.objects.filter(id__in=available_ids)
            .aggregate(total=Sum("market_value_pounds"))["total"] or 0
        )
        valuation_reserved = (
            Device.objects.filter(id__in=reserved_ids)
            .aggregate(total=Sum("market_value_pounds"))["total"] or 0
        )

        data = {
            "available_for_sale": available_for_sale,
            "available_for_device_bank": available_for_device_bank,
            "reserved": reserved,
            "in_pipeline": in_pipeline,
            "total_devices": total_devices,
            "valuation_available": valuation_available,
            "valuation_reserved": valuation_reserved,
        }

        serializer = StockOverviewSerializer(data)
        return Response(serializer.data)
IN_STOCK_STAGES = ['CHECK_IN', 'REFURB_IN_PROGRESS', 'QA', 'AWAITING_DISPATCH']


class StockAvailableView(APIView):
    """
    Returns available devices matching the given filters.
    
    Used by the Sales Manager to check stock before committing to an order.
    Used by the Coordinator to find matching devices for allocation.
    
    A device is 'available' if:
      - stage is not a terminal stage
      - allocation_intent matches the query (or UNDECIDED, which counts for both)
      - no active RESERVED allocation exists for this device
    """
    authentication_classes = [SessionAuthentication]
    permission_classes = [AllowAny]

    def get(self, request):
        # Base: devices in non-terminal stages, no active reservation
        base = Device.objects.filter(
           stage__code__in=IN_STOCK_STAGES
        )  

        # Apply optional filters
        type_filter = request.query_params.get("type")
        initial_grade_filter = request.query_params.get("initial_grade")
        final_grade_filter = request.query_params.get("final_grade")
        win11_filter = request.query_params.get("win11_compatible")
        intent_filter = request.query_params.get("intent")
        min_ram = request.query_params.get("min_memory_gb")
        min_storage = request.query_params.get("min_storage_gb")
        storage_type_filter = request.query_params.get("storage_type")
        processor_filter = request.query_params.get("processor")

        if type_filter:
            base = base.filter(device_type=type_filter)
        if initial_grade_filter:
            base = base.filter(initial_grade=initial_grade_filter)
        if final_grade_filter:
            base = base.filter(final_grade=final_grade_filter)
        if win11_filter:
            base = base.filter(win11_compatible=win11_filter)
        if intent_filter:
            base = base.filter(allocation_intent=intent_filter)

        # Spec-based filters
        spec_filters = {}
        if min_ram:
            spec_filters["memory_gb__gte"] = int(min_ram)
        if min_storage:
            spec_filters["storage_size_gb__gte"] = int(min_storage)
        if storage_type_filter:
            spec_filters["storage_type"] = storage_type_filter
        if processor_filter:
            spec_filters["processor__icontains"] = processor_filter
        if spec_filters:
            matching_specs = DeviceSpecification.objects.filter(**spec_filters)
            base = base.filter(device_specification__in=matching_specs)

        # Count by intent (no overlap)
        needs_classification = base.filter(allocation_intent="UNDECIDED").count()
        available_for_sale = base.filter(allocation_intent="FOR_SALE").count()
        available_for_device_bank = base.filter(allocation_intent="DEVICE_BANK").count()
        recycling = base.filter(allocation_intent="RECYCLE").count()

        # Reserved: devices tagged as RESERVED OR with active allocations
        reserved_ids = set(
            base.filter(allocation_intent="RESERVED").values_list("id", flat=True)
        ) | set(
            Device.objects.filter(allocations__status__in=["RESERVED", "DISPATCHED"]).values_list("id", flat=True)
        )
        reserved = len(reserved_ids)

        # In pipeline: non-terminal, non-reserved
        in_pipeline_total = Device.objects.filter(
            stage__code__in=IN_STOCK_STAGES
        ).exclude(
            allocations__status__in=["RESERVED", "DISPATCHED"]
        ).count()

        # Matching devices (max 100) with allocation recipient info
        matching = base.select_related(
            "device_specification", "stage", "donor"
        ).prefetch_related(
            "allocations__recipient"
        ).distinct()[:100]

        # Valuation
        total_valuation_sale = 0
        total_valuation_device_bank = 0
        for device in matching:
            if device.market_value_pounds:
                if device.allocation_intent == "FOR_SALE":
                    total_valuation_sale += float(device.market_value_pounds)
                elif device.allocation_intent == "DEVICE_BANK":
                    total_valuation_device_bank += float(device.market_value_pounds)

        data = {
            "needs_classification": needs_classification,
            "available_for_sale": available_for_sale,
            "available_for_device_bank": available_for_device_bank,
            "recycle": recycling,
            "reserved": reserved,
            "total_devices": base.count(),
            "matching_devices": matching,
            "valuation": {
                "sale": total_valuation_sale,
                "device_bank": total_valuation_device_bank,
            },
        }

        serializer = StockAvailableSerializer(data)
        return Response(serializer.data)
def _cancel_active_allocations(device_ids):
    """Cancel RESERVED allocations for the given devices.
    Returns (number_cancelled, set_of_affected_fulfilment_request_ids).
    """
    cancelled = 0
    fr_ids = set()
    for alloc in Allocation.objects.filter(
        device_id__in=device_ids, status='RESERVED'
    ).select_related('fulfilment_request'):
        alloc.status = 'CANCELLED'
        alloc.cancelled_at = timezone.now()
        alloc.save(update_fields=['status', 'cancelled_at'])
        cancelled += 1
        if alloc.fulfilment_request_id:
            fr_ids.add(alloc.fulfilment_request_id)
    return cancelled, fr_ids


def _refresh_fulfilment_request_statuses(fr_ids):
    """Recompute FR status after allocations change."""
    for fr in FulfilmentRequest.objects.filter(id__in=fr_ids):
        if fr.status in ('COMPLETE', 'CANCELLED'):
            continue
        active_count = Allocation.objects.filter(
            fulfilment_request=fr,
            status__in=['RESERVED', 'DISPATCHED'],
        ).count()
        if active_count == 0:
            new_status = 'PENDING'
        elif fr.quantity > 0 and active_count >= fr.quantity:
            new_status = 'READY'
        else:
            new_status = 'IN_PROGRESS'
        if fr.status != new_status:
            fr.status = new_status
            fr.save(update_fields=['status'])
class StockBulkUpdateView(APIView):
    """Update allocation_intent for multiple devices at once."""
    authentication_classes = [SessionAuthentication]
    permission_classes = [IsAuthenticated]
    def post(self, request):
        device_ids = request.data.get('device_ids', [])
        allocation_intent = request.data.get('allocation_intent')

        if not device_ids or not allocation_intent:
            return Response({'error': 'device_ids and allocation_intent are required'}, status=400)

        valid_intents = [c.value for c in AllocationIntent]
        if allocation_intent not in valid_intents:
            return Response({'error': f'invalid intent. Must be one of: {", ".join(valid_intents)}'}, status=400)

        count = Device.objects.filter(id__in=device_ids).update(
            allocation_intent=allocation_intent
        )

        cancelled = 0
        if allocation_intent != 'RESERVED':
            cancelled, fr_ids = _cancel_active_allocations(device_ids)
            _refresh_fulfilment_request_statuses(fr_ids)

        return Response({'updated': count, 'cancelled': cancelled})

@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def update_device_intent(request, pk):
    """Update allocation_intent for a single device."""
    try:
        device = Device.objects.get(pk=pk)
    except Device.DoesNotExist:
        return Response({'error': 'Device not found'}, status=404)

    intent = request.data.get('allocation_intent')
    if not intent:
        return Response({'error': 'allocation_intent is required'}, status=400)

    valid_intents = [c.value for c in AllocationIntent]
    if intent not in valid_intents:
        return Response({'error': f'invalid intent. Must be one of: {", ".join(valid_intents)}'}, status=400)

    device.allocation_intent = intent
    device.save(update_fields=['allocation_intent'])

    cancelled = 0
    if intent != 'RESERVED':
        cancelled, fr_ids = _cancel_active_allocations([device.id])
        _refresh_fulfilment_request_statuses(fr_ids)

    return Response({'status': 'ok', 'allocation_intent': intent, 'cancelled': cancelled})


class CoordinatorDashboardView(TemplateView):
    template_name = "coordinator/dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        factory = APIRequestFactory()
        request = factory.get("/api/stock/overview/")
        response = StockOverviewView.as_view()(request)
        context["stock"] = response.data
        return context


FOG_PREFIX = '6'


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def next_inventory_number(request):
    """Return the next available inventory number.
    
    Format: {FOG_PREFIX}{MMDD}{SEQ:04d}
    Example: 605220001
    
    Uses atomic PostgreSQL UPDATE ... RETURNING to guarantee
    no gaps and no duplicates under concurrent calls.
    """
    from django.utils import timezone
    from django.db import transaction
    
    now = timezone.now()
    month = now.month
    day = now.day
    date_prefix = f"{month:02d}{day:02d}"
    
    try:
        with transaction.atomic():
            seq, created = InventorySequence.objects.select_for_update().get_or_create(
                date_prefix=date_prefix,
                defaults={'current_number': 0}
            )
            
            seq.current_number += 1
            seq.save(update_fields=['current_number'])
            
            sequence_number = seq.current_number
    except Exception as e:
        return Response(
            {'error': f'Failed to generate inventory number: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
    
    inventory_number = f"{FOG_PREFIX}{date_prefix}{sequence_number:04d}"
    
    return Response({
        'inventory_number': inventory_number,
        'date_prefix': date_prefix,
        'sequence_number': sequence_number,
        'fog_prefix': FOG_PREFIX,
    })

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def check_serial(request):
    """Check if a serial number already exists in Workbench."""
    serial = request.GET.get('serial', '').strip()
    if not serial:
        return Response({'error': 'serial parameter required'}, status=status.HTTP_400_BAD_REQUEST)
    
    exists = Device.objects.filter(serial_number=serial).exists()
    
    return Response({'exists': exists, 'serial_number': serial})    

class RecipientViewSet(viewsets.ModelViewSet):
    """CRUD for recipients. Detail view includes allocated devices."""
    queryset = Recipient.objects.all()
    serializer_class = RecipientSerializer
    authentication_classes = [SessionAuthentication]
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = {
        "recipient_type": ["exact"],
    }
    search_fields = ["name", "contact_email", "contact_phone"]

    def retrieve(self, request, *args, **kwargs):
        """Override detail to include allocations and fulfilment requests."""
        instance = self.get_object()
        serializer = RecipientDetailSerializer(instance)
        return Response(serializer.data)
class ReserveView(APIView):
    """Reserve devices for a recipient — creates Allocation records."""
    authentication_classes = [SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        device_ids = request.data.get('device_ids', [])
        recipient_id = request.data.get('recipient_id')
        fulfilment_request_id = request.data.get('fulfilment_request_id')

        if not device_ids or not recipient_id:
            return Response({'error': 'device_ids and recipient_id are required'}, status=400)

        try:
            recipient = Recipient.objects.get(id=recipient_id)
        except Recipient.DoesNotExist:
            return Response({'error': 'Recipient not found'}, status=404)

        fulfilment_request = None
        if fulfilment_request_id:
            try:
                fulfilment_request = FulfilmentRequest.objects.get(id=fulfilment_request_id)
            except FulfilmentRequest.DoesNotExist:
                return Response({'error': 'FulfilmentRequest not found'}, status=404)

        devices = list(Device.objects.filter(id__in=device_ids))
        if not devices:
            return Response({'error': 'No matching devices found'}, status=404)

        # Guard 1: skip devices that already have an active allocation
        already_reserved_ids = set(
            Allocation.objects.filter(
                device_id__in=device_ids,
                status__in=['RESERVED', 'DISPATCHED'],
            ).values_list('device_id', flat=True)
        )
        devices = [d for d in devices if d.id not in already_reserved_ids]
        skipped = len(already_reserved_ids)

        # Guard 2: do not exceed the FulfilmentRequest quantity
        remaining = None
        if fulfilment_request and fulfilment_request.quantity > 0:
            active_count = Allocation.objects.filter(
                fulfilment_request=fulfilment_request,
                status__in=['RESERVED', 'DISPATCHED'],
            ).count()
            remaining = fulfilment_request.quantity - active_count
            if remaining <= 0:
                return Response({
                    'error': f"Order {fulfilment_request.erpnext_order_id} is already fully "
                             f"allocated ({fulfilment_request.quantity} devices)."
                }, status=400)
            if len(devices) > remaining:
                return Response({
                    'error': f"Only {remaining} slot(s) remain on order "
                             f"{fulfilment_request.erpnext_order_id}, but {len(devices)} were selected."
                }, status=400)

        count = 0
        for device in devices:
            Allocation.objects.create(
                device=device,
                recipient=recipient,
                fulfilment_request=fulfilment_request,
                status='RESERVED',
                allocation_type='SALE',
                allocated_by=request.user if request.user.is_authenticated else None,
            )
            device.allocation_intent = 'RESERVED'
            device.save(update_fields=['allocation_intent'])

            # Push Stock Entry to ERPNext under the correct item code
            # (serial is created here, at allocation time — not at intake)
            if fulfilment_request and fulfilment_request.item_code:
                try:
                    create_stock_entry(device, fulfilment_request.item_code)
                except ERPNextClientError:
                    # Logged in IntegrationLog — allocation still created locally
                    pass
            count += 1

        # Keep FR status accurate
        if fulfilment_request:
            total_active = Allocation.objects.filter(
                fulfilment_request=fulfilment_request,
                status__in=['RESERVED', 'DISPATCHED'],
            ).count()
            if fulfilment_request.quantity > 0 and total_active >= fulfilment_request.quantity:
                fulfilment_request.status = 'READY'
            elif total_active > 0:
                fulfilment_request.status = 'IN_PROGRESS'
            else:
                fulfilment_request.status = 'PENDING'
            fulfilment_request.save(update_fields=['status'])

        return Response({'reserved': count, 'skipped': skipped})

class FulfilmentRequestViewSet(viewsets.ModelViewSet):
    """CRUD for Fulfilment Requests."""
    queryset = FulfilmentRequest.objects.select_related("recipient").all()    
    authentication_classes = [SessionAuthentication]
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = {
        "status": ["exact"],
        "recipient": ["exact"],
    }
    search_fields = ["erpnext_order_id", "summary"]

    def get_serializer_class(self):
        if self.action == "list":
            return FulfilmentRequestListSerializer
        return FulfilmentRequestDetailSerializer

    def get_queryset(self):
        qs = FulfilmentRequest.objects.select_related("recipient").all()
        if self.action == "retrieve":
            qs = qs.prefetch_related(
                "allocation_set__device__device_specification",
                "allocation_set__device__stage",
            )
        return qs    
    @action(detail=True, methods=['post'], url_path='dispatch')
    def execute_dispatch(self, request, pk=None):
        """Dispatch all RESERVED allocations for this FR.
        
        Transitions allocations to DISPATCHED, records dispatched_at,
        and pushes a Delivery Note to ERPNext with all device serial numbers.
        """
        fr = self.get_object()
        
        # Find all RESERVED allocations for this FR
        allocations = fr.allocation_set.filter(status='RESERVED')
        # Partial despatch support: optionally restrict to specific devices.
        # Frontend can POST {"inventory_numbers": ["607160003"]} to despatch a subset.
        inventory_numbers = request.data.get('inventory_numbers')
        if inventory_numbers:
            if not isinstance(inventory_numbers, (list, tuple)):
                return Response(
                    {'error': 'inventory_numbers must be a list'},
                    status=400,
                )
            allocations = allocations.filter(
                device__inventory_number__in=inventory_numbers
            )
        
        if not allocations.exists():
            return Response(
                {'error': 'No RESERVED allocations found to dispatch'},
                status=400
            )
        # Quantity guard: don't dispatch more than the order requests
        if fr.quantity > 0:
            already_dispatched = fr.allocation_set.filter(status='DISPATCHED').count()
            remaining = fr.quantity - already_dispatched
            to_dispatch = allocations.count()
            if to_dispatch > remaining:
                return Response({
                    'error': (
                        f"Cannot dispatch {to_dispatch} device(s): only {remaining} "
                        f"slot(s) remain on order {fr.erpnext_order_id} "
                        f"({already_dispatched} of {fr.quantity} already dispatched)."
                    ),
                }, status=400)    
        
        devices = []
        for alloc in allocations:
            alloc.status = 'DISPATCHED'
            alloc.dispatched_at = timezone.now()
            alloc.save(update_fields=['status', 'dispatched_at'])
            
            if alloc.device:
                alloc.device.stage = None
                alloc.device.save(update_fields=['stage'])
                devices.append(alloc.device)
        
        # Update FR status based on how much of the order is now dispatched
        if fr.quantity > 0:
            total_dispatched = fr.allocation_set.filter(status='DISPATCHED').count()
            if total_dispatched >= fr.quantity:
                fr.status = 'COMPLETE'
            elif total_dispatched > 0:
                fr.status = 'IN_PROGRESS'
            else:
                fr.status = 'PENDING'
        else:
            # No quantity recorded — treat as complete if nothing is left RESERVED
            fr.status = (
                'COMPLETE'
                if not fr.allocation_set.filter(status='RESERVED').exists()
                else 'IN_PROGRESS'
            )
        fr.save(update_fields=['status'])
        
        # Push Delivery Note to ERPNext
        dn_result = None
        try:
            client = ERPNextClient()

            # Serials already exist in ERPNext (created by the allocation-time
            # Stock Entry). Reference them directly — do NOT create them here.
            serial_numbers = [
                d.inventory_number for d in devices if d.inventory_number
            ]
            
            dn_data = {
                "doctype": "Delivery Note",
                "customer": (fr.recipient.erpnext_customer_id or fr.recipient.name) if fr.recipient else "",
                "company": settings.ERPNEXT_COMPANY,
                "set_warehouse": settings.ERPNEXT_DEFAULT_WAREHOUSE,
                "items": [
                    {
                        "item_code": fr.item_code or "LAPTOP-UNSPECIFIED",
                        "qty": len(devices),
                        "serial_no": "\n".join(serial_numbers),
                        "warehouse": settings.ERPNEXT_DEFAULT_WAREHOUSE,
                    }
                ],
            }
            
            dn_response = client.create("Delivery Note", dn_data)
            dn_name = dn_response.get("data", {}).get("name", "unknown")
            
            # Store the DN reference on allocations
            for alloc in allocations:
                alloc.erpnext_dn_reference = dn_name
                alloc.save(update_fields=['erpnext_dn_reference'])
            
            IntegrationLog.objects.create(
                direction="OUTBOUND",
                doctype="Delivery Note",
                doc_name=dn_name,
                action="create",
                status="SUCCESS",
                completed_at=timezone.now(),
            )
            
            dn_result = {"name": dn_name, "status": "created"}
            
        except (ERPNextClientError, Exception) as e:
            logger.exception("Failed to push Delivery Note to ERPNext")
            IntegrationLog.objects.create(
                direction="OUTBOUND",
                doctype="Delivery Note",
                action="create",
                status="FAILED",
                error_message=str(e),
                completed_at=timezone.now(),
            )
            # Still return success for the dispatch itself
            dn_result = {"error": str(e)}
        
        return Response({
            "status": "dispatched",
            "allocations_dispatched": len(devices),
            "delivery_note": dn_result,
            "fr_status": fr.status,
        })    
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def resolve_barcode(request):
    """Resolve a barcode string to a location, device, or unknown.
    
    GET /api/resolve-barcode/?code=MH18D02
    GET /api/resolve-barcode/?code=605220042
    """
    code = request.query_params.get('code', '').strip()
    if not code:
        return Response({'error': 'code parameter is required'}, status=status.HTTP_400_BAD_REQUEST)
    
    # Try location first (locations have short codes like INT-01, SH-A1, MH18D02)
    location = Location.objects.filter(code__iexact=code, is_active=True).first()
    if location:
        return Response({
            'type': 'location',
            'id': location.code,
            'code': location.code,
            'name': location.description,
            'triggers_stage': location.triggers_stage,
        })
    
    # Try device (inventory numbers like 605220042, 606160001)
    device = Device.objects.filter(inventory_number=code).first()
    if device:
        stage_code = device.stage.code if device.stage else None
        location_code = device.location.code if device.location else None
        return Response({
            'type': 'device',
            'id': device.id,
            'inventory_number': device.inventory_number,
            'serial_number': device.serial_number,
            'stage': stage_code,
            'location': location_code,
            'device_type': device.device_type,
        })
    
    return Response({'type': 'unknown', 'code': code}, status=status.HTTP_404_NOT_FOUND)    
class CustomerWebhookView(APIView):
    """
    Webhook receiver for ERPNext Customer sync.
    POST /api/integration/customer/
    """
    authentication_classes = []
    permission_classes = [AllowAny]

    CUSTOMER_GROUP_MAP = {
        'Commercial': 'BUSINESS',
        'Device Bank': 'CHARITY',
        'eBay': 'BUSINESS',
        'Individual': 'INDIVIDUAL',
    }

    def post(self, request):
        try:
            data = request.data
            # Handle both wrapped {"doc": {...}} and bare payloads
            if 'doc' in data:
                data = data['doc']

            serializer = CustomerSerializer(data=data)
            if not serializer.is_valid():
                IntegrationLog.objects.create(
                    action='CUSTOMER_SYNC',
                    status='ERROR',
                    request_payload=request.data,
                    response_body=serializer.errors,
                )
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

            erpnext_id = serializer.validated_data['name']
            customer_name = serializer.validated_data['customer_name']
            customer_group = serializer.validated_data.get('customer_group', '')

            # Map customer group to recipient type
            recipient_type = self.CUSTOMER_GROUP_MAP.get(
                customer_group, 'INDIVIDUAL'
            )

            recipient, created = Recipient.objects.update_or_create(
                erpnext_customer_id=erpnext_id,
                defaults={
                    'name': customer_name,
                    'recipient_type': recipient_type,
                }
            )

            IntegrationLog.objects.create(
                action='CUSTOMER_SYNC',
                status='SUCCESS',
                request_payload=request.data,
                response_body={'recipient_id': recipient.id, 'created': created},
            )

            return Response({
                'status': 'success',
                'recipient_id': recipient.id,
                'created': created,
            }, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)

        except Exception as e:
            logger.exception("CustomerWebhookView error")
            IntegrationLog.objects.create(
                action='CUSTOMER_SYNC',
                status='ERROR',
                request_payload=request.data,
                response_body={'error': str(e)},
            )
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
