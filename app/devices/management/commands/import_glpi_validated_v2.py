import csv
import re
from django.core.management.base import BaseCommand
from devices.models import Device, DeviceSpecification, StorageType, SpecSource
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
        return "LAPTOP"
    t = glpi_type.strip().lower()
    if "laptop" in t or "notebook" in t:
        return "LAPTOP"
    elif "desktop" in t or "mini" in t or "tower" in t or "sff" in t:
        return "DESKTOP"
    elif "all in one" in t or "imac" in t:
        return "ALL_IN_ONE"
    elif "tablet" in t or "ipad" in t:
        return "TABLET"
    elif "server" in t:
        return "SERVER"
    else:
        return "LAPTOP"


def clean_serial(serial):
    if not serial:
        return ""
    s = serial.strip()
    if len(s) > 100 or s.lower() in ("", "0", "none", "n/a", "unknown"):
        return ""
    return s


def parse_memory_gb(memory_str):
    if not memory_str:
        return None
    memory_str = memory_str.strip()
    match = re.search(r"(\d+(?:\.\d+)?)\s*(?:Gi?B|GB)", memory_str, re.IGNORECASE)
    if match:
        return round(float(match.group(1)))
    match = re.search(r"(\d+)", memory_str)
    if match:
        return int(match.group(1))
    return None


def parse_storage(storage_str):
    if not storage_str:
        return "UNKNOWN", None
    storage_str = storage_str.strip()
    upper = storage_str.upper()
    if "NVME" in upper:
        storage_type = "NVME"
    elif "SSD" in upper or "SATA" in upper:
        storage_type = "SSD"
    elif "HDD" in upper or "HARD DRIVE" in upper:
        storage_type = "HDD"
    elif "EMMC" in upper:
        storage_type = "EMMC"
    else:
        storage_type = "UNKNOWN"
    match = re.search(r"(\d+)\s*(?:GB|TB)", storage_str, re.IGNORECASE)
    if match:
        size = int(match.group(1))
        tb_match = re.search(r"(\d+)\s*TB", storage_str, re.IGNORECASE)
        if tb_match:
            size = int(tb_match.group(1)) * 1024
        return storage_type, size
    return storage_type, None


class Command(BaseCommand):
    help = "Import devices from GLPI CSV export (v2 - with memory/storage parsing)"

    def add_arguments(self, parser):
        parser.add_argument("csv_file", type=str, help="Path to CSV file")
        parser.add_argument("--dry-run", action="store_true", help="Preview without creating")

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
                model_str = row.get("Model", "").strip()
                glpi_status = row.get("Status", "").strip()
                glpi_type = row.get("Type", "").strip()
                comments = row.get("Comments", "").strip()
                manufacturer_str = row.get("Manufacturer", "").strip()
                processor = row.get("Components - Processor", "").strip()
                memory_str = row.get("Components - Memory type", "").strip()
                storage_str = row.get("Components - Hard drive type", "").strip()

                if not inventory:
                    skipped += 1
                    continue

                if Device.objects.filter(inventory_number=inventory).exists():
                    self.stdout.write(f"  SKIP (exists): {inventory}")
                    skipped += 1
                    continue

                device_type = parse_device_type(glpi_type)
                stage_code = parse_stage(glpi_status)
                memory_gb = parse_memory_gb(memory_str)
                storage_type, storage_size_gb = parse_storage(storage_str)

                if not manufacturer_str and model_str:
                    manufacturer_str = model_str.split(None, 1)[0]

                try:
                    stage = Stage.objects.get(code=stage_code)
                except Stage.DoesNotExist:
                    errors.append(f"Row {row_num}: Stage '{stage_code}' not found for {inventory}")
                    skipped += 1
                    continue

                if dry_run:
                    self.stdout.write(
                        f"  WOULD CREATE: {inventory} | {serial} | {manufacturer_str} {model_str} | "
                        f"Type={device_type} | Stage={stage_code} | RAM={memory_gb}GB | "
                        f"Storage={storage_type}:{storage_size_gb}GB | CPU={processor}"
                    )
                    created += 1
                    continue

                try:
                    spec = DeviceSpecification.objects.create(
                        manufacturer=manufacturer_str,
                        model_name=model_str,
                        serial_number=serial if serial else f"glpi-{inventory}",
                        processor=processor,
                        memory_gb=memory_gb,
                        storage_type=storage_type,
                        storage_size_gb=storage_size_gb,
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
                    self.stdout.write(
                        f"  CREATED: {inventory} ({manufacturer_str} {model_str}) -> {stage_code} | "
                        f"RAM={memory_gb}GB | Storage={storage_type}:{storage_size_gb}GB"
                    )
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
