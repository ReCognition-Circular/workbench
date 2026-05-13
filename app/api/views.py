from rest_framework.permissions import AllowAny
from rest_framework.authentication import SessionAuthentication
from rest_framework import viewsets, mixins, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend

from devices.models import Device
from locations.models import Location, Site
from workflow.models import Stage
from donors.models import Donor

from .serializers import (
    DeviceSerializer,
    DeviceListSerializer,
    DeviceLocationUpdateSerializer,
    LocationSerializer,
    StageSerializer,
    DonorSerializer,
    SiteSerializer,
)

class DeviceViewSet(
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.ListModelMixin,
    viewsets.GenericViewSet,
):
    permission_classes = []
    authentication_classes = []
    
    """
    API endpoint for devices.
    - POST /api/devices/ — Create a new device (called by n8n)
    - GET  /api/devices/ — List all devices (with filters)
    - GET  /api/devices/{id}/ — Get device details
    - PATCH /api/devices/{id}/ — Update a device
    - POST /api/devices/{id}/update_location/ — Scan location barcode
    - POST /api/devices/{id}/transition/ — Move device to next stage
    """

    queryset = Device.objects.select_related(
        "location", "stage", "donor", "device_specification"
    ).all()
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = {
        "device_type": ["exact"],
        "grade": ["exact"],
        "ownership_type": ["exact"],
        "stage__code": ["exact"],
        "location__code": ["exact"],
        "donor__id": ["exact"],
        "created_at": ["gte", "lte"],
    }
    search_fields = [
        "inventory_number",
        "serial_number",
        "notes",
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
        old_location = device.location

        device.location = location
        device.save(update_fields=["location", "updated_at"])

        # Record the scan in history
        LocationScan.objects.create(
            device=device,
            from_location=old_location,
            to_location=location,
            scanned_by=request.user,
            notes=request.data.get("notes", ""),
        )

        return Response(
            {
                "device": device.inventory_number,
                "previous_location": old_location.code if old_location else None,
                "new_location": location.code,
            },
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["post"])
    def transition(self, request, pk=None):
        """Move a device to the next stage."""
        from workflow.services import TransitionService, TransitionError

        device = self.get_object()
        to_stage_code = request.data.get("to_stage_code")

        if not to_stage_code:
            return Response(
                {"error": "to_stage_code is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        service = TransitionService(
            device=device,
            to_stage_code=to_stage_code,
            user=request.user,
            notes=request.data.get("notes", ""),
        )

        try:
            transition = service.execute()
            serializer = self.get_serializer(device)
            return Response(
                {
                    "device": serializer.data,
                    "transition": {
                        "from": transition.from_stage.code if transition.from_stage else None,
                        "to": transition.to_stage.code,
                        "by": str(transition.transitioned_by) if transition.transitioned_by else None,
                        "at": transition.created_at.isoformat(),
                    },
                },
                status=status.HTTP_200_OK,
            )
        except TransitionError as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )


class LocationViewSet(viewsets.ReadOnlyModelViewSet):
    """API endpoint for locations."""

    queryset = Location.objects.select_related("site").all()
    serializer_class = LocationSerializer
    filter_backends = [filters.SearchFilter]
    search_fields = ["code", "barcode", "description"]


class StageViewSet(viewsets.ReadOnlyModelViewSet):
    """API endpoint for workflow stages."""

    queryset = Stage.objects.all()
    serializer_class = StageSerializer
    filter_backends = [filters.SearchFilter]
    search_fields = ["code", "name"]


class DonorViewSet(viewsets.ReadOnlyModelViewSet):
    """API endpoint for donors."""

    queryset = Donor.objects.all()
    serializer_class = DonorSerializer
    filter_backends = [filters.SearchFilter]
    search_fields = ["name", "contact_name", "contact_email"]
