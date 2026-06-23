from django.core.management.base import BaseCommand
from devices.models import Device
from devices.win11_check import determine_win11_compatible

class Command(BaseCommand):
    help = 'Calculate Windows 11 compatibility from processor specs for all devices'

    def handle(self, *args, **options):
        devices = Device.objects.select_related('device_specification').all()
        updated = 0
        skipped = 0

        for device in devices:
            spec = device.device_specification
            processor = spec.processor if spec else ''
            
            if not processor:
                skipped += 1
                continue

            new_value = determine_win11_compatible(processor)
            if new_value != device.win11_compatible:
                device.win11_compatible = new_value
                device.save(update_fields=['win11_compatible'])
                updated += 1
                self.stdout.write(f'  {device.inventory_number}: {device.win11_compatible} ← {processor[:50]}')

        self.stdout.write(self.style.SUCCESS(
            f'\nDone. Updated: {updated}, Skipped (no processor): {skipped}'
        ))
