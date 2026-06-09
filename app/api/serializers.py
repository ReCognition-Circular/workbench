from rest_framework import serializers
from devices.models import Device, DeviceSpecification, Allocation, Recipient, FulfilmentRequest
from locations.models import Location, Site
from workflow.models import Stage
from donors.models import Donor


class SiteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Site
        fields = '__all__'


class LocationSerializer(serializers.ModelSerializer):
    site = SiteSerializer(read_only=True)
    site_code = serializers.CharField(write_only=True)

    class Meta:
        model = Location
        fields = '__all__'


class StageSerializer(serializers.ModelSerializer):
    allowed_next_stages = serializers.SlugRelatedField(
        many=True, read_only=True, slug_field='code'
    )

    class Meta:
        model = Stage
        fields = '__all__'


class DonorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Donor
        fields = '__all__'


class DeviceSpecificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeviceSpecification
        fields = '__all__'


class DeviceSpecificationWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeviceSpecification
        fields = [
            'manufacturer',
            'model_name',
            'processor',
            'memory_gb',
            'storage_type',
            'storage_size_gb',
            'memory_gb_upgraded',
            'storage_size_gb_upgraded',
            'processor_upgraded',
        ]


class DeviceSerializer(serializers.ModelSerializer):
    device_specification = DeviceSpecificationSerializer(read_only=True)
    location = LocationSerializer(read_only=True)
    stage = StageSerializer(read_only=True)
    donor = DonorSerializer(read_only=True)

    # Write-only fields for creating/updating via API
    location_code = serializers.CharField(write_only=True, required=False)
    stage_code = serializers.CharField(write_only=True, required=False)
    donor_id = serializers.UUIDField(write_only=True, required=False)

    # Write-only nested spec
    device_specification_data = DeviceSpecificationWriteSerializer(
        write_only=True, required=False, source='device_specification'
    )

    class Meta:
        model = Device
        fields = [
            'id',
            'inventory_number',
            'serial_number',
            'device_type',
            'ownership_type',
            'grade',
            'wipe_status',
            'wipe_notes',
            'parts_status',
            'parts_notes',
            'parts_cost_pounds',
            'memory_gb_upgraded',
            'storage_size_gb_upgraded',
            'processor_upgraded',
            'allocation_intent',
            'market_value_pounds',
            'device_specification',
            'device_specification_data',
            'location',
            'manufacturer',
            'model_name',
            'location_code',
            'stage',
            'stage_code',
            'donor',
            'donor_id',
            'notes',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def create(self, validated_data):
        spec_data = validated_data.pop('device_specification', None)
        location_code = validated_data.pop('manufacturer',
            'model_name',
            'location_code', None)
        stage_code = validated_data.pop('stage_code', None)
        donor_id = validated_data.pop('donor_id', None)

        if location_code:
            try:
                validated_data['location'] = Location.objects.get(code=location_code)
            except Location.DoesNotExist:
                raise serializers.ValidationError(
                    {'location_code': f"Location '{location_code}' not found"}
                )

        if stage_code:
            try:
                validated_data['stage'] = Stage.objects.get(code=stage_code)
            except Stage.DoesNotExist:
                raise serializers.ValidationError(
                    {'stage_code': f"Stage '{stage_code}' not found"}
                )

        if donor_id:
            try:
                validated_data['donor'] = Donor.objects.get(id=donor_id)
            except Donor.DoesNotExist:
                raise serializers.ValidationError(
                    {'donor_id': f"Donor with id '{donor_id}' not found"}
                )

        # Create specification FIRST
        if spec_data:
            spec = DeviceSpecification.objects.create(**spec_data)
            validated_data['device_specification'] = spec

        # Create device and link to spec
        device = super().create(validated_data)

        return device

    def update(self, instance, validated_data):
        spec_data = validated_data.pop('device_specification', None)
        location_code = validated_data.pop('manufacturer',
            'model_name',
            'location_code', None)
        stage_code = validated_data.pop('stage_code', None)
        donor_id = validated_data.pop('donor_id', None)

        if location_code:
            try:
                validated_data['location'] = Location.objects.get(code=location_code)
            except Location.DoesNotExist:
                raise serializers.ValidationError(
                    {'location_code': f"Location '{location_code}' not found"}
                )

        if stage_code:
            try:
                validated_data['stage'] = Stage.objects.get(code=stage_code)
            except Stage.DoesNotExist:
                raise serializers.ValidationError(
                    {'stage_code': f"Stage '{stage_code}' not found"}
                )

        if donor_id:
            try:
                validated_data['donor'] = Donor.objects.get(id=donor_id)
            except Donor.DoesNotExist:
                raise serializers.ValidationError(
                    {'donor_id': f"Donor with id '{donor_id}' not found"}
                )

        if spec_data:
            spec = getattr(instance, 'device_specification', None)
            if spec:
                for key, value in spec_data.items():
                    setattr(spec, key, value)
                spec.save()
            else:
                spec = DeviceSpecification.objects.create(**spec_data)
                validated_data['device_specification'] = spec

        return super().update(instance, validated_data)


class DeviceListSerializer(serializers.ModelSerializer):
    manufacturer = serializers.CharField(source="device_specification.manufacturer", read_only=True)
    model_name = serializers.CharField(source="device_specification.model_name", read_only=True)
    location_code = serializers.CharField(source='location.code', read_only=True)
    stage_code = serializers.CharField(source='stage.code', read_only=True)
    stage_name = serializers.CharField(source='stage.name', read_only=True)
    donor_name = serializers.CharField(source='donor.name', read_only=True)

    class Meta:
        model = Device
        fields = [
            'id',
            'inventory_number',
            'serial_number',
            'device_type',
            'grade',
            'manufacturer',
            'model_name',
            'location_code',
            'stage_code',
            'stage_name',
            'donor_name',
            'created_at',
            'updated_at',
        ]


class DeviceLocationUpdateSerializer(serializers.Serializer):
    location_code = serializers.CharField(required=True)

    def validate_location_code(self, value):
        try:
            Location.objects.get(code=value, is_active=True)
        except Location.DoesNotExist:
            raise serializers.ValidationError(
                f"Active location '{value}' not found"
            )
        return value

class StockOverviewSerializer(serializers.Serializer):
    """Read-only serializer for stock overview data."""
    available_for_sale = serializers.IntegerField()
    available_for_device_bank = serializers.IntegerField()
    reserved = serializers.IntegerField()
    in_pipeline = serializers.IntegerField()
    total_devices = serializers.IntegerField()
    valuation_available = serializers.DecimalField(max_digits=10, decimal_places=2)
    valuation_reserved = serializers.DecimalField(max_digits=10, decimal_places=2)
class StockDevicesSerializer(serializers.Serializer):
    """Read-only serializer for a single device in stock query results."""
    inventory_number = serializers.CharField()
    serial_number = serializers.CharField()
    device_type = serializers.CharField()
    grade = serializers.CharField()
    allocation_intent = serializers.CharField()
    stage = serializers.SerializerMethodField()
    memory_gb = serializers.IntegerField(source='device_specification.memory_gb', default=None)
    storage_size_gb = serializers.IntegerField(source='device_specification.storage_size_gb', default=None)
    storage_type = serializers.CharField(source='device_specification.storage_type', default=None)
    processor = serializers.CharField(source='device_specification.processor', default=None)
    win11_compatible = serializers.CharField()
    market_value_pounds = serializers.DecimalField(max_digits=8, decimal_places=2, allow_null=True)

    def get_stage(self, obj):
        return obj.stage.code if obj.stage else None


class StockAvailableSerializer(serializers.Serializer):
    """Read-only serializer for the stock available query response."""
    available_for_sale = serializers.IntegerField()
    available_for_donation = serializers.IntegerField()
    reserved = serializers.IntegerField()
    in_pipeline = serializers.IntegerField()
    matching_devices = StockDevicesSerializer(many=True)
    valuation = serializers.DictField(child=serializers.DecimalField(max_digits=10, decimal_places=2))    
