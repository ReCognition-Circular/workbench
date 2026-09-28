# app/integrations/management/commands/audit_unspecified_serials.py
import json
from django.core.management.base import BaseCommand

from devices.models import Device
from integrations.erpnext_client import ERPNextClient


class Command(BaseCommand):
    help = "Audit LAPTOP-UNSPECIFIED serials in ERPNext against Workbench allocations."

    def handle(self, *args, **options):
        client = ERPNextClient()
        resp = client._request(
            "GET",
            "/api/resource/Serial No",
            params={
                "filters": json.dumps({"item_code": "LAPTOP-UNSPECIFIED"}),
                "fields": json.dumps(["name", "item_code", "status"]),
                "limit_page_length": 500,
            },
        )
        serials = resp.get("data", [])

        self.stdout.write(f"LAPTOP-UNSPECIFIED serials in ERPNext: {len(serials)}\n")

        for s in serials:
            name = s.get("name")
            status = s.get("status")
            device = Device.objects.filter(inventory_number=name).first()

            alloc = None
            if device:
                alloc = (
                    device.allocations
                    .filter(status__in=["RESERVED", "DISPATCHED"])
                    .order_by("-allocated_at")
                    .first()
                )

            alloc_status = alloc.status if alloc else "-"
            fr_code = "-"
            if alloc and alloc.fulfilment_request:
                fr_code = alloc.fulfilment_request.item_code or "-"
            se = device.erpnext_stock_entry if device else "-"

            self.stdout.write(
                f"{name:12} serial_status={status:12} alloc={alloc_status:12} "
                f"fr_item={fr_code:20} device_SE={se}"
            )
