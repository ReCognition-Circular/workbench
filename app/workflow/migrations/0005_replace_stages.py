from django.db import migrations


def replace_stages(apps, schema_editor):
    Stage = apps.get_model('workflow', 'Stage')
    Device = apps.get_model('devices', 'Device')
    StageTransition = apps.get_model('workflow', 'StageTransition')

    # 0. Delete all StageTransition records
    StageTransition.objects.all().delete()

    # 1. Terminal-stage devices: set allocation_intent, clear stage
    terminal_map = {
        'PARTS_HARVESTING': 'PARTS_HARVESTING',
        'DONATED': 'DEVICE_BANK',
        'RECYCLED': 'RECYCLE',
    }
    for old_code, intent in terminal_map.items():
        try:
            old_stage = Stage.objects.get(code=old_code)
            Device.objects.filter(stage=old_stage).update(
                allocation_intent=intent, stage=None
            )
        except Stage.DoesNotExist:
            pass

    # 2. Delete old stages not being kept
    stages_to_delete = [
        'RECEIVED', 'LOGGED', 'VISUAL_INSPECTION', 'GRADING',
        'REPAIR', 'IMAGING', 'QA_PENDING', 'QA_PASS', 'READY',
        'PARTS_HARVESTING', 'DONATED', 'RECYCLED',
    ]
    Stage.objects.filter(code__in=stages_to_delete).delete()

    # 3. Update existing stages we're keeping
    try:
        awaiting = Stage.objects.get(code='AWAITING_DISPATCH')
        awaiting.name = 'Awaiting Dispatch'
        awaiting.sequence = 3
        awaiting.save(update_fields=['name', 'sequence'])
    except Stage.DoesNotExist:
        awaiting = Stage.objects.create(
            code='AWAITING_DISPATCH', name='Awaiting Dispatch', sequence=3
        )

    try:
        dispatched = Stage.objects.get(code='DISPATCHED')
        dispatched.name = 'Dispatched'
        dispatched.sequence = 4
        dispatched.save(update_fields=['name', 'sequence'])
    except Stage.DoesNotExist:
        dispatched = Stage.objects.create(
            code='DISPATCHED', name='Dispatched', sequence=4
        )

    # 4. Create new stages
    check_in = Stage.objects.create(
        code='CHECK_IN', name='Check-In', sequence=1
    )
    refurb = Stage.objects.create(
        code='REFURB_IN_PROGRESS', name='Refurb In Progress', sequence=2
    )

    # 5. Set allowed_next using real model (historical model lacks M2M)
    from workflow.models import Stage as RealStage

    real_check_in = RealStage.objects.get(code='CHECK_IN')
    real_refurb = RealStage.objects.get(code='REFURB_IN_PROGRESS')
    real_awaiting = RealStage.objects.get(code='AWAITING_DISPATCH')
    real_dispatched = RealStage.objects.get(code='DISPATCHED')

    real_check_in.allowed_next_stages.add(real_refurb, real_awaiting)
    real_refurb.allowed_next_stages.add(real_awaiting)
    real_awaiting.allowed_next_stages.add(real_dispatched)


def reverse_stages(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ('workflow', '0004_rename_repair_to_refurb'),
    ]

    operations = [
        migrations.RunPython(replace_stages, reverse_stages),
    ]
