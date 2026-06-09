import csv
import sys
from django.core.management.base import BaseCommand, CommandError
from locations.models import Site, Location, LocationPurpose, LocationMaxSize


class Command(BaseCommand):
    help = "Import location records from a CSV file"

    def add_arguments(self, parser):
        parser.add_argument("csv_file", help="Path to the CSV file")
        parser.add_argument(
            "--site-code",
            default="OG8",
            help="Site code to assign (default: OG8)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Validate CSV without importing",
        )

    def handle(self, *args, **options):
        csv_path = options["csv_file"]
        site_code = options["site_code"]
        dry_run = options["dry_run"]

        # Validate CSV columns
        expected_columns = {"code", "purpose", "zone", "max_size", "notes"}

        # Get or create site
        try:
            site = Site.objects.get(code=site_code)
        except Site.DoesNotExist:
            if dry_run:
                self.stdout.write(f"[DRY-RUN] Would create site: {site_code}")
                site = None
            else:
                site = Site.objects.create(
                    code=site_code,
                    name="OG8 Store Room",
                    address="OG8 Store Room (address TBC)",
                )
                self.stdout.write(self.style.SUCCESS(f"Created site: {site_code}"))

        created_count = 0
        updated_count = 0
        error_count = 0

        with open(csv_path, newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)

            # Validate columns
            cols = set(reader.fieldnames or [])
            missing = expected_columns - cols
            if missing:
                raise CommandError(
                    f"CSV missing columns: {', '.join(sorted(missing))}. "
                    f"Found: {', '.join(sorted(cols))}"
                )

            for row_num, row in enumerate(reader, start=2):
                code = row["code"].strip()
                purpose_raw = row["purpose"].strip().upper()
                zone_raw = row["zone"].strip()
                max_size_raw = row["max_size"].strip().upper()
                notes = row.get("notes", "").strip()

                # Validate purpose
                purpose = None
                for choice in LocationPurpose.choices:
                    if choice[0] == purpose_raw:
                        purpose = purpose_raw
                        break
                if purpose is None:
                    self.stderr.write(
                        self.style.ERROR(
                            f"Row {row_num} ({code}): Invalid purpose '{purpose_raw}'. "
                            f"Valid: {', '.join(c[0] for c in LocationPurpose.choices)}"
                        )
                    )
                    error_count += 1
                    continue

                # Validate max_size
                max_size = None
                for choice in LocationMaxSize.choices:
                    if choice[0] == max_size_raw:
                        max_size = max_size_raw
                        break
                if max_size is None:
                    self.stderr.write(
                        self.style.ERROR(
                            f"Row {row_num} ({code}): Invalid max_size '{max_size_raw}'. "
                            f"Valid: {', '.join(c[0] for c in LocationMaxSize.choices)}"
                        )
                    )
                    error_count += 1
                    continue

                if not zone_raw:
                    self.stderr.write(
                        self.style.ERROR(
                            f"Row {row_num} ({code}): Zone cannot be blank"
                        )
                    )
                    error_count += 1
                    continue

                if dry_run:
                    self.stdout.write(
                        f"[DRY-RUN] Would create/update: "
                        f"code={code}, site={site_code}, zone={zone_raw}, "
                        f"purpose={purpose}, max_size={max_size}, notes={notes}"
                    )
                    continue

                # Create or update location
                try:
                    location, created = Location.objects.update_or_create(
                        code=code,
                        defaults={
                            "site": site,
                            "zone": zone_raw,
                            "purpose": purpose,
                            "max_size": max_size,
                            "notes": notes,
                            "is_active": True,
                        },
                    )
                    if created:
                        created_count += 1
                    else:
                        updated_count += 1
                except Exception as e:
                    self.stderr.write(
                        self.style.ERROR(f"Row {row_num} ({code}): {e}")
                    )
                    error_count += 1

        # Summary
        self.stdout.write("\n--- Import Summary ---")
        if dry_run:
            self.stdout.write(f"Dry run: {error_count} errors")
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Created: {created_count}, "
                    f"Updated: {updated_count}, "
                    f"Errors: {error_count}"
                )
            )

        if error_count:
            raise CommandError(f"{error_count} error(s) occurred during import")

