"""
Cedar certificate ingestion management command.

Two modes:
  ingest_cedar watch     — Run continuously, watching for new files via inotify
  ingest_cedar process   — Scan incoming dirs once, process everything found

Scans /cedar/incoming/ recursively for JSON files of type:
  - erase:   _erasure.json suffix OR Drive Eraser batch export array
  - audit:   _asset_certificate.json suffix OR Cedar Audit batch export
"""
import json
import os
import re
import shutil
import time
from datetime import datetime
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from devices.models import Device, WipeStatus
from wipe.models import DataWipeRecord


INCOMING_BASE = Path("/cedar/incoming")
PROCESSED_BASE = Path("/cedar/processed")
UNMATCHED_BASE = Path("/cedar/unmatched")

# Certificate type is determined by filename suffix:
#   _erasure.json        → erase (wipe certificate)
#   _asset_certificate.json → audit (hardware diagnostic / asset certificate)
FILENAME_PATTERNS = {
    "erase": re.compile(r"_erasure\.json$", re.IGNORECASE),
    "audit": re.compile(r"_asset_certificate\.json$", re.IGNORECASE),
}


def detect_cert_type_from_json(data):
    """Determine certificate type from JSON content."""
    if data.get("erasure_applicable") is not None:
        return "erase"
    if data.get("tests") is not None:
        return "audit"
    if data.get("erasures"):
        return "erase"
    # New Drive Eraser export: has parent_serial_number but no tests
    if data.get("parent_serial_number") and not data.get("tests"):
        return "erase"
    return "audit"


