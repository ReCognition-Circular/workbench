import secrets
from django.db import models
from django.utils import timezone
from django.contrib.auth.hashers import make_password, check_password


class APIKey(models.Model):
    name = models.CharField(max_length=100, unique=True)
    key_hash = models.CharField(max_length=128, editable=False)
    is_active = models.BooleanField(default=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        'auth.User', on_delete=models.SET_NULL, null=True, blank=True
    )

    def __str__(self):
        return f"{self.name} ({'active' if self.is_active else 'inactive'})"

    @staticmethod
    def generate_raw_key():
        return 'wb-' + secrets.token_urlsafe(32)

    def hash_key(self, raw_key):
        self.key_hash = make_password(raw_key)

    def verify_key(self, raw_key):
        return check_password(raw_key, self.key_hash)

    def record_usage(self):
        self.last_used_at = timezone.now()
        self.save(update_fields=['last_used_at'])
