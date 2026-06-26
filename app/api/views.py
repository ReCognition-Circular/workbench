from django.views.generic import TemplateView
from rest_framework.test import APIRequestFactory
from rest_framework.authentication import SessionAuthentication

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
from .serializers import (
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
            "grade": ["exact"],
            "ownership_type": ["exact"],
            "stage__code": ["exact"],
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
        """Scan a device to a location barcode."""
        from locations.models import LocationScan

        device = self.get_object()
        serializer = DeviceLocationUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        location = Location.objects.get(
            code=serializer.validated_data["location_code"]
        )

        device.location = location
        device.save()

        LocationScan.objects.create(
            device=device,
            to_location=location,
            scanned_by=request.user if request.user.is_authenticated else None,
        )

        if request.content_type and 'form' in request.content_type:
            return redirect(f'/devices/{device.id}/')

        return Response(DeviceSerializer(device).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"])
    def transition(self, request, pk=None):
        """Move device to any stage. Creates a StageTransition record for audit."""
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

        # Record the transition
        StageTransition.objects.create(
            device=device,
            from_stage=from_stage,
            to_stage=to_stage,
            transitioned_by=request.user if request.user.is_authenticated else None,
            notes=notes,
        )

        # Update device stage
        device.stage = to_stage
        device.save(update_fields=["stage"])

        serializer = self.get_serializer(device)
        return Response(serializer.data, status=status.HTTP_200_OK)


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
            stage__code="READY",
            allocation_intent__in=["UNDECIDED", "SALE"],
        ).exclude(
            allocations__status="RESERVED"
        ).count()

        # Available for device bank: stage=READY, intent=DEVICE_BANK, no active RESERVED allocation
        available_for_device_bank = Device.objects.filter(
            stage__code="READY",
            allocation_intent="DEVICE_BANK",
        ).exclude(
            allocations__status="RESERVED"
        ).count()

        # Reserved: linked to any active Allocation
        reserved = Device.objects.filter(
            allocations__status="RESERVED"
        ).distinct().count()

        # In pipeline: not READY and not allocated
        in_pipeline = total_devices - available_for_sale - available_for_device_bank - reserved

        # Valuation: sum of market_value_pounds
        available_ids = Device.objects.filter(
            stage__code="READY",
            allocation_intent__in=["UNDECIDED", "SALE"],
        ).exclude(
            allocations__status="RESERVED"
        ).values_list("id", flat=True)

        reserved_ids = Device.objects.filter(
            allocations__status="RESERVED"
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
TERMINAL_STAGES = ['BER', 'DISPOSED', 'DISPATCHED', 'SOLD', 'DONATED', 'RAAS_COMPLETE']


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
        base = Device.objects.exclude(
            stage__code__in=TERMINAL_STAGES
        )

        # Apply optional filters
        type_filter = request.query_params.get("type")
        grade_filter = request.query_params.get("grade")
        win11_filter = request.query_params.get("win11_compatible")
        intent_filter = request.query_params.get("intent")
        min_ram = request.query_params.get("min_memory_gb")
        min_storage = request.query_params.get("min_storage_gb")
        storage_type_filter = request.query_params.get("storage_type")
        processor_filter = request.query_params.get("processor")

        if type_filter:
            base = base.filter(device_type=type_filter)
        if grade_filter:
            base = base.filter(grade=grade_filter)
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
        available_for_sale = base.filter(allocation_intent="SALE").count()
        available_for_device_bank = base.filter(allocation_intent="DEVICE_BANK").count()
        recycling = base.filter(allocation_intent="RECYCLING").count()
        other = base.filter(allocation_intent="OTHER").count()

        # Reserved: devices tagged as RESERVED OR with active allocations
        reserved_ids = set(
            base.filter(allocation_intent="RESERVED").values_list("id", flat=True)
        ) | set(
            Device.objects.filter(allocations__status="RESERVED").values_list("id", flat=True)
        )
        reserved = len(reserved_ids)

        # In pipeline: non-terminal, non-reserved
        in_pipeline_total = Device.objects.exclude(
            stage__code__in=TERMINAL_STAGES
        ).exclude(
            allocations__status="RESERVED"
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
                if device.allocation_intent == "SALE":
                    total_valuation_sale += float(device.market_value_pounds)
                elif device.allocation_intent == "DEVICE_BANK":
                    total_valuation_device_bank += float(device.market_value_pounds)

        data = {
            "needs_classification": needs_classification,
            "available_for_sale": available_for_sale,
            "available_for_device_bank": available_for_device_bank,
            "recycling": recycling,
            "other": other,
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

        return Response({'updated': count})
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
    device.save()
    return Response({'status': 'ok', 'allocation_intent': intent})

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

        if not device_ids or not recipient_id:
            return Response({'error': 'device_ids and recipient_id are required'}, status=400)

        try:
            recipient = Recipient.objects.get(id=recipient_id)
        except Recipient.DoesNotExist:
            return Response({'error': 'Recipient not found'}, status=404)

        devices = Device.objects.filter(id__in=device_ids)
        if not devices.exists():
            return Response({'error': 'No matching devices found'}, status=404)

        count = 0
        for device in devices:
            Allocation.objects.create(
                device=device,
                recipient=recipient,
                status='RESERVED',
                allocation_type='SALE',
                allocated_by=request.user if request.user.is_authenticated else None,
            )
            device.allocation_intent = 'RESERVED'
            device.save(update_fields=['allocation_intent'])
            count += 1

        return Response({'reserved': count})    
class FulfilmentRequestViewSet(viewsets.ReadOnlyModelViewSet):
    """List and detail views for fulfilment requests with allocation progress."""
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
