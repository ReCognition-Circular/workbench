"""
Management command to seed the three checklist templates and their items.

Usage:  python manage.py seed_checklists
        python manage.py seed_checklists --force   (re-seed even if templates exist)
"""
from django.core.management.base import BaseCommand
from checklists.models import (
    ChecklistTemplate,
    ChecklistTemplateItem,
)

# Maps Cedar component names → RepairTaskType for auto-creating defects
CEDAR_REPAIR_LOOKUP = {
    "motherboard": "MOTHERBOARD_REPAIR",
    "processor": "MOTHERBOARD_REPAIR",
    "memory": "RAM_REPLACEMENT",
    "display": "SCREEN_REPLACEMENT",
    "Storage": "STORAGE_REPLACEMENT",
    "BIOS Logo": "SOFTWARE_ISSUE",
    "battery": "BATTERY_REPLACEMENT",
    "keyboard": "KEYBOARD_REPLACEMENT",
    "WiFi": "MOTHERBOARD_REPAIR",
    "touchscreen": "SCREEN_REPLACEMENT",
    "ethernet": "MOTHERBOARD_REPAIR",
    "speaker": "OTHER",
    "microphone": "OTHER",
    "webcam": "OTHER",
    "pointer": "OTHER",
}

# Standard weight tier points used in auto-grade calculation
WEIGHT_POINTS = {0: 10, 1: 5, 2: 3, 3: 1}

# ── Check-In template items ──────────────────────────────────────────────

CHECKIN_PHYSICAL = [
    ("Physical Track", "Display / screen damage", "PASS_FAIL", 1, True, None, None),
    ("Physical Track", "Hinge condition", "PASS_FAIL", 2, True, None, None),
    ("Physical Track", "Missing parts (bezel, rubber feet, screws)", "PASS_FAIL", 3, True, None, None),
    ("Physical Track", "Case / lid damage (dents, cracks)", "PASS_FAIL", 4, True, None, None),
    ("Physical Track", "Keyboard / trackpad condition", "PASS_FAIL", 5, True, None, None),
    ("Physical Track", "Port damage (USB, HDMI, etc.)", "PASS_FAIL", 6, True, None, None),
    ("Physical Track", "BIOS password present", "YES_NO", 7, True, None, None),
    ("Physical Track", "Serial number / label present", "YES_NO", 8, False, None, None),
    ("Physical Track", "Charger / adapter included", "YES_NO", 9, False, None, None),
    ("Physical Track", "Data Wipe — erasure certificate result", "PASS_FAIL", 10, True, "DATAWIPE_RECORD", None),
]

CHECKIN_CEDAR = [
    # Tier 0 — Critical (10 pts)
    ("Cedar Track", "Motherboard — diagnostic result", "PASS_FAIL", 10, True, "CEDAR_TEST", "motherboard", 0),
    ("Cedar Track", "Processor — diagnostic result", "PASS_FAIL", 11, True, "CEDAR_TEST", "processor", 0),
    # Tier 1 — Major (5 pts)
    ("Cedar Track", "Memory — diagnostic result", "PASS_FAIL", 12, True, "CEDAR_TEST", "memory", 1),
    ("Cedar Track", "Display — diagnostic result", "PASS_FAIL", 13, True, "CEDAR_TEST", "display", 1),
    # Storage removed — not in Cedar audit JSON. ("Cedar Track", "Storage — diagnostic result", "PASS_FAIL", 14, True, "CEDAR_TEST", None, 1),
    ("Cedar Track", "BIOS Logo — diagnostic result", "PASS_FAIL", 15, True, "CEDAR_TEST", "bios", 1),
    ("Cedar Track", "Battery — diagnostic result", "PASS_FAIL", 16, True, "CEDAR_TEST", "battery", 1),
    # Tier 2 — Moderate (3 pts)
    ("Cedar Track", "Keyboard — diagnostic result", "PASS_FAIL", 17, True, "CEDAR_TEST", "keyboard", 2),
    ("Cedar Track", "WiFi — diagnostic result", "PASS_FAIL", 18, True, "CEDAR_TEST", "wifi", 2),
    ("Cedar Track", "Touchscreen — diagnostic result", "PASS_FAIL", 19, True, "CEDAR_TEST", "touchscreen", 2),
    ("Cedar Track", "Ethernet — diagnostic result", "PASS_FAIL", 20, True, "CEDAR_TEST", "ethernet", 2),
    # Tier 3 — Low (1 pt)
    ("Cedar Track", "Speaker — diagnostic result", "PASS_FAIL", 21, True, "CEDAR_TEST", "speaker", 3),
    ("Cedar Track", "Microphone — diagnostic result", "PASS_FAIL", 22, True, "CEDAR_TEST", "microphone", 3),
    ("Cedar Track", "Webcam — diagnostic result", "PASS_FAIL", 23, True, "CEDAR_TEST", "webcam", 3),
    ("Cedar Track", "Pointer / touchpad — diagnostic result", "PASS_FAIL", 24, True, "CEDAR_TEST", "pointer", 3),
]

# ── Refurb template items ────────────────────────────────────────────────

