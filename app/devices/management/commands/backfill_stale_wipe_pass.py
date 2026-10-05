from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Count

from devices.models import Device

# --- Devices deliberately excluded from this backfill ---
#
# These three carry wipe_status='PASS' with no supporting evidence, but are NOT
# cleaned by this command. They are listed here (rather than silently filtered)
# so the residue stays visible and is not forgotten.
#
#   09250009    Test/boundary data ('boundary-test' in notes). Not production
#               stock - should be removed by a fixture reset, not a status flip.
#
#   707090001   Notes read 'tested pass, not through Cedar'. The device appears
#               to have been wiped by a method other than Cedar, but no
#               certificate was captured and no DataWipeRecord exists. The
#               evidence is gone; reclassifying it now would be inventing a
#               category after the fact. Left as-is.
#
#   707090002   As above ('tested pass, not through Cedar, thought').
#
EXCLUDED_INVENTORY_NUMBERS = [
    "09250009",
    "707090001",
    "707090002",
]

class Command(BaseCommand):
    help = (
        "Demote stale wipe_status='PASS' to PENDING where no evidence exists "
        "(no drive serial queried, no DataWipeRecord). Dry run by default."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Write changes. Default is a dry run (no writes).",
        )

    def handle(self, *args, **options):
        apply_changes = options["apply"]

        candidates = (
            Device.objects
            .filter(
                wipe_status="PASS",
                device_specification__drive_serial="",
                erasure_required=True,
            )
            .annotate(n_wipe=Count("wipe_records"))
            .filter(n_wipe=0)
            .exclude(inventory_number__in=EXCLUDED_INVENTORY_NUMBERS)
            .select_related("stage", "device_specification")
            .order_by("inventory_number")
        )

        rows = list(candidates)

        self.stdout.write("")
        self.stdout.write(
            f"Stale wipe_status=PASS backfill - "
            f"{'APPLIED' if apply_changes else 'DRY RUN'}"
        )
        self.stdout.write("-" * 70)

        for device in rows:
            stage_code = device.stage.code if device.stage else "NONE"
            spec = device.device_specification
            source = spec.source if spec else "NOSPEC"
            self.stdout.write(
                f"  {device.inventory_number}: PASS -> PENDING  "
                f"[stage={stage_code}, spec_source={source}]"
            )

        self.stdout.write("-" * 70)
        self.stdout.write(f"Total devices to change: {len(rows)}")

        if apply_changes:
            with transaction.atomic():
                changed = (
                    Device.objects
                    .filter(id__in=[d.id for d in rows])
                    .update(wipe_status="PENDING")
                )
            self.stdout.write(f"Applied: {changed} device(s) set to PENDING.")
        else:
            self.stdout.write(
                "\nThis was a DRY RUN. Run with --apply to write the changes."
            )
