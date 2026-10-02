from rest_framework import viewsets, mixins, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from .models import DataWipeRecord
from devices.models import Device
from .serializers import DataWipeRecordSerializer


class DataWipeRecordViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    queryset = DataWipeRecord.objects.select_related("device", "uploaded_by").all()
    serializer_class = DataWipeRecordSerializer

    @action(detail=False, methods=["post"], url_path="by-device/(?P<device_id>[^/.]+)")
    def create_for_device(self, request, device_id=None):
        """Upload a wipe certificate for a specific device."""
        try:
            device = Device.objects.get(id=device_id)
        except Device.DoesNotExist:
            return Response(
                {"error": "Device not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = DataWipeRecordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        record = serializer.save(
            device=device,
            uploaded_by=request.user if request.user.is_authenticated else None,
        )

        # Map the wipe record's result onto Device.wipe_status.
        # DataWipeRecord.result: SUCCESS / FAILED / PASS / FAIL / NOT_REQUIRED
        # Device.wipe_status:   the WipeStatus vocabulary
        result = serializer.validated_data.get("result")
        result_to_status = {
            "SUCCESS": "PASS",
            "PASS": "PASS",
            "FAILED": "FAIL",
            "FAIL": "FAIL",
            "NOT_REQUIRED": "N/A",
        }
        new_status = result_to_status.get(result)
        if new_status and new_status != device.wipe_status:
            device.wipe_status = new_status
            device.save(update_fields=["wipe_status"])
        return Response(DataWipeRecordSerializer(record).data, status=status.HTTP_201_CREATED)
