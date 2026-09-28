# app/integrations/management/commands/migrate_unspecified_serials.py
import json
import re
from django.core.management.base import BaseCommand

from devices.models import Device
from integrations.erpnext_client import ERPNextClient, ERPNextClientError
from integrations.services import create_stock_entry


class Command(BaseCommand):
    help = "Migrate LAPTOP-UNSPECIFIED serials to their correct item codes."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Print the plan only.")
        parser.add_argument("--only", nargs="*", help="Process only these serial names.")

    def handle(self, *args, **options):
        dry = options["dry_run"]
        only = set(options["only"] or [])

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
        names = [s["name"] for s in resp.get("data", [])]
        if only:
            names = [n for n in names if n in only]

        self.stdout.write(f"Processing {len(names)} serials" + (" (DRY RUN)" if dry else ""))

        for name in names:
            device = Device.objects.filter(inventory_number=name).first()
            alloc = None
            fr_code = None
            if device:
                alloc = (
                    device.allocations
                    .filter(status__in=["RESERVED", "DISPATCHED"])
                    .order_by("-allocated_at")
                    .first()
                )
                if alloc and alloc.fulfilment_request:
                    fr_code = alloc.fulfilment_request.item_code

            se_name = device.erpnext_stock_entry if device else None
            alloc_status = alloc.status if alloc else "-"
            recreate = bool(device and alloc and fr_code and fr_code != "LAPTOP-UNSPECIFIED")

            self.stdout.write(
                f"\n{name}: alloc={alloc_status} fr={fr_code or '-'} SE={se_name or '-'}"
                + ("  -> recreate as " + fr_code if recreate else "")
            )

            if dry:
                if se_name:
                    self.stdout.write(f"    [would] cancel SE {se_name}")
                self.stdout.write("    [would] delete SBB + serial")
                continue

            # 1. Cancel live Stock Entry if present
            if se_name:
                try:
                    client._request("POST", "/api/method/frappe.client.cancel", params={"doctype": "Stock Entry", "name": se_name})
                    self.stdout.write(f"    cancelled SE {se_name}")
                except ERPNextClientError as e:
                    if "cancelled" in str(e).lower():
                        self.stdout.write(f"    SE {se_name} already cancelled")
                    else:
                        self.stdout.write(f"    [warn] cancel SE failed: {e}")

            # 2. Delete SBB + serial
            try:
                client.delete("Serial No", name)
                self.stdout.write("    deleted serial")
            except ERPNextClientError as e:
                m = re.search(r"serial-and-batch-bundle/([0-9a-zA-Z]+)", str(e))
                if not m:
                    self.stdout.write(f"    [fail] no SBB in error: {str(e)[:200]}")
                    continue
                sbb = m.group(1)
                # Cancel the bundle's Stock Entry if the bundle is still submitted
                try:
                    sbb_doc = client.get("Serial and Batch Bundle", sbb)["data"]
                    se_no = sbb_doc.get("voucher_no")
                    if se_no:
                        client._request(
                            "POST", "/api/method/frappe.client.cancel",
                            params={"doctype": "Stock Entry", "name": se_no},
                        )
                        self.stdout.write(f"    cancelled SE {se_no} (via SBB)")
                except ERPNextClientError as e2:
                    if "cancelled" not in str(e2).lower():
                        self.stdout.write(f"    [warn] cancel SE via SBB: {str(e2)[:150]}")
                try:
                    client.delete("Serial and Batch Bundle", sbb)
                    self.stdout.write(f"    deleted SBB {sbb}")
                    client.delete("Serial No", name)
                    self.stdout.write("    deleted serial")
                except ERPNextClientError as e3:
                    self.stdout.write(f"    [fail] after cancel: {str(e3)[:200]}")
                    continue

            # 3. Clear device SE
            if device and device.erpnext_stock_entry:
                device.erpnext_stock_entry = None
                device.save(update_fields=["erpnext_stock_entry"])

            # 4. Recreate under correct item
            if recreate:
                try:
                    new_se = create_stock_entry(device, fr_code)
                    self.stdout.write(f"    [ok] recreated under {fr_code} -> {new_se}")
                except ERPNextClientError as e:
                    self.stdout.write(f"    [fail] recreate: {e}")

        self.stdout.write("\nDone.")
