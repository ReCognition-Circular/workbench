import logging
from itertools import product

from django.core.management.base import BaseCommand
from django.utils import timezone
from integrations.erpnext_client import ERPNextClient, ERPNextClientError
from integrations.models import IntegrationLog

logger = logging.getLogger(__name__)

COMMON_VARIANTS = [
    # Modern premium (Grade A/B, 16GB, 256-512GB)
    {"Model": m, "Grade": g, "Storage": s, "Memory": "16GB",
     "Processor": "Core i5", "Processor Gen": "12th"}
    for m in [
        "Dell Latitude 5000 series", "Dell Latitude 7000 series",
        "HP EliteBook 800 series", "HP EliteBook 600 series",
        "Lenovo ThinkPad T Series", "Lenovo ThinkPad X1 Carbon",
        "Apple MacBook Pro", "Apple MacBook Air",
    ]
    for g in ["A", "B"]
    for s in ["256GB SSD", "500GB SSD"]
] + [
    # Budget / older (Grade B/C, 8GB, 128-256GB)
    {"Model": m, "Grade": g, "Storage": s, "Memory": "8GB",
     "Processor": "Core i5", "Processor Gen": "10th"}
    for m in [
        "Dell Latitude 3000 series", "Dell Latitude 5000 series",
        "HP ProBook 400 Series", "HP EliteBook 800 series",
        "Lenovo ThinkPad L Series", "Lenovo ThinkPad T Series",
    ]
    for g in ["B", "C"]
    for s in ["128GB SSD", "256GB SSD"]
] + [
    # Low-end / bulk (Grade C/D, 4GB, 128GB)
    {"Model": m, "Grade": g, "Storage": "128GB SSD", "Memory": "4GB",
     "Processor": "Core i5", "Processor Gen": "8th"}
    for m in [
        "Dell Latitude 3000 series", "HP ProBook 400 Series", "Lenovo ThinkPad L Series",
    ]
    for g in ["C", "D"]
] + [
    # Unspecified fallback — one per grade/storage/memory combo
    {"Model": "Unspecified", "Grade": g, "Storage": s, "Memory": m,
     "Processor": "Core i5", "Processor Gen": "10th"}
    for g in ["A", "B", "C", "D"]
    for s in ["128GB SSD", "256GB SSD", "500GB SSD"]
    for m in ["4GB", "8GB", "16GB"]
]


class Command(BaseCommand):
    help = "Create sensible Item Variants in ERPNext from the LAPTOP template"

    def handle(self, *args, **options):
        client = ERPNextClient()

        for idx, variant in enumerate(COMMON_VARIANTS, 1):
            model_abbr = self._abbr(variant["Model"])
            grade_abbr = variant["Grade"]
            storage_abbr = self._storage_abbr(variant["Storage"])
            memory_abbr = variant["Memory"].replace("GB", "")

            item_code = (
                f"LAPTOP-{model_abbr}-i5-{variant['Processor Gen']}"
                f"-{grade_abbr}-{storage_abbr}-{memory_abbr}GB"
            )
            item_name = (
                f"Refurb Laptop - {variant['Model']}, "
                f"Grade {variant['Grade']}, "
                f"{variant['Memory']} RAM, {variant['Storage']}"
            )

            payload = {
                "item_code": item_code,
                "item_name": item_name,
                "item_group": "Products",
                "stock_uom": "Nos",
                "variant_of": "LAPTOP",
                "attributes": [
                    {"attribute": "Model", "attribute_value": variant["Model"]},
                    {"attribute": "Processor", "attribute_value": variant["Processor"]},
                    {"attribute": "Processor Gen", "attribute_value": variant["Processor Gen"]},
                    {"attribute": "Grade", "attribute_value": variant["Grade"]},
                    {"attribute": "Storage", "attribute_value": variant["Storage"]},
                    {"attribute": "Memory", "attribute_value": variant["Memory"]},
                ],
            }

            try:
                client.create("Item", payload)
                self.stdout.write(f"  [{idx}/{len(COMMON_VARIANTS)}] Created {item_code}")
                IntegrationLog.objects.create(
                    direction="OUTBOUND",
                    doctype="Item",
                    doc_name=item_code,
                    action="create_variant",
                    status="SUCCESS",
                    completed_at=timezone.now(),
                )
            except ERPNextClientError as e:
                if "already exists" in str(e).lower():
                    self.stdout.write(f"  [{idx}/{len(COMMON_VARIANTS)}] Skipped {item_code} (exists)")
                else:
                    self.stderr.write(f"  [{idx}/{len(COMMON_VARIANTS)}] FAILED {item_code}: {e}")
                    IntegrationLog.objects.create(
                        direction="OUTBOUND",
                        doctype="Item",
                        doc_name=item_code,
                        action="create_variant",
                        status="FAILED",
                        error_message=str(e),
                        completed_at=timezone.now(),
                    )

        self.stdout.write(self.style.SUCCESS(f"Done. Attempted {len(COMMON_VARIANTS)} variants."))

    def _abbr(self, name):
        mapping = {
            "Dell Latitude 3000 series": "DL3000",
            "Dell Latitude 5000 series": "DL5000",
            "Dell Latitude 7000 series": "DL7000",
            "HP ProBook 400 Series": "HPPB400",
            "HP EliteBook 800 series": "HPEB800",
            "HP EliteBook 600 series": "HPEB600",
            "Lenovo ThinkPad L Series": "LTPL",
            "Lenovo ThinkPad T Series": "LTPT",
            "Lenovo ThinkPad X Series": "LTPX",
            "Lenovo ThinkPad X1 Carbon": "LTPX1",
            "Apple MacBook Pro": "AMBP",
            "Apple MacBook Air": "AMBA",
            "Unspecified": "U",
            "Other": "O",
        }
        return mapping.get(name, name[:4].upper())

    def _storage_abbr(self, storage):
        mapping = {
            "128GB SSD": "128",
            "256GB SSD": "256",
            "500GB SSD": "500",
            "1TB GB SSD": "1000",
        }
        return mapping.get(storage, storage.split()[0])