REFURB_SECTION_1 = [
    ("Standard", "Clean device (exterior, screen, keyboard)", "DONE_NOT_DONE", 1, False, None, None),
    ("Standard", "Clean dust from fan / heatsink", "DONE_NOT_DONE", 2, False, None, None),
    ("Standard", "Replace thermal paste (if applicable)", "DONE_NOT_DONE", 3, False, None, None),
    ("Standard", "Test all USB ports", "PASS_FAIL", 4, False, None, None),
    ("Standard", "Test keyboard (all keys)", "PASS_FAIL", 5, False, None, None),
]

REFURB_SECTION_2 = [
    ("OS Install", "OS choice", "SELECT", 6, False, None, None),
    ("OS Install", "OS installed successfully", "PASS_FAIL", 7, False, None, None),
]

REFURB_SECTION_3 = [
    ("Spec-Change", "Storage upgraded", "PASS_FAIL", 8, False, None, None),
    ("Spec-Change", "RAM upgraded", "PASS_FAIL", 9, False, None, None),
]

# ── QA template items ────────────────────────────────────────────────────

QA_SECTION_1 = [
    ("BIOS", "BIOS date/time correct", "PASS_FAIL", 1, False, None, None),
    ("BIOS", "Boot order correct", "PASS_FAIL", 2, False, None, None),
    ("BIOS", "Secure Boot enabled", "PASS_FAIL", 3, False, None, None),
    ("BIOS", "TPM / admin password cleared", "PASS_FAIL", 4, False, None, None),
]

QA_SECTION_2 = [
    ("Physical", "Screen condition", "PASS_FAIL", 5, False, None, None),
    ("Physical", "Keyboard / trackpad", "PASS_FAIL", 6, False, None, None),
    ("Physical", "Hinges / lid action", "PASS_FAIL", 7, False, None, None),
    ("Physical", "All ports functional", "PASS_FAIL", 8, False, None, None),
    ("Physical", "Charger / power LED / cable", "PASS_FAIL", 9, False, None, None),
]

QA_SECTION_3 = [
    ("Records", "Device spec matches record", "PASS_FAIL", 10, False, None, None),
    ("Records", "DataWipeRecord present & cleared", "PASS_FAIL", 11, True, "DATAWIPE_RECORD", None),
    ("Records", "Cedar certificate on file", "PASS_FAIL", 12, True, "CEDAR_TEST", None),
    ("Records", "Refurb checklist complete", "PASS_FAIL", 13, True, "REFURB_STATUS", None),
]


def _build_template_items(template, items, options=None):
    """Create ChecklistTemplateItem rows for a given template."""
    for row in items:
        section, label, item_type, order, generates_defect, auto_source, cedar_key = row[:7]
        weight_tier = row[7] if len(row) > 7 else None

        kwargs = dict(
            template=template,
            section_label=section,
            label=label,
            item_type=item_type,
            order_number=order,
            generates_defect=generates_defect,
            is_auto_populated=bool(auto_source),
            auto_source=auto_source or None,
            cedar_component_key=cedar_key,
            weight_tier=weight_tier,
        )
        if options:
            kwargs["options"] = options
        ChecklistTemplateItem.objects.create(**kwargs)


class Command(BaseCommand):
    help = "Seed the three checklist templates (check-in, refurb, qa) and their items."

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Delete existing templates and re-seed from scratch.",
        )

    def handle(self, *args, **options):
        if options["force"]:
            ChecklistTemplate.objects.all().delete()
            self.stdout.write(self.style.WARNING("Deleted all existing templates."))

        if ChecklistTemplate.objects.exists():
            self.stdout.write(
                self.style.WARNING(
                    "Templates already exist. Use --force to re-seed."
                )
            )
            return

        # ── Check-In ─────────────────────────────────────────────────────
        ct_checkin = ChecklistTemplate.objects.create(
            code="check-in",
            name="Check-In Checklist",
            version=1,
        )
        _build_template_items(ct_checkin, CHECKIN_PHYSICAL)
        _build_template_items(ct_checkin, CHECKIN_CEDAR)
        self.stdout.write(f"  ✅ Check-In — {ct_checkin.items.count()} items")

        # ── Refurb ────────────────────────────────────────────────────────
        ct_refurb = ChecklistTemplate.objects.create(
            code="refurb",
            name="Refurb Checklist",
            version=1,
        )
        _build_template_items(ct_refurb, REFURB_SECTION_1)
        _build_template_items(ct_refurb, REFURB_SECTION_2, options=["Windows 11", "Ubuntu", "Linux Mint", "Other"])
        _build_template_items(ct_refurb, REFURB_SECTION_3)
        self.stdout.write(f"  ✅ Refurb — {ct_refurb.items.count()} items")

        # ── QA ────────────────────────────────────────────────────────────
        ct_qa = ChecklistTemplate.objects.create(
            code="qa",
            name="QA Checklist",
            version=1,
        )
        _build_template_items(ct_qa, QA_SECTION_1)
        _build_template_items(ct_qa, QA_SECTION_2)
        _build_template_items(ct_qa, QA_SECTION_3)
        self.stdout.write(f"  ✅ QA — {ct_qa.items.count()} items")

        self.stdout.write(self.style.SUCCESS("\nSeed complete — 3 templates created."))

