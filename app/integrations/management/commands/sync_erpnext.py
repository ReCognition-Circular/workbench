import logging
from datetime import datetime

from django.core.management.base import BaseCommand
from devices.models import Recipient
from integrations.erpnext_client import ERPNextClient, ERPNextClientError
from integrations.models import IntegrationLog, CachedProduct
from django.utils import timezone

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Sync Customers → Recipients and Items → CachedProducts from ERPNext"

    def handle(self, *args, **options):
        client = ERPNextClient()
        self.sync_customers(client)
        self.sync_items(client)

    def log_result(self, direction, doctype, action, status, doc_name="", response_code=None, error=""):
        IntegrationLog.objects.create(
            direction=direction,
            doctype=doctype,
            doc_name=doc_name,
            action=action,
            status=status,
            response_code=response_code,
            error_message=error,
            completed_at=timezone.now(),
        )

    # ── Customers ──────────────────────────────────────────
    def sync_customers(self, client):
        self.stdout.write("Syncing Customers from ERPNext...")
        try:
            resp = client.get("Customer", fields=["name", "customer_name", "customer_type", "customer_group"])
        except ERPNextClientError as e:
            self.log_result("OUTBOUND", "Customer", "sync_customers", "FAILED", error=str(e))
            self.stderr.write(f"  FAILED: {e}")
            return

        data = resp.get("data", [])
        self.stdout.write(f"  Found {len(data)} customers")
        for item in data:
            name = item.get("name", "")
            customer_name = item.get("customer_name", name)
            customer_type = item.get("customer_type", "Individual")

            type_map = {
                "Company": "BUSINESS",
                "Individual": "INDIVIDUAL",
                "Non Profit": "CHARITY",
                "Educational Institution": "SCHOOL",
            }
            recipient_type = type_map.get(customer_type, "BUSINESS")

            recipient, created = Recipient.objects.update_or_create(
                erpnext_customer_id=name,
                defaults={
                    "name": customer_name,
                    "recipient_type": recipient_type,
                },
            )
            action = "created" if created else "updated"
            self.stdout.write(f"    {action}: {recipient.name} ({name})")

        self.log_result("OUTBOUND", "Customer", "sync_customers", "SUCCESS")

    # ── Items ──────────────────────────────────────────────
    def sync_items(self, client):
        self.stdout.write("Syncing Items from ERPNext...")
        try:
            resp = client.get("Item", fields=[
                "name", "item_name", "item_group", "has_variants", "variant_of",
            ])
        except ERPNextClientError as e:
            self.log_result("OUTBOUND", "Item", "sync_items", "FAILED", error=str(e))
            self.stderr.write(f"  FAILED: {e}")
            return

        data = resp.get("data", [])
        self.stdout.write(f"  Found {len(data)} items")
        for item in data:
            item_code = item.get("name", "")
            variant_of = item.get("variant_of") or ""

            obj, created = CachedProduct.objects.update_or_create(
                item_code=item_code,
                defaults={
                    "item_name": item.get("item_name", item_code),
                    "item_group": item.get("item_group", ""),
                    "is_variant": bool(item.get("has_variants")),
                    "variant_of": variant_of,
                    "attributes": {},
                },
            )
            action = "created" if created else "updated"
            self.stdout.write(f"    {action}: {obj.item_code} — {obj.item_name}")

        self.log_result("OUTBOUND", "Item", "sync_items", "SUCCESS")