class Command(BaseCommand):
    help = "Ingest Cedar erase and audit certificates"

    def add_arguments(self, parser):
        parser.add_argument(
            "mode",
            nargs="?",
            choices=["watch", "process"],
            default="process",
            help="Run mode: watch (inotify daemon) or process (one-shot scan)",
        )

    def handle(self, *args, **options):
        raise CommandError(
            "ingest_cedar is RETIRED. The Cedar FTP integration has been "
            "replaced by the Cedar API (see integrations/cedar_api.py and "
            "the sync in api/views.py). This command is disabled because its "
            "_extract_result() defaults to PASS when it cannot parse a result, "
            "which can record a wipe as passed with no evidence. "
            "Do not re-enable without fixing that default and confirming the "
            "FTP route is in use. See CHANGELOG-erasure-spec.md."
        )
        mode = options["mode"]
        self.stdout.write(f"Cedar ingestion — mode: {mode}")

        if mode == "process":
            self.process_all()
        elif mode == "watch":
            self.watch_loop()

    # ── Processing Logic ──────────────────────────────────────────

    def process_all(self):
        """Scan all incoming directories and process every JSON file found."""
        for json_path in sorted(INCOMING_BASE.rglob("*.json")):
            if json_path.name.startswith("."):
                continue
            if json_path.name == "manifest.json":
                continue
            self.process_file(json_path)

    def process_file(self, json_path):
        """Process a single JSON file and its matching PDF."""
        self.stdout.write(f"  Processing: {json_path.name}")

        # 1. Parse JSON
        try:
            with open(json_path) as f:
                data = json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            self.stdout.write(self.style.ERROR(f"    Failed to parse JSON: {e}"))
            self._move_to_unmatched(json_path, None)
            return

        # 1a. Handle array format (new batch export from Drive Eraser / Cedar Audit)
        if isinstance(data, list):
            self.stdout.write(f"    Batch export with {len(data)} entries")
            for item in data:
                self._process_single_cert(item, json_path.name, json_path.parent)
            # Archive the batch JSON — all entries processed
            self._archive_batch_json(json_path)
            return

        pdf_path = json_path.with_suffix(".pdf")

        # 2. Determine certificate type
        cert_type = self._detect_cert_type(json_path.name, data)
        self.stdout.write(f"    Type: {cert_type}")

        # 3. Extract serial from JSON
        serial = self._extract_serial(data, json_path.name)
        if not serial:
            self.stdout.write(self.style.WARNING(f"    Could not extract serial"))
            self._move_to_unmatched(json_path, pdf_path)
            return

        # 4. Find device
        try:
            device = Device.objects.get(serial_number__iexact=serial)
        except Device.DoesNotExist:
            self.stdout.write(self.style.WARNING(f"    Device not found for serial: {serial}"))
            self._move_to_unmatched(json_path, pdf_path)
            return

        # 5. Determine result
        result = self._extract_result(data, json_path.name)
        wiped_at = self._extract_timestamp(data)

        # 6. Create DataWipeRecord and update device
        with transaction.atomic():
            # Check for duplicate — same device + cert_type + timestamp
            if wiped_at:
                existing = DataWipeRecord.objects.filter(
                    device=device,
                    certificate_type=cert_type.upper(),
                    wiped_at=wiped_at,
                ).exists()
                if existing:
                    self.stdout.write(self.style.WARNING(
                        f"    Duplicate — already ingested for {device.serial_number} at {wiped_at}"
                    ))
                    self._archive_processed(json_path, pdf_path, device, cert_type)
                    return

            record = DataWipeRecord.objects.create(
                device=device,
                certificate_type=cert_type.upper(),
                result=result,
                json_data=data,
                certificate_file=self._store_certificate(pdf_path, device, cert_type),
                wiped_at=wiped_at,
            )

            if cert_type == "erase":
                device.wipe_status = WipeStatus.PASS if result == "PASS" else WipeStatus.FAIL
                device.save(update_fields=["wipe_status"])
            elif cert_type == "audit":
                new_status = "PASS" if result == "PASS" else "FAIL"
                if device.initial_audit_status in ("PASS", "FAIL"):
                    # Initial audit already done — this is a final audit
                    device.final_audit_status = new_status
                    device.save(update_fields=["final_audit_status"])
                else:
                    device.initial_audit_status = new_status
                    device.save(update_fields=["initial_audit_status"])

        self.stdout.write(self.style.SUCCESS(
            f"    ✅ {device.inventory_number} — {cert_type} = {result}"
        ))

        # 7. Archive
        self._archive_processed(json_path, pdf_path, device, cert_type)

    def _process_single_cert(self, data, batch_filename, directory):
        """Process a single certificate entry from a batch export array."""
        # Determine certificate type from content
        cert_type = detect_cert_type_from_json(data)
        self.stdout.write(f"    Entry type: {cert_type}")

        # Extract serial — parent_serial_number first (new erase format),
        # then system.serial_number (audit format)
        serial = data.get("parent_serial_number")
        if not serial:
            serial = self._extract_serial(data, batch_filename)
        if not serial:
            self.stdout.write(self.style.WARNING(f"    Could not extract serial for entry"))
            return

        self.stdout.write(f"    Serial: {serial}")

        # Find device
        try:
            device = Device.objects.get(serial_number__iexact=serial)
        except Device.DoesNotExist:
            self.stdout.write(self.style.WARNING(f"    Device not found for serial: {serial}"))
            return

        # Find matching PDF in same directory
        # Try drive serial match first, then asset number, then first PDF
        drive_serial = data.get("serial_number", "")
        asset_number = data.get("asset_number") or data.get("company", {}).get("asset_number", "")
        pdf_path = None
        for f in directory.glob("*.pdf"):
            if drive_serial and drive_serial in f.name:
                pdf_path = f
                break
            if asset_number and asset_number in f.name:
                pdf_path = f
                break
        # Fallback: first PDF in dir (single-device batch)
        if not pdf_path:
            pdfs = sorted(directory.glob("*.pdf"))
            if pdfs:
                pdf_path = pdfs[0]

        # Determine result
        result = self._extract_result(data, batch_filename)
        wiped_at = self._extract_timestamp(data)

        # Create record
        with transaction.atomic():
            if wiped_at:
                existing = DataWipeRecord.objects.filter(
                    device=device,
                    certificate_type=cert_type.upper(),
                    wiped_at=wiped_at,
                ).exists()
                if existing:
                    self.stdout.write(self.style.WARNING(
                        f"    Duplicate — already ingested for {device.serial_number} at {wiped_at}"
                    ))
                    if pdf_path and pdf_path.exists():
                        self._archive_processed(None, pdf_path, device, cert_type)
                    return

            record = DataWipeRecord.objects.create(
                device=device,
                certificate_type=cert_type.upper(),
                result=result,
                json_data=data,
                certificate_file=self._store_certificate(pdf_path, device, cert_type),
                wiped_at=wiped_at,
            )

            if cert_type == "erase":
                if device.wipe_status != "PASS":
                    device.wipe_status = WipeStatus.PASS if result == "PASS" else WipeStatus.FAIL
                    device.save(update_fields=["wipe_status"])
            elif cert_type == "audit":
                new_status = "PASS" if result == "PASS" else "FAIL"
                if device.initial_audit_status in ("PASS", "FAIL"):
                    device.final_audit_status = new_status
                    device.save(update_fields=["final_audit_status"])
                else:
                    device.initial_audit_status = new_status
                    device.save(update_fields=["initial_audit_status"])

        self.stdout.write(self.style.SUCCESS(
            f"    ✅ {device.inventory_number} — {cert_type} = {result}"
        ))

        # Archive PDF
        if pdf_path and pdf_path.exists():
            self._archive_processed(None, pdf_path, device, cert_type)

    def _archive_batch_json(self, json_path):
        """Archive batch JSON export after all entries are processed."""
        archive_dir = PROCESSED_BASE / "batch"
        archive_dir.mkdir(parents=True, exist_ok=True)
        shutil.move(str(json_path), str(archive_dir / json_path.name))
        self.stdout.write(f"    Archived batch JSON to: {archive_dir}")

    def _detect_cert_type(self, filename, data):
        """Determine certificate type from filename suffix or JSON content."""
        for cert_type, pattern in FILENAME_PATTERNS.items():
            if pattern.search(filename):
                return cert_type
        return detect_cert_type_from_json(data)

    def _extract_serial(self, data, filename):
        """Extract device serial number from JSON body.

        Checks system.serial_number (audit/old erase) first,
        then parent_serial_number (new Drive Eraser export).
        """
        # Audit / old erase format: system.serial_number
        system = data.get("system", {})
        if isinstance(system, dict):
            serial = system.get("serial_number")
            if serial and serial.strip() and serial.strip().lower() != "none":
                return serial.strip()

        # New Drive Eraser export: parent_serial_number
        parent_serial = data.get("parent_serial_number")
        if parent_serial and parent_serial.strip() and parent_serial.strip().lower() != "none":
            return parent_serial.strip()

        # Fallback: top-level serial_number
        serial = data.get("serial_number")
        if serial and serial.strip() and serial.strip().lower() != "none":
            return serial.strip()

        self.stdout.write(self.style.WARNING(
            f"    No serial found in JSON body for {filename}"
        ))
        return None

    def _extract_result(self, data, filename):
        """Extract PASS/FAIL from JSON data or filename fallback."""
        # Try JSON status.result first (audit cert format)
        status = data.get("status", {})
        if isinstance(status, dict):
            result = status.get("result")
            if result and result.upper() in ("PASS", "FAIL"):
                return result.upper()

        # Try top-level result (new Drive Eraser format)
        result = data.get("result")
        if result and result.upper() in ("PASS", "FAIL"):
            return result.upper()

        # Fallback: filename suffix
        name = filename.rsplit(".", 1)[0].lower()
        if name.endswith("_pass"):
            return "PASS"
        if name.endswith("_fail"):
            return "FAIL"

        return "PASS"

    def _extract_timestamp(self, data):
        """Extract wipe timestamp from JSON."""
        timestamps = data.get("timestamps", {})
        if isinstance(timestamps, dict):
            ended = timestamps.get("ended")
            if ended:
                try:
                    return datetime.fromisoformat(ended)
                except (ValueError, TypeError):
                    pass
            started = timestamps.get("started")
            if started:
                try:
                    return datetime.fromisoformat(started)
                except (ValueError, TypeError):
                    pass

        created_at = data.get("created_at")
        if created_at:
            try:
                return datetime.fromisoformat(created_at)
            except (ValueError, TypeError):
                pass
        return None

    def _store_certificate(self, pdf_path, device, cert_type):
        """Copy PDF to Django's media storage and return the path."""
        if not pdf_path or not pdf_path.exists():
            return None

        dest_dir = Path("wipe_certificates") / cert_type
        dest = dest_dir / f"{device.inventory_number}_{cert_type}.pdf"
        full_dest = Path("/app/media") / dest

        full_dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(pdf_path, full_dest)

        return str(dest)

    def _archive_processed(self, json_path, pdf_path, device, cert_type):
        """Move processed files to archive directory."""
        if cert_type == "erase":
            # Group by donation pledge reference + donor name
            pledge = getattr(device, 'donation_pledge', None)
            if pledge:
                ref = getattr(pledge, 'reference_number', None) or str(pledge.id)
                donor_name = getattr(pledge, 'donor_name', '') or ''
                donor_slug = re.sub(r'[^a-zA-Z0-9_-]', '', donor_name.replace(' ', '_')).upper()
                dir_name = f"{ref}_{donor_slug}" if donor_slug else str(ref)
            else:
                dir_name = device.serial_number
            archive_dir = PROCESSED_BASE / "wipe" / dir_name
        else:
            # Group by fulfilment request + recipient name
            from devices.models import Allocation
            alloc = Allocation.objects.filter(device=device).first()
            if alloc and alloc.fulfilment_request:
                fr = alloc.fulfilment_request
                fr_ref = fr.erpnext_order_id or str(fr.id)
                recipient_name = str(getattr(fr, 'recipient', '') or '')
                recipient_slug = re.sub(r'[^a-zA-Z0-9_-]', '', recipient_name.replace(' ', '_')).upper()
                dir_name = f"{fr_ref}_{recipient_slug}" if recipient_slug else str(fr_ref)
            else:
                dir_name = device.serial_number
            archive_dir = PROCESSED_BASE / "audit" / dir_name

        archive_dir.mkdir(parents=True, exist_ok=True)

        if json_path and json_path.exists():
            shutil.move(str(json_path), str(archive_dir / json_path.name))
        if pdf_path and pdf_path.exists():
            shutil.move(str(pdf_path), str(archive_dir / pdf_path.name))

        self.stdout.write(f"    Archived to: {archive_dir}")

    def _move_to_unmatched(self, json_path, pdf_path):
        """Move unmatched files for manual review."""
        UNMATCHED_BASE.mkdir(parents=True, exist_ok=True)
        if json_path and json_path.exists():
            shutil.move(str(json_path), str(UNMATCHED_BASE / json_path.name))
        if pdf_path and pdf_path.exists():
            shutil.move(str(pdf_path), str(UNMATCHED_BASE / pdf_path.name))
        self.stdout.write(f"    Moved to unmatched: {UNMATCHED_BASE}")

    # ── Watch Mode ────────────────────────────────────────────────

    def watch_loop(self):
        """Run continuously using watchdog inotify."""
        from watchdog.observers import Observer
        from watchdog.events import FileSystemEventHandler

        class CedarHandler(FileSystemEventHandler):
            def __init__(self, command):
                self.command = command
                self.recent = set()

            def on_created(self, event):
                if event.is_directory:
                    return
                path = Path(event.src_path)
                if path.suffix != ".json":
                    return
                if path.name == "manifest.json":
                    return

                if path.name in self.recent:
                    return
                self.recent.add(path.name)

                def _clear():
                    time.sleep(10)
                    self.recent.discard(path.name)

                import threading
                threading.Thread(target=_clear, daemon=True).start()

                self.command.process_file(path)

        event_handler = CedarHandler(self)
        observer = Observer()
        observer.schedule(event_handler, str(INCOMING_BASE), recursive=True)
        self.stdout.write(f"  Watching: {INCOMING_BASE}")

        self.stdout.write(self.style.SUCCESS("Cedar watcher started (Ctrl+C to stop)"))
        observer.start()

        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            observer.stop()
        observer.join()

