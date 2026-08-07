from django.apps import AppConfig


class ChecklistsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'checklists'

    def ready(self):
        import checklists.signals  # noqa — register Cedar hook signal'
