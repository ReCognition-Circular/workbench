"""Seed one deliberate FAIL device for exercising the erasure obligation flow.

This is TEST TOOLING. It exists so the QA gate (Phase 3b) and the device-detail
erasure panel (Phase 3a) can be exercised against real data, because genuine
Cedar erasure failures are rare.

It writes only through the model layer. It creates at most one device, and it
is fully reversible with --delete.

    python manage.py seed_erasure_test          # create / re-assert
    python manage.py seed_erasure_test --delete # remove

Delete this file (and the device it creates) before go-live.
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from devices.models import (
    Device,
    DeviceSpecification,
    DeviceType,
    OwnershipType,
    WipeStatus,
)
from workflow.models import Stage

TEST_INVENTORY = "TEST-ERASURE-001"
TEST_SERIAL = "TEST-ERASURE-SN-001"
TEST_DRIVE_SERIAL = "TEST-ERASURE-DRIVE-001"


class Command(BaseCommand):
    help = "Create (or delete) a single FAIL device for erasure-flow testing."

    def add_arguments(self, parser):
        parser.add_argument(
            "--delete",
            action="store_true",
            help="Remove the test device and its specification instead of creating them.",
        )

    def handle(self, *args, **options):
        if options["delete"]:
            return self._delete()

        return self._create()

    # ── create ───────────────────────────────────────────────────────────

    @transaction.atomic
    def _create(self):
        spec, spec_created = DeviceSpecification.objects.update_or_create(
            serial_number=TEST_SERIAL,
            defaults={
                "manufacturer": "TEST",
                "model_name": "Erasure Obligation Fixture",
                "model_number": "TEST-EO-001",
                "processor": "Test Processor",
                "memory_gb": 8,
                "storage_size_gb": 256,
                "drive_serial": TEST_DRIVE_SERIAL,
            },
        )

        qa_stage = Stage.objects.filter(code="QA").first()

        device, device_created = Device.objects.update_or_create(
            inventory_number=TEST_INVENTORY,
            defaults={
                "serial_number": TEST_SERIAL,
                "device_type": DeviceType.LAPTOP,
                "ownership_type": OwnershipType.DONATION,
                "device_specification": spec,
                "stage": qa_stage,
                # ── the obligation ──
                "wipe_status": WipeStatus.FAIL,
                "drive_removed": False,
                "wipe_notes": (
                    "TEST FIXTURE — deliberate Cedar erasure failure. "
                    "Drive is present and no evidence has been supplied, so the "
                    "QA gate should block. Use --delete to remove."
                ),
            },
        )

        action = "Created" if device_created else "Re-asserted"
        self.stdout.write(self.style.SUCCESS(
            f"{action} test device pk={device.id} "
            f"inventory={device.inventory_number} "
            f"wipe_status={device.wipe_status} "
            f"drive_removed={device.drive_removed}"
        ))
        self.stdout.write(
            "  Detail page: /devices/%d/" % device.id
        )
        self.stdout.write(
            "  Spec: %s (%s)"
            % (spec.serial_number, "created" if spec_created else "reused")
        )
        self.stdout.write(self.style.WARNING(
            "  REMINDER: this is test data. Remove it before go-live."
        ))

    # ── delete ───────────────────────────────────────────────────────────

    @transaction.atomic
    def _delete(self):
        devices = Device.objects.filter(inventory_number=TEST_INVENTORY)
        specs = DeviceSpecification.objects.filter(serial_number=TEST_SERIAL)

        device_count = devices.count()
        spec_count = specs.count()

        if not device_count and not spec_count:
            self.stdout.write(self.style.WARNING(
                "Nothing to delete — no test device/spec found."
            ))
            return

        devices.delete()
        specs.delete()

        self.stdout.write(self.style.SUCCESS(
            f"Deleted {device_count} test device(s) and {spec_count} spec(s)."
        ))
