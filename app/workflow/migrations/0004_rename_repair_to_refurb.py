from django.db import migrations

def rename_stages(apps, schema_editor):
    Stage = apps.get_model('workflow', 'Stage')
    Stage.objects.filter(code='REPAIR_QUEUE').update(code='REFURB_QUEUE')
    Stage.objects.filter(code='IN_REPAIR').update(code='IN_REFURB')
    Stage.objects.filter(code='REPAIR_COMPLETE').update(code='REFURB_COMPLETE')

def reverse_rename(apps, schema_editor):
    Stage = apps.get_model('workflow', 'Stage')
    Stage.objects.filter(code='REFURB_QUEUE').update(code='REPAIR_QUEUE')
    Stage.objects.filter(code='IN_REFURB').update(code='IN_REPAIR')
    Stage.objects.filter(code='REFURB_COMPLETE').update(code='REPAIR_COMPLETE')

class Migration(migrations.Migration):

    dependencies = [
        ('workflow', '0003_add_default_zone'),
    ]

    operations = [
        migrations.RunPython(rename_stages, reverse_rename),
    ]
