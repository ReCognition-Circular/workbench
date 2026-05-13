from django.core.management.base import BaseCommand
from api.models import APIKey


class Command(BaseCommand):
    help = 'Create a new API key for an external system'

    def add_arguments(self, parser):
        parser.add_argument('name', type=str)

    def handle(self, *args, **options):
        name = options['name']

        if APIKey.objects.filter(name=name).exists():
            self.stderr.write(self.style.ERROR(f"Key '{name}' already exists"))
            return

        raw_key = APIKey.generate_raw_key()
        api_key = APIKey(name=name)
        api_key.hash_key(raw_key)
        api_key.save()

        self.stdout.write(self.style.SUCCESS(f'API key created for: {name}'))
        self.stdout.write(f'Key: {raw_key}')
        self.stdout.write(self.style.WARNING(
            'Store this key securely. It will not be shown again.'
        ))
