import logging
from django.core.management.base import BaseCommand
from devices.models import Device
from integrations.services import create_stock_entry
from integrations.erpnext_client import ERPNextClientError

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Create ERPNext Stock Entries for all devices that don't have one yet."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Count devices to process without creating Stock Entries.",
        )

    def handle(self, *args, **options):
        devices = Device.objects.filter(erpnext_stock_entry__isnull=True)
        total = devices.count()
        self.stdout.write(f"Found {total} devices without Stock Entries.")

        if options["dry_run"]:
            self.stdout.write("Dry run — no Stock Entries created.")
            return

        success = 0
        failed = 0
        for device in devices:
            try:
                create_stock_entry(device)
                success += 1
                self.stdout.write(f"  ✅ {device.inventory_number}")
            except ERPNextClientError:
                failed += 1
                self.stdout.write(f"  ❌ {device.inventory_number} — failed")

        self.stdout.write(f"\nDone. {success} succeeded, {failed} failed.")
