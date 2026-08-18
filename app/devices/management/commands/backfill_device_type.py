import re

from django.core.management.base import BaseCommand

from devices.models import Device, DeviceType


# --- Classifier (device-type-bug.md §D) ---

TABLET_KEYWORDS = ["ipad", "tablet"]
DESKTOP_KEYWORDS = ["optiplex", "thinkcentre", "prodesk", "elitedesk", "precision"]
ALL_IN_ONE_KEYWORDS = ["all-in-one", "all in one", "imac", "23-p"]
MONITOR_KEYWORDS = ["x2301", "monitor", "display"]
LAPTOP_KEYWORDS = [
    "thinkpad", "latitude", "probook", "elitebook", "vivobook", "aspire",
    "lifebook", "vostro", "pavilion", "envy", "inspiron", "travelmate",
    "ideapad", "surface laptop", "chromebook", "geoflex", "notebook", "macbook",
]

# Mobile CPU markers: Intel N-series (N4000/N4100/...), and U/Y/H/HQ/HK/P/M/QM suffixes
MOBILE_CPU_PATTERN = re.compile(r"\bn[4-6]\d{3}\b|\d(hq|hk|qm|u|y|h|p|m)\b", re.IGNORECASE)
CPU_BRAND_PATTERN = re.compile(r"\b(intel|amd)\b", re.IGNORECASE)


def _has(text, keywords):
    return any(k in (text or "").lower() for k in keywords)


def classify_device_type(model_name, processor):
    model = (model_name or "").strip().lower()
    proc = (processor or "").strip()

    # Completely blank record: leave for manual review
    if not model and not proc:
        return DeviceType.OTHER

    # 1) Model-name keywords (strongest signal — check ALL types first)
    if _has(model, TABLET_KEYWORDS):
        return DeviceType.TABLET
    if _has(model, DESKTOP_KEYWORDS):
        return DeviceType.DESKTOP
    if _has(model, ALL_IN_ONE_KEYWORDS):
        return DeviceType.ALL_IN_ONE
    if _has(model, MONITOR_KEYWORDS):
        return DeviceType.MONITOR
    if _has(model, LAPTOP_KEYWORDS):
        return DeviceType.LAPTOP

    # 2) Fallbacks when model name gives no signal
    if not proc:
        return DeviceType.MONITOR  # no CPU at all → display/monitor

    if MOBILE_CPU_PATTERN.search(proc):
        return DeviceType.LAPTOP
    if CPU_BRAND_PATTERN.search(proc):
        return DeviceType.DESKTOP

    return DeviceType.OTHER


class Command(BaseCommand):
    help = "Backfill Device.device_type using the §D classifier (model_name + processor)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Write changes. Default is a dry run (no writes).",
        )

    def handle(self, *args, **options):
        apply_changes = options["apply"]
        devices = Device.objects.select_related("device_specification").all()

        changes = []
        skipped = []

        for device in devices:
            spec = device.device_specification
            if spec is None:
                skipped.append((device.inventory_number, "no specification"))
                continue

            new_type = classify_device_type(spec.model_name, spec.processor)
            if new_type != device.device_type:
                changes.append((device, device.device_type, new_type))
                if apply_changes:
                    device.device_type = new_type
                    device.save(update_fields=["device_type"])

        self.stdout.write("")
        self.stdout.write(f"Device type backfill — {'APPLIED' if apply_changes else 'DRY RUN'}")
        self.stdout.write("-" * 70)

        summary = {}
        for device, old, new in changes:
            key = f"{old} -> {new}"
            summary[key] = summary.get(key, 0) + 1
            model = device.device_specification.model_name or "(blank)"
            self.stdout.write(f"  {device.inventory_number}: {old} -> {new}  [{model}]")

        self.stdout.write("-" * 70)
        self.stdout.write("Summary of changes:")
        for key in sorted(summary):
            self.stdout.write(f"  {key}: {summary[key]}")
        self.stdout.write(f"Total changes: {len(changes)}")
        self.stdout.write(f"Skipped (no specification): {len(skipped)}")

        if not apply_changes:
            self.stdout.write("\nThis was a DRY RUN. Run with --apply to write the changes.")
