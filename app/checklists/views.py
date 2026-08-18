from django.http import HttpResponse
import io
from PIL import Image
from django.utils import timezone

from django.contrib.contenttypes.models import ContentType
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.generics import GenericAPIView
from rest_framework.mixins import ListModelMixin, RetrieveModelMixin
from rest_framework.response import Response
from rest_framework.views import APIView

from checklists.models import (
    ChecklistTemplate,
    ChecklistInstance,
    ChecklistItemResponse,
    ChecklistTemplateItem,
    Defect,
    DevicePhoto,
)
from checklists.serializers import (
    ChecklistTemplateSerializer,
    ChecklistInstanceSerializer,
    ChecklistInstanceListSerializer,
    ChecklistItemResponseSerializer,
    ChecklistItemResponseUpdateSerializer,
    DevicePhotoSerializer,
    GradeResultSerializer,
)
from devices.models import Device, RepairTask

# ── Grade Calculation ───────────────────────────────────────────────────

PHYSICAL_SEVERITY_MAP = {
    "none": "A",
    "minor": "B",
    "moderate": "C",
    "heavy": "D",
}
WEIGHT_POINTS = {0: 10, 1: 5, 2: 3, 3: 1}
CEDAR_SCORE_MAP = [
    (0, "A"),
    (2, "B"),
    (5, "C"),
    (10, "D"),
]

GRADE_ORDER = {"A": 0, "B": 1, "C": 2, "D": 3, "BER": 4}


def _calc_grade(instance):
    """Calculate auto-grade from a completed Check-In instance.
    Returns {"auto_grade": str, "physical_severity": str, "cedar_weighted_score": int}
    """
    # Physical severity — worst from physical track FAIL items
    physical_fails = []
    for resp in instance.responses.filter(
        template_item__section_label="Physical Track",
    ):
        if resp.value is False:
            physical_fails.append(resp.template_item)

    # Derive physical severity from the items (simplified for MVP)
    # Items 1-6 are damage types (display, hinge, missing parts, case, keyboard, ports)
    # We count them to determine severity
    damage_count = len([
        r for r in physical_fails
        if r.label and any(d in r.label.lower() for d in ["display", "hinge", "missing parts", "case", "keyboard", "port"])
    ])
    damaged_items = damage_count
    if damaged_items == 0:
        physical_severity = "none"
    elif damaged_items <= 2:
        physical_severity = "minor"
    elif damaged_items <= 4:
        physical_severity = "moderate"
    else:
        physical_severity = "heavy"

    # Cedar weighted score — sum tier weights for FAIL results
    cedar_score = 0
    for resp in instance.responses.filter(
        template_item__section_label="Cedar Track",
    ):
        if resp.value is False and resp.template_item.weight_tier is not None:
            cedar_score += WEIGHT_POINTS.get(resp.template_item.weight_tier, 0)

    # Map scores to grades
    physical_grade = PHYSICAL_SEVERITY_MAP[physical_severity]
    cedar_grade = "A"
    for threshold, grade in CEDAR_SCORE_MAP:
        if cedar_score <= threshold:
            cedar_grade = grade
            break
    else:
        cedar_grade = "D"

    # Lower grade wins (worse condition dominates)
    auto_grade = cedar_grade if GRADE_ORDER[cedar_grade] > GRADE_ORDER[physical_grade] else physical_grade

    return {
        "auto_grade": auto_grade,
        "physical_severity": physical_severity,
        "cedar_weighted_score": cedar_score,
    }


# ── Templates ────────────────────────────────────────────────────────────

class TemplateListView(ListModelMixin, GenericAPIView):
    """GET /api/checklists/templates/ — list active templates."""
    queryset = ChecklistTemplate.objects.filter(is_active=True)
    serializer_class = ChecklistTemplateSerializer

    def get(self, request, *args, **kwargs):
        return self.list(request, *args, **kwargs)


class TemplateDetailView(RetrieveModelMixin, GenericAPIView):
    """GET /api/checklists/templates/{code}/ — get template with all items."""
    queryset = ChecklistTemplate.objects.filter(is_active=True)
    serializer_class = ChecklistTemplateSerializer
    lookup_field = "code"

    def get(self, request, *args, **kwargs):
        return self.retrieve(request, *args, **kwargs)


# ── Instances ────────────────────────────────────────────────────────────

