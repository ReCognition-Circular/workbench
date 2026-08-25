"""Backfill AuditRecord from legacy DataWipeRecord(certificate_type=AUDIT).

Devices audited under the old Cedar integration stored audit certificates
in DataWipeRecord (certificate_type="AUDIT"). The new integration stores
them in AuditRecord and points Device.latest_audit / initial_audit at them.

This command re-syncs those devices' asset certificates via the new Cedar
API, populates AuditRecord + the FK pointers, so the QA "Cedar audit
certificate on file" item resolves correctly.

Usage:
    python manage.py backfill_audit_records --dry-run
    python manage.py backfill_audit_records
    python manage.py backfill_audit_records --device-ids 12 30 166
"""

from django.core.management.base import BaseCommand

from devices.models import Device
from wipe.models import AuditRecord, DataWipeRecord

from api.views import _serial_variants, _tests_have_fail
from integrations.cedar_api import CedarAPIError, search_asset_certificates_by_serials


class Command(BaseCommand):
    help = "Migrate legacy DataWipeRecord(AUDIT) into AuditRecord via the new Cedar API."

    def add_arguments(self, parser):
        parser.add_argument(
            "--device-ids",
            nargs="*",
            type=int,
            help="Optional list of device IDs to process (default: all affected).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report what would be created without writing to the DB.",
        )

    def handle(self, *args, **options):
        device_ids = options["device_ids"]
        dry_run = options["dry_run"]

        legacy_device_ids = (
            DataWipeRecord.objects.filter(certificate_type="AUDIT")
            .values_list("device_id", flat=True)
            .distinct()
        )
        qs = Device.objects.filter(
            id__in=legacy_device_ids,
            latest_audit__isnull=True,
        )
        if device_ids:
            qs = qs.filter(id__in=device_ids)

        created = 0
        updated = 0
        skipped_api = 0
        skipped_empty = 0

        for device in qs.order_by("id"):
            self.stdout.write(f"Device {device.id} (serial {device.serial_number})…")
            try:
                resp = search_asset_certificates_by_serials(
                    _serial_variants(device.serial_number)
                )
                certs = (
                    resp.get("certificates", {}).get("data", [])
                    if isinstance(resp, dict)
                    else []
                )
            except CedarAPIError as e:
                self.stderr.write(f"  ! Cedar API error: {e}")
                skipped_api += 1
                continue

            if not certs:
                self.stdout.write("  - no asset certs found in Cedar")
                skipped_empty += 1
                continue

            certs.sort(
                key=lambda c: (
                    c.get("created_at") or c.get("id") or c.get("uuid") or ""
                )
            )

            initial = None
            latest = None
            for cert in certs:
                cert_id = cert.get("id") or cert.get("uuid")
                result = "FAIL" if _tests_have_fail(cert.get("tests")) else "PASS"

                if dry_run:
                    self.stdout.write(
                        f"  [dry-run] upsert AuditRecord cert_id={cert_id} result={result}"
                    )
                    continue

                rec, was_created = AuditRecord.objects.update_or_create(
                    device=device,
                    cedar_certificate_id=cert_id,
                    defaults={
                        "result": result,
                        "test_results": cert,
                        "auditor": "Cedar Enterprise",
                        "notes": (
                            f"Migrated from legacy DataWipeRecord "
                            f"(device {device.serial_number})"
                        ),
                    },
                )
                created += 1 if was_created else 0
                updated += 0 if was_created else 1
                if initial is None:
                    initial = rec
                latest = rec

            if dry_run:
                self.stdout.write(
                    f"  [dry-run] would set initial_audit/latest_audit "
                    f"to last of {len(certs)} cert(s)"
                )
                continue

            if initial:
                device.initial_audit = initial
                device.latest_audit = latest
                device.save(update_fields=["initial_audit", "latest_audit"])
                self.stdout.write(
                    f"  ✓ {len(certs)} cert(s); initial_audit={initial.id}, "
                    f"latest_audit={latest.id}"
                )

        self.stdout.write(
            self.style.SUCCESS(
                f"Done. created={created} updated={updated} "
                f"api_errors={skipped_api} no_certs={skipped_empty}"
            )
        )
