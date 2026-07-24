"""
Cedar certificate ingestion management command.

Two modes:
  ingest_cedar watch     — Run continuously, watching for new files via inotify
  ingest_cedar process   — Scan incoming dirs once, process everything found

Scans /cedar/incoming/ recursively for JSON files of type:
  - erase:   filenames ending with _erasure.json (Cedar Drive Eraser)
  - audit:   filenames ending with _asset_certificate.json (Cedar Audit)
"""
import json
import os
import re
import shutil
import time
from datetime import datetime
from pathlib import Path

from django.core.management.base import BaseCommand
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
            self.process_file(json_path)

    def process_file(self, json_path):
        """Process a single JSON file and its matching PDF."""
        self.stdout.write(f"  Processing: {json_path.name}")

        pdf_path = json_path.with_suffix(".pdf")

        # 1. Parse JSON
        try:
            with open(json_path) as f:
                data = json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            self.stdout.write(self.style.ERROR(f"    Failed to parse JSON: {e}"))
            self._move_to_unmatched(json_path, pdf_path)
            return

        # 2. Determine certificate type
        cert_type = self._detect_cert_type(json_path.name, data)
        self.stdout.write(f"    Type: {cert_type}")

        # 3. Extract serial from JSON system.serial_number
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
                device.initial_audit_status = "PASS" if result == "PASS" else "FAIL"
                device.save(update_fields=["initial_audit_status"])

        self.stdout.write(self.style.SUCCESS(
            f"    ✅ {device.inventory_number} — {cert_type} = {result}"
        ))

        # 7. Archive
        self._archive_processed(json_path, pdf_path, device, cert_type)

    def _detect_cert_type(self, filename, data):
        """Determine certificate type from filename suffix or JSON content."""
        for cert_type, pattern in FILENAME_PATTERNS.items():
            if pattern.search(filename):
                return cert_type
        return detect_cert_type_from_json(data)

    def _extract_serial(self, data, filename):
        """Extract device serial number from JSON body.

        The serial is at data['system']['serial_number'] in all Cedar JSON formats.
        Filename-based extraction is NOT reliable.
        """
        system = data.get("system", {})
        if isinstance(system, dict):
            serial = system.get("serial_number")
            if serial and serial.strip() and serial.strip().lower() != "none":
                return serial.strip()

        # Fallback: try top-level serial_number
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

        # Try top-level result (asset/erase cert format)
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
        if not pdf_path.exists():
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
                # Sanitize donor name for directory use
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

        if json_path.exists():
            shutil.move(str(json_path), str(archive_dir / json_path.name))
        if pdf_path.exists():
            shutil.move(str(pdf_path), str(archive_dir / pdf_path.name))

        self.stdout.write(f"    Archived to: {archive_dir}")

    def _move_to_unmatched(self, json_path, pdf_path):
        """Move unmatched files for manual review."""
        UNMATCHED_BASE.mkdir(parents=True, exist_ok=True)
        if json_path.exists():
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
