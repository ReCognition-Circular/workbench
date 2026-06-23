import os
os.environ['DJANGO_SETTINGS_MODULE'] = 'workbench.settings'
import django
django.setup()

from django.conf import settings
middleware = list(settings.MIDDLEWARE)
middleware = [m for m in middleware if 'Message' not in m]
settings.MIDDLEWARE = tuple(middleware)

from django.test import Client
from django.contrib.auth.models import User
from devices.models import Device

client = Client(enforce_csrf_checks=False)
user = User.objects.first()
client.force_login(user)
device = Device.objects.get(pk=125)

client.get(f'/devices/{device.id}/edit/')

response = client.post(f'/devices/{device.id}/edit/', {
    'notes': 'test msg mw removed',
    'grade': 'B',
    'parts_status': 'NOT_NEEDED',
    'parts_notes': '',
    'parts_cost_pounds': '0.00',
    'wipe_status': 'PENDING',
    'wipe_notes': '',
    'win11_compatible': 'NO',
    'allocation_intent': 'UNDECIDED',
    'market_value_pounds': '',
    'processor': '',
    'memory_gb': '',
    'storage_type': 'UNKNOWN',
    'storage_size_gb': '',
}, follow=True)
print(f'Status: {response.status_code}')
print(f'Redirect chain: {response.redirect_chain}')
