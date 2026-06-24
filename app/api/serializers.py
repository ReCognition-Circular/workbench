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
    memory_gb = serializers.IntegerField(allow_null=True, required=False)
    storage_size_gb = serializers.IntegerField(allow_null=True, required=False)
    memory_gb_upgraded = serializers.IntegerField(allow_null=True, required=False)
    storage_size_gb_upgraded = serializers.IntegerField(allow_null=True, required=False)

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

    # Manufacturer and model name from device_specification
    manufacturer = serializers.CharField(source='device_specification.manufacturer', read_only=True)
    model_name = serializers.CharField(source='device_specification.model_name', read_only=True)

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
        location_code = validated_data.pop('location_code', None)
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
        location_code = validated_data.pop('location_code', None)
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
    recipient_name = serializers.SerializerMethodField()
    id = serializers.IntegerField()

    def get_stage(self, obj):
        return obj.stage.code if obj.stage else None

    def get_recipient_name(self, obj):
        allocation = obj.allocations.filter(status="RESERVED").first()
        if allocation and allocation.recipient:
            return allocation.recipient.name
        return None

class StockAvailableSerializer(serializers.Serializer):
    """Read-only serializer for the stock available query response."""
    needs_classification = serializers.IntegerField()
    available_for_sale = serializers.IntegerField()
    available_for_device_bank = serializers.IntegerField()
    recycling = serializers.IntegerField()
    other = serializers.IntegerField()
    reserved = serializers.IntegerField()
    total_devices = serializers.IntegerField()
    matching_devices = StockDevicesSerializer(many=True)
    valuation = serializers.DictField(child=serializers.DecimalField(max_digits=10, decimal_places=2))
class RecipientSerializer(serializers.ModelSerializer):
    class Meta:
        model = Recipient
        fields = '__all__'


class AllocationOnRecipientSerializer(serializers.ModelSerializer):
    inventory_number = serializers.CharField(source="device.inventory_number")
    serial_number = serializers.CharField(source="device.serial_number")
    device_type = serializers.CharField(source="device.device_type")
    grade = serializers.CharField(source="device.grade")
    stage = serializers.CharField(source="device.stage.code", default=None)
    wipe_status = serializers.CharField(source="device.wipe_status")
    parts_status = serializers.CharField(source="device.parts_status")
    manufacturer = serializers.CharField(source="device.device_specification.manufacturer", default=None)
    model_name = serializers.CharField(source="device.device_specification.model_name", default=None)

    class Meta:
        model = Allocation
        fields = [
            'id', 'status', 'allocation_type', 'price_pounds',
            'target_ready_by', 'allocated_at', 'dispatched_at',
            'inventory_number', 'serial_number', 'device_type',
            'grade', 'stage', 'wipe_status', 'parts_status',
            'manufacturer', 'model_name',
        ]


class RecipientDetailSerializer(serializers.ModelSerializer):
    allocations = serializers.SerializerMethodField()
    fulfilment_requests = serializers.SerializerMethodField()

    class Meta:
        model = Recipient
        fields = '__all__'

    def get_allocations(self, obj):
        allocations = obj.allocation_set.select_related(
            "device", "device__device_specification", "device__stage"
        ).all()
        return AllocationOnRecipientSerializer(allocations, many=True).data

    def get_fulfilment_requests(self, obj):
        requests = obj.fulfilmentrequest_set.all()
        return FulfilmentRequestOnRecipientSerializer(requests, many=True).data


class FulfilmentRequestOnRecipientSerializer(serializers.ModelSerializer):
    allocated_device_count = serializers.SerializerMethodField()

    class Meta:
        model = FulfilmentRequest
        fields = [
            'id', 'erpnext_order_id', 'summary', 'target_date',
            'status', 'delivery_method', 'delivery_scheduled_date',
            'allocated_device_count',
        ]

    def get_allocated_device_count(self, obj):
        return obj.allocation_set.count()
class DeviceOnFulfilmentSerializer(serializers.ModelSerializer):
    """Read-only serializer for a device within an FR detail view."""
    inventory_number = serializers.CharField(source="device.inventory_number")
    serial_number = serializers.CharField(source="device.serial_number")
    device_type = serializers.CharField(source="device.device_type")
    grade = serializers.CharField(source="device.grade")
    stage = serializers.CharField(source="device.stage.code", default=None)
    stage_name = serializers.CharField(source="device.stage.name", default=None)
    wipe_status = serializers.CharField(source="device.wipe_status")
    parts_status = serializers.CharField(source="device.parts_status")
    manufacturer = serializers.CharField(source="device.device_specification.manufacturer", default=None)
    model_name = serializers.CharField(source="device.device_specification.model_name", default=None)
    processor = serializers.CharField(source="device.device_specification.processor", default=None)
    memory_gb = serializers.IntegerField(source="device.device_specification.memory_gb", default=None)
    allocation_type = serializers.CharField()
    target_ready_by = serializers.DateField()
    allocated_at = serializers.DateTimeField()
    status = serializers.CharField()

    class Meta:
        model = Allocation
        fields = [
            'id', 'inventory_number', 'serial_number', 'device_type',
            'grade', 'stage', 'stage_name', 'wipe_status', 'parts_status',
            'manufacturer', 'model_name', 'processor', 'memory_gb',
            'allocation_type', 'target_ready_by', 'allocated_at', 'status',
        ]


class FulfilmentRequestDetailSerializer(serializers.ModelSerializer):
    """Detail serializer for a single FR — includes devices and stage breakdown."""
    allocated_devices = serializers.SerializerMethodField()
    allocated_count = serializers.SerializerMethodField()
    shortfall = serializers.SerializerMethodField()
    stage_breakdown = serializers.SerializerMethodField()

    class Meta:
        model = FulfilmentRequest
        fields = [
            'id', 'erpnext_order_id', 'erpnext_order_url', 'recipient',
            'summary', 'quantity', 'target_date', 'status',
            'delivery_method', 'delivery_address', 'delivery_scheduled_date',
            'requested_spec', 'notes', 'created_at',
            'allocated_devices', 'allocated_count', 'shortfall', 'stage_breakdown',
        ]

    def get_allocated_devices(self, obj):
        allocations = obj.allocation_set.select_related(
            "device", "device__device_specification", "device__stage"
        ).all()
        return DeviceOnFulfilmentSerializer(allocations, many=True).data

    def get_allocated_count(self, obj):
        return obj.allocation_set.count()

    def get_shortfall(self, obj):
        return max(0, obj.quantity - obj.allocation_set.count())

    def get_stage_breakdown(self, obj):
        stages = {}
        for alloc in obj.allocation_set.select_related("device__stage").all():
            stage_code = alloc.device.stage.code if alloc.device.stage else "NO_STAGE"
            stages[stage_code] = stages.get(stage_code, 0) + 1
        return stages


class FulfilmentRequestListSerializer(serializers.ModelSerializer):
    """List serializer for FR index — summary only."""
    recipient_name = serializers.CharField(source="recipient.name", default=None)
    allocated_count = serializers.SerializerMethodField()
    shortfall = serializers.SerializerMethodField()

    class Meta:
        model = FulfilmentRequest
        fields = [
            'id', 'erpnext_order_id', 'summary', 'quantity',
            'target_date', 'status', 'delivery_method', 'delivery_scheduled_date',
            'recipient_name', 'allocated_count', 'shortfall',
        ]

    def get_allocated_count(self, obj):
        return obj.allocation_set.count()

    def get_shortfall(self, obj):
        return max(0, obj.quantity - obj.allocation_set.count())    
