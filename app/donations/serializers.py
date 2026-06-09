from rest_framework import serializers
from .models import DonationPledge, ExpectedDevice


class ExpectedDeviceSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExpectedDevice
        fields = [
            "id", "make", "model", "serial_number", "device_type",
            "matched_device", "status", "interim_id", "notes",
        ]


class DonationPledgeSerializer(serializers.ModelSerializer):
    expected_devices = ExpectedDeviceSerializer(many=True, read_only=True)

    class Meta:
        model = DonationPledge
        fields = [
            "id", "donor_name", "donor_contact", "donor_email",
            "reference_number", "source", "status",
            "transfer_of_title_signed", "notes", "device_list_file",
            "expected_devices", "created_at", "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]


class DonationPledgeCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = DonationPledge
        fields = [
            "donor_name", "donor_contact", "donor_email",
            "reference_number", "source", "notes",
        ]
