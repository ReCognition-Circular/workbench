from rest_framework import serializers

from checklists.models import (
    ChecklistTemplate,
    ChecklistTemplateItem,
    ChecklistInstance,
    ChecklistItemResponse,
    Defect,
    DevicePhoto,
)


# ── Template & Items ─────────────────────────────────────────────────────

class ChecklistTemplateItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChecklistTemplateItem
        fields = [
            "id", "order_number", "section_label", "label", "item_type",
            "options", "is_auto_populated", "auto_source", "cedar_component_key",
            "weight_tier", "photo_required", "max_photos", "generates_defect",
        ]


class ChecklistTemplateSerializer(serializers.ModelSerializer):
    items = ChecklistTemplateItemSerializer(many=True, read_only=True)

    class Meta:
        model = ChecklistTemplate
        fields = ["id", "code", "name", "version", "is_active", "items"]


# ── Responses ────────────────────────────────────────────────────────────

class ChecklistItemResponseSerializer(serializers.ModelSerializer):
    """A single answer — PATCHed on every toggle for auto-save."""
    template_item = ChecklistTemplateItemSerializer(read_only=True)

    class Meta:
        model = ChecklistItemResponse
        fields = [
            "id", "template_item", "defect", "value", "notes",
            "responded_at", "responded_by",
        ]
        read_only_fields = ["id", "template_item", "defect", "responded_at", "responded_by"]


class ChecklistItemResponseUpdateSerializer(serializers.ModelSerializer):
    """Used by the PATCH endpoint — only value and notes are writable."""

    class Meta:
        model = ChecklistItemResponse
        fields = ["value", "notes"]


# ── Instances ────────────────────────────────────────────────────────────

class ChecklistInstanceSerializer(serializers.ModelSerializer):
    responses = ChecklistItemResponseSerializer(many=True, read_only=True)

    class Meta:
        model = ChecklistInstance
        fields = [
            "id", "device", "template", "stage", "status",
            "started_at", "completed_at", "started_by", "completed_by",
            "responses",
        ]
        read_only_fields = ["started_at", "completed_at", "started_by"]


class ChecklistInstanceListSerializer(serializers.ModelSerializer):
    """Lightweight — used in device detail / list views."""
    template_code = serializers.CharField(source="template.code", read_only=True)
    template_name = serializers.CharField(source="template.name", read_only=True)

    class Meta:
        model = ChecklistInstance
        fields = [
            "id", "template_code", "template_name", "stage", "status",
            "started_at", "completed_at",
        ]


# ── Device Photo ─────────────────────────────────────────────────────────

class DevicePhotoSerializer(serializers.ModelSerializer):
    photo_type_display = serializers.CharField(source="get_photo_type_display", read_only=True)

    class Meta:
        model = DevicePhoto
        fields = [
            "id", "device", "photo_type", "photo_type_display", "image", "notes",
            "content_type", "object_id", "captured_at", "captured_by",
            ]

# ── Grade Calculation (returned by the check-in complete endpoint) ───────

class GradeResultSerializer(serializers.Serializer):
    auto_grade = serializers.CharField()
    physical_severity = serializers.CharField()
    cedar_weighted_score = serializers.IntegerField()
    override_reason = serializers.CharField(required=False, allow_blank=True)

