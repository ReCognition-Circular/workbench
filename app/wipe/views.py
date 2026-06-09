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

        # Update device wipe_status based on result
        result = serializer.validated_data.get("result")
        if result == "SUCCESS":
            device.wipe_status = "PASS"
        elif result == "FAILED":
            device.wipe_status = "FAIL"
        elif result == "NOT_REQUIRED":
            device.wipe_status = "NO_STORAGE"
        device.save(update_fields=["wipe_status"])

        return Response(DataWipeRecordSerializer(record).data, status=status.HTTP_201_CREATED)
