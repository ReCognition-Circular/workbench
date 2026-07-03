from django.db import models
from django.conf import settings


class DataWipeRecord(models.Model):
    CERTIFICATE_TYPES = [
        ("ERASE", "Erase Certificate"),
        ("AUDIT", "Audit Certificate"),
    ]

    device = models.ForeignKey(
        "devices.Device",
        on_delete=models.CASCADE,
        related_name="wipe_records",
    )
    certificate_type = models.CharField(
        max_length=10,
        choices=CERTIFICATE_TYPES,
        default="ERASE",
        help_text="Whether this is an erase or audit certificate from Cedar",
    )
    result = models.CharField(
        max_length=20,
        choices=[
            ("SUCCESS", "Success"),
            ("FAILED", "Failed"),
            ("PASS", "Pass"),
            ("FAIL", "Fail"),
            ("NOT_REQUIRED", "Not Required"),
        ],
        default="SUCCESS",
    )
    wipe_method = models.CharField(max_length=100, blank=True)
    wipe_standard = models.CharField(max_length=100, default="NIST 800-88")
    certificate_file = models.FileField(
        upload_to="wipe_certificates/",
        null=True, blank=True,
    )
    wiped_by = models.CharField(max_length=100, blank=True)
    wiped_at = models.DateTimeField(null=True, blank=True)

    # Cedar JSON data
    json_data = models.JSONField(
        null=True, blank=True,
        help_text="Raw JSON from Cedar certificate",
    )

    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)

    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-uploaded_at"]

    def __str__(self):
        return f"{self.device.inventory_number} - {self.result} ({self.get_certificate_type_display()})"
