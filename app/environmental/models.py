from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class EnvironmentalReport(models.Model):
    class Kind(models.TextChoices):
        ORDER = "ORDER", "Fulfilment request"
        DONATION = "DONATION", "Donation pledge"

    kind = models.CharField(max_length=10, choices=Kind.choices)

    fulfilment_request = models.ForeignKey(
        "devices.FulfilmentRequest",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="environmental_reports",
    )
    donation_pledge = models.ForeignKey(
        "donations.DonationPledge",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="environmental_reports",
    )

    prepared_for = models.CharField(max_length=200)

    device_count = models.PositiveIntegerField()
    excluded_count = models.PositiveIntegerField(default=0)
    total_gwp_kg = models.DecimalField(max_digits=12, decimal_places=2)

    breakdown_json = models.JSONField(default=dict)
    constants_json = models.JSONField(default=dict)
    methodology_version = models.CharField(max_length=40)

    generated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    generated_at = models.DateTimeField(auto_now_add=True)
    pdf_file = models.FileField(
        upload_to="environmental_reports/", null=True, blank=True
    )

    class Meta:
        ordering = ["-generated_at"]

    def clean(self):
        super().clean()
        if self.kind == self.Kind.ORDER:
            if not self.fulfilment_request or self.donation_pledge:
                raise ValidationError(
                    "An ORDER report requires exactly a fulfilment_request."
                )
        elif self.kind == self.Kind.DONATION:
            if not self.donation_pledge or self.fulfilment_request:
                raise ValidationError(
                    "A DONATION report requires exactly a donation_pledge."
                )

    def __str__(self):
        return f"EnvironmentalReport #{self.pk} ({self.get_kind_display()})"
