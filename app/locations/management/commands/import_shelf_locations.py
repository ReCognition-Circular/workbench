import csv
from django.core.management.base import BaseCommand
from locations.models import Location, Site


class Command(BaseCommand):
    help = "Import shelf locations from a CSV file"

    def add_arguments(self, parser):
        parser.add_argument("csv_file", type=str, help="Path to CSV file")

    def handle(self, *args, **options):
        path = options["csv_file"]

        site, _ = Site.objects.get_or_create(
            code="RECOG",
            defaults={"name": "ReCognition Birmingham"},
        )

        with open(path) as f:
            reader = csv.DictReader(f)
            created = 0
            skipped = 0

            for row in reader:
                code = row.get("code", "").strip()
                zone = row.get("zone", "").strip()
                purpose = row.get("purpose", "").strip()
                max_size = row.get("max_size", "").strip()
                notes = row.get("notes", "").strip()

                if not code:
                    skipped += 1
                    continue

                _, was_created = Location.objects.get_or_create(
                    code=code,
                    defaults={
                        "site": site,
                        "zone": zone,
                        "purpose": purpose,
                        "max_size": max_size,
                        "notes": notes,
                        "description": code,
                        "barcode": code,
                    },
                )
                if was_created:
                    created += 1
                else:
                    skipped += 1

            self.stdout.write(
                self.style.SUCCESS(
                    f"Done. Created: {created}, Skipped (existing/missing code): {skipped}"
                )
            )
