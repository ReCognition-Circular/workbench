from django.db import migrations


def add_qa_remove_dispatched(apps, schema_editor):
    Stage = apps.get_model('workflow', 'Stage')
    Device = apps.get_model('devices', 'Device')

    # 1. Move DISPATCHED devices to AWAITING_DISPATCH
    try:
        dispatched = Stage.objects.get(code='DISPATCHED')
        awaiting = Stage.objects.get(code='AWAITING_DISPATCH')
        Device.objects.filter(stage=dispatched).update(stage=awaiting)
        dispatched.delete()
    except Stage.DoesNotExist:
        pass

    # 2. Create QA stage
    qa = Stage.objects.create(
        code='QA', name='QA', sequence=3
    )

    # 3. Re-sequence AWAITING_DISPATCH
    awaiting = Stage.objects.get(code='AWAITING_DISPATCH')
    awaiting.sequence = 4
    awaiting.save(update_fields=['sequence'])

    # 4. Rebuild allowed_next_stages using real model
    from workflow.models import Stage as RealStage

    real_check_in = RealStage.objects.get(code='CHECK_IN')
    real_refurb = RealStage.objects.get(code='REFURB_IN_PROGRESS')
    real_qa = RealStage.objects.get(code='QA')
    real_awaiting = RealStage.objects.get(code='AWAITING_DISPATCH')

    # Clear existing
    for s in [real_check_in, real_refurb, real_qa, real_awaiting]:
        s.allowed_next_stages.clear()

    # Set new transitions
    real_check_in.allowed_next_stages.add(real_refurb, real_qa)
    real_refurb.allowed_next_stages.add(real_qa)
    real_qa.allowed_next_stages.add(real_awaiting, real_refurb)


def reverse_stages(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ('workflow', '0005_replace_stages'),
    ]

    operations = [
        migrations.RunPython(add_qa_remove_dispatched, reverse_stages),
    ]
