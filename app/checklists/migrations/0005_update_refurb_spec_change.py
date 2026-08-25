from django.db import migrations

STORAGE_TYPES = ["HDD", "SSD", "NVMe", "eMMC"]

NEW_ITEMS = [
    # (section, label, item_type, order, auto_source, cedar_key, options)
    ("Spec-Change", "Storage changed", "YES_NO", 8, None, None, None),
    ("Spec-Change", "Storage old type", "SELECT", 9, "DEVICE_SPEC", "storage_type", STORAGE_TYPES),
    ("Spec-Change", "Storage old size (GB)", "TEXT", 10, "DEVICE_SPEC", "storage_size_gb", None),
    ("Spec-Change", "Storage new type", "SELECT", 11, None, None, STORAGE_TYPES),
    ("Spec-Change", "Storage new size (GB)", "TEXT", 12, None, None, None),
    ("Spec-Change", "RAM changed", "YES_NO", 13, None, None, None),
    ("Spec-Change", "RAM old size (GB)", "TEXT", 14, "DEVICE_SPEC", "memory_gb", None),
    ("Spec-Change", "RAM new size (GB)", "TEXT", 15, None, None, None),
]

OLD_LABELS = ["Storage upgraded", "RAM upgraded"]

NEW_OS_OPTIONS = ["Windows 11", "Ubuntu", "Linux Mint", "Other", "None"]


def forwards(apps, schema_editor):
    ChecklistTemplateItem = apps.get_model("checklists", "ChecklistTemplateItem")
    ChecklistTemplate = apps.get_model("checklists", "ChecklistTemplate")
    ChecklistItemResponse = apps.get_model("checklists", "ChecklistItemResponse")

    refurb = ChecklistTemplate.objects.filter(code="refurb").first()
    if not refurb:
        return

    old_items = ChecklistTemplateItem.objects.filter(
        template=refurb, section_label="Spec-Change", label__in=OLD_LABELS
    )

    # Delete responses referencing the old items first (protected FK)
    ChecklistItemResponse.objects.filter(template_item__in=old_items).delete()

    # Now safe to delete the old Spec-Change items
    old_items.delete()

    # Create the new Spec-Change items
    for section, label, item_type, order, auto_source, cedar_key, options in NEW_ITEMS:
        ChecklistTemplateItem.objects.create(
            template=refurb,
            section_label=section,
            label=label,
            item_type=item_type,
            order_number=order,
            generates_defect=False,
            is_auto_populated=bool(auto_source),
            auto_source=auto_source,
            cedar_component_key=cedar_key,
            options=options,
        )

    # Add "None" to the OS choice options
    os_item = ChecklistTemplateItem.objects.filter(
        template=refurb, section_label="OS Install", label="OS choice"
    ).first()
    if os_item:
        os_item.options = NEW_OS_OPTIONS
        os_item.save(update_fields=["options"])


def backwards(apps, schema_editor):
    ChecklistTemplateItem = apps.get_model("checklists", "ChecklistTemplateItem")
    ChecklistTemplate = apps.get_model("checklists", "ChecklistTemplate")

    refurb = ChecklistTemplate.objects.filter(code="refurb").first()
    if not refurb:
        return

    # Remove the new Spec-Change items
    ChecklistTemplateItem.objects.filter(
        template=refurb, section_label="Spec-Change"
    ).delete()

    # Restore the two old Pass/Fail items
    ChecklistTemplateItem.objects.create(
        template=refurb, section_label="Spec-Change",
        label="Storage upgraded", item_type="PASS_FAIL",
        order_number=8, generates_defect=False,
    )
    ChecklistTemplateItem.objects.create(
        template=refurb, section_label="Spec-Change",
        label="RAM upgraded", item_type="PASS_FAIL",
        order_number=9, generates_defect=False,
    )

    # Restore original OS options
    os_item = ChecklistTemplateItem.objects.filter(
        template=refurb, section_label="OS Install", label="OS choice"
    ).first()
    if os_item:
        os_item.options = ["Windows 11", "Ubuntu", "Linux Mint", "Other"]
        os_item.save(update_fields=["options"])


class Migration(migrations.Migration):

    dependencies = [
        ("checklists", "0004_update_checkin_physical"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
