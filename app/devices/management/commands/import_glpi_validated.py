import csv
import re
from django.core.management.base import BaseCommand
from devices.models import Device, DeviceSpecification, DeviceType
from workflow.models import Stage


def parse_stage(glpi_status):
    if not glpi_status:
        return "VISUAL_INSPECTION"
    status = glpi_status.strip().lower()
    if "refurb complete" in status:
        return "QA_PASS"
    elif "refurb in progress" in status:
        return "REPAIR"
    elif "refurb pending" in status:
        return "VISUAL_INSPECTION"
    else:
        return "VISUAL_INSPECTION"


def parse_device_type(glpi_type):
    if not glpi_type:
        return DeviceType.LAPTOP
    t = glpi_type.strip().lower()
    if "laptop" in t or "notebook" in t:
        return DeviceType.LAPTOP
    elif "desktop" in t or "mini" in t or "tower" in t or "sff" in t:
        return DeviceType.DESKTOP
    elif "all in one" in t or "imac" in t:
        return DeviceType.ALL_IN_ONE
    elif "tablet" in t or "ipad" in t:
        return DeviceType.TABLET
    elif "server" in t:
        return DeviceType.SERVER
    else:
        return DeviceType.LAPTOP


def clean_serial(serial):
    if not serial:
        return ""
    s = serial.strip()
    if len(s) > 50 or s.lower() in ("", "0", "none", "n/a", "unknown"):
        return ""
    return s


class Command(BaseCommand):
    help = "Import validated devices from GLPI CSV export"

    def add_arguments(self, parser):
        parser.add_argument("csv_file", type=str, help="Path to CSV file")
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Preview without creating anything",
        )

    def handle(self, *args, **options):
        path = options["csv_file"]
        dry_run = options["dry_run"]
        created = 0
        skipped = 0
        errors = []

        with open(path, encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row_num, row in enumerate(reader, start=2):
                inventory = row.get("Inventory number", "").strip()
                serial = clean_serial(row.get("Serial number", ""))
                model = row.get("Model", "").strip()
                glpi_status = row.get("Status", "").strip()
                glpi_type = row.get("Type", "").strip()
                comments = row.get("Comments", "").strip()
                processor = row.get("Components - Processor", "").strip()

                if not inventory:
                    skipped += 1
                    continue

                if Device.objects.filter(inventory_number=inventory).exists():
                    self.stdout.write(f"  SKIP (exists): {inventory}")
                    skipped += 1
                    continue

                device_type = parse_device_type(glpi_type)
                stage_code = parse_stage(glpi_status)

                try:
                    stage = Stage.objects.get(code=stage_code)
                except Stage.DoesNotExist:
                    errors.append(f"Row {row_num}: Stage '{stage_code}' not found for {inventory}")
                    skipped += 1
                    continue

                manufacturer = ""
                if model:
                    parts = model.split(None, 1)
                    manufacturer = parts[0] if parts else ""

                if dry_run:
                    self.stdout.write(
                        f"  WOULD CREATE: {inventory} | {serial} | {manufacturer} {model} | "
                        f"{device_type} | {stage_code}"
                    )
                    created += 1
                    continue

                try:
                    spec = DeviceSpecification.objects.create(
                        manufacturer=manufacturer,
                        model_name=model,
                        serial_number=serial if serial else f"glpi-{inventory}",
                        processor=processor,
                        source="MANUAL",
                    )
                    device = Device.objects.create(
                        inventory_number=inventory,
                        serial_number=serial,
                        device_type=device_type,
                        stage=stage,
                        notes=comments,
                        ownership_type="DONATION",
                    )
                    device.device_specification = spec
                    device.save(update_fields=["device_specification"])
                    created += 1
                    self.stdout.write(f"  CREATED: {inventory} ({manufacturer} {model}) → {stage_code}")
                except Exception as e:
                    errors.append(f"Row {row_num}: {inventory} - {str(e)}")
                    skipped += 1

        self.stdout.write("\n" + "=" * 50)
        self.stdout.write(self.style.SUCCESS(f"Created: {created}"))
        self.stdout.write(f"Skipped: {skipped}")
        if errors:
            self.stdout.write(self.style.WARNING(f"Errors: {len(errors)}"))
            for err in errors[:10]:
                self.stdout.write(f"  {err}")
            if len(errors) > 10:
                self.stdout.write(f"  ... and {len(errors) - 10} more")
