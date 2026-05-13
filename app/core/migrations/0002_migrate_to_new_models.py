from django.db import migrations


def migrate_location(apps, schema_editor):
    CoreLocation = apps.get_model("core", "Location")
    Site = apps.get_model("locations", "Site")
    Location = apps.get_model("locations", "Location")

    for cl in CoreLocation.objects.all():
        site, _ = Site.objects.get_or_create(
            code=cl.code,
            defaults={
                "name": cl.name,
                "address": cl.address or "",
                "is_active": cl.is_active,
                "created_at": cl.created_at,
                "deactivated_at": cl.deactivated_at,
            },
        )
        Location.objects.get_or_create(
            code=cl.code,
            defaults={
                "site": site,
                "zone": cl.code[:1] if cl.code else "X",
                "shelf": "1",
                "section": "1",
                "barcode": cl.code,
                "description": cl.name,
                "is_active": cl.is_active,
                "created_at": cl.created_at,
                "deactivated_at": cl.deactivated_at,
            },
        )


def migrate_stage(apps, schema_editor):
    CoreStage = apps.get_model("core", "Stage")
    Stage = apps.get_model("workflow", "Stage")

    for cs in CoreStage.objects.all():
        Stage.objects.get_or_create(
            code=cs.name.upper().replace(" ", "_"),
            defaults={
                "name": cs.name,
                "sequence": cs.order,
                "is_terminal": False,
            },
        )


def migrate_device(apps, schema_editor):
    CoreDevice = apps.get_model("core", "Device")
    Location = apps.get_model("locations", "Location")
    Stage = apps.get_model("workflow", "Stage")
    Device = apps.get_model("devices", "Device")

    for cd in CoreDevice.objects.all():
        location = Location.objects.filter(code=cd.location_id).first() if cd.location_id else None
        stage = Stage.objects.filter(code=cd.stage.name.upper().replace(" ", "_")).first() if cd.stage else None
        Device.objects.get_or_create(
            inventory_number=cd.inventory_number,
            defaults={
                "serial_number": cd.serial_number,
                "location": location,
                "stage": stage,
                "notes": cd.notes or "",
                "created_at": cd.created_at,
                "updated_at": cd.updated_at,
            },
        )


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0001_initial"),
        ("locations", "0001_initial"),
        ("workflow", "0001_initial"),
        ("devices", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(migrate_location),
        migrations.RunPython(migrate_stage),
        migrations.RunPython(migrate_device),
    ]
