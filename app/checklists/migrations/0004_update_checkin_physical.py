from django.db import migrations


def update_checkin_physical(apps, schema_editor):
    ChecklistTemplate = apps.get_model("checklists", "ChecklistTemplate")
    ChecklistTemplateItem = apps.get_model("checklists", "ChecklistTemplateItem")

    # ⚠️ Confirm this is your actual check-in template code (could be "check-in", "checkin", etc.)
    checkin = ChecklistTemplate.objects.get(code="check-in")

    # (a) Backfill: existing Pass/Fail items that generate defects now fire on "FAIL"
    #     (covers physical items 1-6 and the 15 Cedar-track items).
    ChecklistTemplateItem.objects.filter(
        template=checkin,
        item_type="PASS_FAIL",
        generates_defect=True,
    ).update(defect_trigger_value="FAIL")

    # (b) Item 7 — BIOS: rename + defect fires on "No"
    ChecklistTemplateItem.objects.update_or_create(
        template=checkin,
        order_number=7,
        defaults={
            "section_label": "Physical Track",
            "label": "BIOS accessible (no password lock)",
            "item_type": "YES_NO",
            "is_auto_populated": False,
            "generates_defect": True,
            "defect_trigger_value": "NO",
            "photo_required": False,
            "max_photos": 0,
        },
    )

    # (c) Item 10 — PXE boot successful: new, no defect
    ChecklistTemplateItem.objects.update_or_create(
        template=checkin,
        order_number=10,
        defaults={
            "section_label": "Physical Track",
            "label": "PXE boot successful",
            "item_type": "YES_NO",
            "is_auto_populated": False,
            "generates_defect": False,
            "defect_trigger_value": None,
            "photo_required": False,
            "max_photos": 0,
        },
    )


class Migration(migrations.Migration):
    dependencies = [
        ("checklists", "0003_checklisttemplateitem_defect_trigger_value"),
    ]

    operations = [
        migrations.RunPython(update_checkin_physical, migrations.RunPython.noop),
    ]
