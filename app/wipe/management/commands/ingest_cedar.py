"""
Cedar certificate ingestion management command.

Two modes:
  ingest_cedar watch     — Run continuously, watching for new files via inotify
  ingest_cedar process   — Scan incoming dirs once, process everything found

Watches /cedar/incoming/erase/ and /cedar/incoming/audit/ recursively.
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

CERT_DIRS = {
    "erase": INCOMING_BASE / "erase",
    "audit": INCOMING_BASE / "audit",
}


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
        """Scan all incoming directories and process every file found."""
        for cert_type, dirpath in CERT_DIRS.items():
            if not dirpath.exists():
                self.stdout.write(f"  Directory not found: {dirpath}")
                continue
            for json_path in sorted(dirpath.rglob("*.json")):
                self.process_file(json_path, cert_type)
            for pdf_path in sorted(dirpath.rglob("*.pdf")):
                if not pdf_path.with_suffix(".json").exists():
                    self.stdout.write(f"  No matching JSON for {pdf_path.name}, skipping")

    def process_file(self, json_path, cert_type):
        """Process a single JSON file and its matching PDF."""
        self.stdout.write(f"  Processing: {json_path.name} ({cert_type})")

        pdf_path = json_path.with_suffix(".pdf")

        # 1. Extract serial from filename
        serial = self._extract_serial(json_path.name)
        if not serial:
            self.stdout.write(self.style.WARNING(f"    Could not extract serial from {json_path.name}"))
            self._move_to_unmatched(json_path, pdf_path)
            return

        # 2. Find device
        try:
            device = Device.objects.get(serial_number__iexact=serial)
        except Device.DoesNotExist:
            self.stdout.write(self.style.WARNING(f"    Device not found for serial: {serial}"))
            self._move_to_unmatched(json_path, pdf_path)
            return

        # 3. Parse JSON
        try:
            with open(json_path) as f:
                data = json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            self.stdout.write(self.style.ERROR(f"    Failed to parse JSON: {e}"))
            self._move_to_unmatched(json_path, pdf_path)
            return

        # 4. Determine result
        result = self._extract_result(data, json_path.name)
        wiped_at = self._extract_timestamp(data)

        # 5. Create DataWipeRecord and update device
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
            elif cert_type == "audit":
                device.audit_status = "PASS" if result == "PASS" else "FAIL"
            device.save(update_fields=["wipe_status", "audit_status"])

        self.stdout.write(self.style.SUCCESS(
            f"    ✅ {device.inventory_number} — {cert_type} = {result}"
        ))

        # 6. Archive
        self._archive_processed(json_path, pdf_path, device, cert_type)

    def _extract_serial(self, filename):
        """Extract serial number from filename.
        
        Expected format: {SERIAL}_{UUID}_Pass.pdf or {SERIAL}_{UUID}_Fail.json
        The serial is the part before the first underscore.
        """
        name = filename.rsplit(".", 1)[0]  # remove extension
        parts = name.split("_")
        if len(parts) >= 2:
            return parts[0]
        return None

    def _extract_result(self, data, filename):
        """Extract PASS/FAIL from JSON data or filename fallback."""
        # Try JSON status.result first
        status = data.get("status", {})
        result = status.get("result")
        if result and result.upper() in ("PASS", "FAIL"):
            return result.upper()

        # Fallback: filename suffix
        name = filename.rsplit(".", 1)[0]
        if name.endswith("_Pass"):
            return "PASS"
        if name.endswith("_Fail"):
            return "FAIL"

        return "PASS"  # default

    def _extract_timestamp(self, data):
        """Extract wipe timestamp from JSON."""
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
            # Archive by donor pledge ID (or serial as fallback)
            pledge_id = device.donation_pledge_id or device.serial_number
            archive_dir = PROCESSED_BASE / "wipe" / str(pledge_id)
        else:
            # Archive by fulfilment request ID (or serial as fallback)
            fr_id = device.fulfilment_request_id or device.serial_number
            archive_dir = PROCESSED_BASE / "audit" / str(fr_id)

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
                # Debounce: track recently processed files
                self.recent = set()

            def on_created(self, event):
                if event.is_directory:
                    return
                path = Path(event.src_path)
                if path.suffix != ".json":
                    return

                # Debounce — skip if processed in last 5 seconds
                if path.name in self.recent:
                    return
                self.recent.add(path.name)
                # Clear after 10 seconds
                def _clear():
                    time.sleep(10)
                    self.recent.discard(path.name)

                import threading
                threading.Thread(target=_clear, daemon=True).start()

                # Determine cert type from directory
                cert_type = None
                for ct, base in CERT_DIRS.items():
                    if str(path).startswith(str(base)):
                        cert_type = ct
                        break

                if cert_type:
                    self.command.process_file(path, cert_type)

        event_handler = CedarHandler(self)
        observer = Observer()

        for cert_type, dirpath in CERT_DIRS.items():
            if dirpath.exists():
                observer.schedule(event_handler, str(dirpath), recursive=True)
                self.stdout.write(f"  Watching: {dirpath}")

        self.stdout.write(self.style.SUCCESS("Cedar watcher started (Ctrl+C to stop)"))
        observer.start()

        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            observer.stop()
        observer.join()