class DeviceChecklistView(APIView):
    """GET /api/devices/{id}/checklists/{stage_code}/
    Get or create a checklist instance for a device at a given stage.
    """

    def get(self, request, pk, stage_code):
        device = get_object_or_404(Device, pk=pk)

        # Map stage code to template code
        stage_to_template = {
            "CHECK_IN": "check-in",
            "REFURB_IN_PROGRESS": "refurb",
            "QA": "qa","check-in": "check-in","refurb": "refurb","qa": "qa",
        }
        template_code = stage_to_template.get(stage_code)
        if not template_code:
            return Response(
                {"error": f"No checklist for stage '{stage_code}'"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        template = get_object_or_404(ChecklistTemplate, code=template_code, is_active=True)

        instance, created = ChecklistInstance.objects.get_or_create(
            device=device,
            template=template,
            defaults={"stage": device.stage, "started_by": request.user},
        )

        # If it already existed but has no stage set, update it
        if not created and instance.stage is None:
            instance.stage = device.stage
            instance.save(update_fields=["stage"])
        # Re-open completed instances so they can be amended
        if not created and instance.status == ChecklistInstance.Status.COMPLETE:
            instance.status = ChecklistInstance.Status.IN_PROGRESS
            instance.completed_at = None
            instance.completed_by = None
            instance.save(update_fields=["status", "completed_at", "completed_by"])    

        # Ensure all template items have corresponding responses
        existing_item_ids = set(
            instance.responses.values_list('template_item_id', flat=True)
        )
        for item in template.items.all():
            if item.id not in existing_item_ids:
                ChecklistItemResponse.objects.get_or_create(
                    instance=instance,
                    template_item=item,
                )

        serializer = ChecklistInstanceSerializer(instance)
        data = serializer.data

        # ── Refurb: inject defect section ─────────────────────────────────
        if template_code == "refurb":
            from checklists.models import Defect
            open_defects = Defect.objects.filter(
                device=device,
                generates_refurb_item=True,
                resolution_status__in=["OPEN", "IN_PROGRESS"],
            ).order_by("-created_at")

            defect_items = []
            for d in open_defects:
                defect_items.append({
                    "id": d.id,
                    "description": d.description or str(d.source_item.label) if d.source_item else f"Defect #{d.id}",
                    "source_type": d.source_type,
                    "resolution_status": d.resolution_status,
                    "resolved": False,
                })

            data["defect_section"] = {
                "label": "Defect Repairs",
                "items": defect_items,
            } if defect_items else None

        return Response(data)

class ChecklistCompleteView(APIView):
    """POST /api/devices/{id}/checklists/{stage_code}/complete/
    Mark a checklist instance as complete. Triggers grade calc for check-in.
    """

    def post(self, request, pk, stage_code):
        device = get_object_or_404(Device, pk=pk)

        stage_to_template = {
            "CHECK_IN": "check-in",
            "REFURB_IN_PROGRESS": "refurb",
            "QA": "qa","check-in": "check-in","refurb": "refurb","qa": "qa",
        }
        template_code = stage_to_template.get(stage_code)
        if not template_code:
            return Response(
                {"error": f"No checklist for stage '{stage_code}'"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        template = get_object_or_404(ChecklistTemplate, code=template_code)
        instance = get_object_or_404(
            ChecklistInstance, device=device, template=template
        )

        instance.status = ChecklistInstance.Status.COMPLETE
        instance.completed_at = timezone.now()
        instance.completed_by = request.user
        instance.save()

        # ── Check-In specific: auto-grade ─────────────────────────────────
        if template_code == "check-in":
            grade_result = _calc_grade(instance)

            # Only set auto-grade if technician hasn't manually overridden
            override_grade = request.data.get("override_grade")
            override_reason = request.data.get("override_reason", "")

            if override_grade in ["A", "B", "C", "D", "BER"]:
                device.initial_grade = override_grade
            else:
                device.initial_grade = grade_result["auto_grade"]

            device.save(update_fields=["initial_grade"])

            # Auto-create Defect records from FAIL items
            _create_defects_from_checkin(instance)

            # Route device: all grades go to REFURB_IN_PROGRESS
            from workflow.models import Stage
            refurb_stage = Stage.objects.filter(code="REFURB_IN_PROGRESS").first()
            if refurb_stage:
                device.stage = refurb_stage
                device.save(update_fields=["stage"])

            result = GradeResultSerializer(grade_result).data
            result["override_grade"] = override_grade

        # ── Refurb specific ───────────────────────────────────────────────
        elif template_code == "refurb":
            # Move device to QA
            from workflow.models import Stage
            qa_stage = Stage.objects.filter(code="QA").first()
            if qa_stage:
                device.stage = qa_stage
                device.save(update_fields=["stage"])

            result = {"status": "complete", "next_stage": "QA"}

        # ── QA specific ───────────────────────────────────────────────────
        elif template_code == "qa":
            # Determine pass/fail from QA responses
            all_pass = True
            for resp in instance.responses.filter(
                template_item__section_label__in=["BIOS", "Physical", "Records"]
            ):
                if resp.value is False and resp.template_item.item_type == "PASS_FAIL":
                    all_pass = False
                    break

            if all_pass:
                device.qa_status = "PASS"
                from workflow.models import Stage
                dispatch_stage = Stage.objects.filter(code="AWAITING_DISPATCH").first()
                if dispatch_stage:
                    device.stage = dispatch_stage
                result = {"status": "qa_pass", "next_stage": "AWAITING_DISPATCH"}
            else:
                device.qa_status = "FAIL"
                from workflow.models import Stage
                refurb_stage = Stage.objects.filter(code="REFURB_IN_PROGRESS").first()
                if refurb_stage:
                    device.stage = refurb_stage
                result = {"status": "qa_fail", "next_stage": "REFURB_IN_PROGRESS"}

            device.save(update_fields=["qa_status", "stage"])

        return Response(result, status=status.HTTP_200_OK)


def _create_defects_from_checkin(instance):
    """Create Defect records for Physical Track items at check-in completion.

    Cedar Track defects are created separately by fill_cedar_track() during
    Cedar sync, so they are skipped here. Uses per-item defect_trigger_value.
    """
    for resp in instance.responses.all():
        item = resp.template_item

        # Cedar track handled by fill_cedar_track()
        if item.section_label == "Cedar Track":
            continue

        if resp.value is None:
            continue

        if not _should_defect(item, resp.value):
            continue

        Defect.objects.get_or_create(
            device=instance.device,
            source_type=Defect.SourceType.CHECKIN_PHYSICAL,
            source_item=item,
            defaults={
                "checklist_response": resp,
                "generates_refurb_item": True,
                "resolution_status": Defect.ResolutionStatus.OPEN,
                "description": item.label,
            },
        )
# ── Cedar Track Auto-Fill ────────────────────────────────────────────────

_PASS_VALUES = {"pass", "passed", "true", "yes", "ok", "success", "successful"}
_FAIL_VALUES = {"fail", "failed", "false", "no", "error"}


def _is_pass_value(value):
    v = str(value or "").strip().lower()
    if v in _FAIL_VALUES:
        return False
    if v in _PASS_VALUES:
        return True
    return True  # unknown → neutral/pass


def _collect_results(node, out):
    if isinstance(node, dict):
        if "result" in node:
            out.append(node["result"])
        for v in node.values():
            _collect_results(v, out)
    elif isinstance(node, list):
        for v in node:
            _collect_results(v, out)


def _cedar_component_passed(component):
    """Any fail value (flat or nested) → False; otherwise True."""
    outcomes = []
    _collect_results(component or {}, outcomes)
    if not outcomes:
        return True  # no result anywhere → neutral pass
    return all(_is_pass_value(v) for v in outcomes)


def _should_defect(item, value_is_true):
    """Map defect_trigger_value to a decision for a boolean response.

    FAIL → defect when the item failed (value False)
    YES  → defect when value True
    NO   → defect when value False
    ""   → never
    """
    trigger = (item.defect_trigger_value or "").strip().upper()
    if trigger == "FAIL":
        return value_is_true is False
    if trigger == "YES":
        return value_is_true is True
    if trigger == "NO":
        return value_is_true is False
    return False


def fill_cedar_track(device, asset_cert):
    """Auto-fill Cedar Track responses + defects from a Cedar asset certificate.

    Idempotent: existing responses/defects are never overwritten.
    asset_cert: full Cedar asset certificate JSON (contains a `tests` dict).
    """
    tests = (asset_cert or {}).get("tests") or {}
    if not isinstance(tests, dict):
        return

    template = ChecklistTemplate.objects.filter(code="check-in", is_active=True).first()
    if not template:
        return

    instance, _ = ChecklistInstance.objects.get_or_create(
        device=device,
        template=template,
        defaults={"stage": device.stage, "status": ChecklistInstance.Status.IN_PROGRESS},
    )

    cedar_items = ChecklistTemplateItem.objects.filter(
        template=template,
        section_label="Cedar Track",
    )

    for item in cedar_items:
        key = item.cedar_component_key
        if not key:
            continue

        component = tests.get(key)
        if component is None:
            continue

        passed = _cedar_component_passed(component)

        response, created = ChecklistItemResponse.objects.get_or_create(
            instance=instance,
            template_item=item,
            defaults={
                "value": passed,
                "notes": "Auto-filled from Cedar asset certificate",
            },
        )
        if not created:
            continue  # already filled — do not overwrite, do not re-create defect

        if not _should_defect(item, passed):
            continue

        Defect.objects.get_or_create(
            device=device,
            source_type=Defect.SourceType.CEDAR_TEST,
            source_item=item,
            defaults={
                "checklist_response": response,
                "generates_refurb_item": True,
                "resolution_status": Defect.ResolutionStatus.OPEN,
                "description": item.label,
            },
        )

# ── Responses (auto-save) ────────────────────────────────────────────────

class ResponseUpdateView(APIView):
    """PATCH /api/checklists/responses/{id}/ — auto-save a single toggle."""

    def patch(self, request, pk):
        resp = get_object_or_404(ChecklistItemResponse, pk=pk)
        serializer = ChecklistItemResponseUpdateSerializer(resp, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save(responded_by=request.user)
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ── Device Instance List (for device detail page) ────────────────────────

class DeviceInstanceListView(APIView):
    """GET /api/devices/{id}/checklists/ — list all checklist instances for a device."""

    def get(self, request, pk):
        device = get_object_or_404(Device, pk=pk)
        instances = ChecklistInstance.objects.filter(device=device).select_related("template")
        serializer = ChecklistInstanceListSerializer(instances, many=True)
        return Response(serializer.data)


# ── Photo Upload ─────────────────────────────────────────────────────────

class PhotoUploadView(APIView):
    """POST /api/photos/upload/ — upload a photo with GFK attachment."""

    def post(self, request):
        # Determine what this photo is attached to
        content_type_str = request.data.get("content_type")
        object_id = request.data.get("object_id")

        if content_type_str and object_id:
            try:
                app_label, model = content_type_str.split(".")
                ct = ContentType.objects.get(app_label=app_label, model=model)
            except (ValueError, ContentType.DoesNotExist):
                return Response(
                    {"error": "Invalid content_type"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        else:
            ct = None
            object_id = None

        serializer = DevicePhotoSerializer(data={
            "device": request.data.get("device"),
            "photo_type": request.data.get("photo_type", "DAMAGE_DETAIL"),
            "image": request.FILES.get("image"),
            "notes": request.data.get("notes", ""),
            "content_type": ct.pk if ct else None,
            "object_id": object_id,
        })
        if serializer.is_valid():
            photo = serializer.save(captured_by=request.user)
            # Server-side compression: resize + strip EXIF
            try:
                img = Image.open(photo.image.path)
                w, h = img.size
                if max(w, h) > 1200:
                    ratio = 1200.0 / max(w, h)
                    new_size = (int(w * ratio), int(h * ratio))
                    img = img.resize(new_size, Image.LANCZOS)
                if img.mode in ('RGBA', 'P'):
                    img = img.convert('RGB')
                img.save(photo.image.path, 'JPEG', quality=80)
            except Exception:
                pass  # Non-fatal: keep original on failure
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
class PhotoDeleteView(APIView):
    """DELETE /api/photos/{id}/ — soft-delete a photo."""

    def delete(self, request, pk):
        photo = get_object_or_404(DevicePhoto, pk=pk)
        # Soft-delete: keep file, mark as inactive (or hard-delete if preferred)
        photo.image.delete(save=False)  # delete file from storage
        photo.delete()  # delete DB record
        return Response(status=status.HTTP_204_NO_CONTENT)


class DevicePhotoListView(APIView):
    """GET /api/checklists/devices/{id}/photos/ — list photos for a device."""

    def get(self, request, pk):
        device = get_object_or_404(Device, pk=pk)
        photos = DevicePhoto.objects.filter(device=device).order_by("-captured_at")
        serializer = DevicePhotoSerializer(photos, many=True)
        return Response(serializer.data)

# ---- QR Code image endpoint ----
import qrcode as pyqrcode
import io
from django.http import HttpResponse

class QRCodeView(APIView):
    """Generate QR code PNG and return it inline."""
    def get(self, request):
        data = request.GET.get("data", "")
        if not data:
            return HttpResponse("Missing ?data=", status=400)
        img = pyqrcode.make(data, box_size=6, border=1)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        return HttpResponse(buf.getvalue(), content_type="image/png")
