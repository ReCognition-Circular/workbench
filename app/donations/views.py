from rest_framework import viewsets, mixins, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from django_filters.rest_framework import DjangoFilterBackend
from django.shortcuts import render, redirect

import csv
import io

from .models import DonationPledge, ExpectedDevice
from .serializers import (
    DonationPledgeSerializer,
    DonationPledgeCreateSerializer,
    ExpectedDeviceSerializer,
)


class DonationPledgeViewSet(
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.ListModelMixin,
    viewsets.GenericViewSet,
):
    queryset = DonationPledge.objects.prefetch_related("expected_devices").all()
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ["status", "source"]
    search_fields = ["donor_name", "reference_number"]
    ordering_fields = ["created_at"]
    ordering = ["-created_at"]

    def get_permissions(self):
        if self.action == "create":
            return [AllowAny()]
        return super().get_permissions()

    def get_serializer_class(self):
        if self.action == "create":
            return DonationPledgeCreateSerializer
        return DonationPledgeSerializer

    @action(detail=True, methods=["post"])
    def import_csv(self, request, pk=None):
        """Upload a CSV file to create ExpectedDevice records."""
        pledge = self.get_object()
        file = request.FILES.get("file")

        if not file:
            return Response(
                {"error": "CSV file required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            decoded = file.read().decode("utf-8")
            reader = csv.DictReader(io.StringIO(decoded))
        except Exception:
            return Response(
                {"error": "Invalid CSV file"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        created = []
        errors = []

        for row_num, row in enumerate(reader, start=2):
            serial = row.get("serial_number", "").strip()
            make = row.get("make", "").strip()
            model = row.get("model", "").strip()
            device_type = row.get("device_type", "LAPTOP").strip().upper()

            if not serial:
                errors.append(f"Row {row_num}: serial_number is required")
                continue

            ExpectedDevice.objects.create(
                donation_pledge=pledge,
                make=make,
                model=model,
                serial_number=serial,
                device_type=device_type if device_type in dict(ExpectedDevice.device_type.field.choices) else "LAPTOP",
            )
            created.append(serial)

        return Response({
            "pledge": pledge.reference_number,
            "created": len(created),
            "serials": created,
            "errors": errors,
        })


class ExpectedDeviceViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = ExpectedDevice.objects.select_related("donation_pledge", "matched_device").all()
    serializer_class = ExpectedDeviceSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ["status", "device_type", "donation_pledge"]
    search_fields = ["serial_number", "make", "model"]
    ordering = ["donation_pledge", "serial_number"]
import csv
import io
from django.shortcuts import render, redirect
from django.urls import reverse
from .models import DonationPledge, ExpectedDevice


def donate_page(request):
    """Public webform for donors to submit device lists."""
    if request.method == "POST":
        donor_name = request.POST.get("donor_name", "")
        donor_contact = request.POST.get("donor_contact", "")
        donor_email = request.POST.get("donor_email", "")
        notes = request.POST.get("notes", "")
        declaration = request.POST.get("declaration") == "on"

        if not declaration:
            return render(request, "donate.html", {
                "error": "You must confirm you are authorised to donate these devices.",
            })

        # Create the pledge
        import uuid
        reference = f"DON-{uuid.uuid4().hex[:8].upper()}"
        pledge = DonationPledge.objects.create(
            donor_name=donor_name,
            donor_contact=donor_contact,
            donor_email=donor_email,
            reference_number=reference,
            source="WEBFORM",
            notes=notes,
            storage_removed=request.POST.get("storage_removed") == "on",
            transfer_of_title_signed=True,
        )

        # Parse CSV upload
        csv_file = request.FILES.get("csv_file")
        if csv_file:
            decoded = csv_file.read().decode("utf-8")
            reader = csv.DictReader(io.StringIO(decoded))
            for row in reader:
                ExpectedDevice.objects.create(
                    donation_pledge=pledge,
                    make=row.get("make", "").strip(),
                    model=row.get("model", "").strip(),
                    serial_number=row.get("serial_number", "").strip(),
                    device_type=row.get("device_type", "OTHER").strip().upper(),
                    notes=row.get("notes", "").strip(),
                )

        # Parse manual entries
        manual_makes = request.POST.getlist("manual_make[]")
        manual_models = request.POST.getlist("manual_model[]")
        manual_serials = request.POST.getlist("manual_serial[]")
        manual_types = request.POST.getlist("manual_type[]")

        for i in range(len(manual_makes)):
            if manual_makes[i].strip():
                ExpectedDevice.objects.create(
                    donation_pledge=pledge,
                    make=manual_makes[i].strip(),
                    model=manual_models[i].strip(),
                    serial_number=manual_serials[i].strip(),
                    device_type=manual_types[i].strip().upper() if manual_types[i].strip() else "OTHER",
                )

        return redirect(reverse("donate_thanks", kwargs={"reference": reference}))

    return render(request, "donate.html")


def donate_thanks(request, reference):
    """Thank you page after pledge submission."""
    pledge = DonationPledge.objects.get(reference_number=reference)
    return render(request, "donate_thanks.html", {
        "pledge": pledge,
    })
def donate_template(request):
    """Serve CSV template for download."""
    import csv, io
    from django.http import HttpResponse

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="donation_template.csv"'
    
    writer = csv.writer(response)
    writer.writerow(['make', 'model', 'serial_number', 'device_type', 'notes'])
    writer.writerow(['Dell', 'Latitude 5520', 'ABC123', 'LAPTOP', 'Some scuffs on lid'])
    writer.writerow(['HP', 'EliteBook 840', 'XYZ789', 'LAPTOP', ''])
    
    return response    
