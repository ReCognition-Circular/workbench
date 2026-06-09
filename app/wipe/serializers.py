from rest_framework import serializers
from .models import DataWipeRecord


class DataWipeRecordSerializer(serializers.ModelSerializer):
    device_inventory = serializers.CharField(
        source="device.inventory_number", read_only=True
    )

    class Meta:
        model = DataWipeRecord
        fields = [
            "id", "device", "device_inventory",
            "result", "wipe_method", "wipe_standard",
            "certificate_file", "wiped_by", "wiped_at",
            "uploaded_by", "uploaded_at", "notes",
        ]
        read_only_fields = ["uploaded_by", "uploaded_at"]
