from django.db import models


class IntegrationLog(models.Model):
    """Audit log for every ERPNext API call."""

    DIRECTION_CHOICES = [
        ("OUTBOUND", "Outbound — Workbench → ERPNext"),
        ("INBOUND", "Inbound — ERPNext → Workbench (webhook)"),
    ]

    STATUS_CHOICES = [
        ("SUCCESS", "Success"),
        ("FAILED", "Failed"),
        ("PENDING", "Pending"),
    ]

    direction = models.CharField(max_length=10, choices=DIRECTION_CHOICES)
    doctype = models.CharField(max_length=100, blank=True, help_text="ERPNext DocType (e.g. Sales Order)")
    doc_name = models.CharField(max_length=100, blank=True, help_text="ERPNext document name/ID")
    action = models.CharField(max_length=50, help_text="e.g. create, update, get, sync_customers")
    request_payload = models.JSONField(blank=True, null=True)
    response_code = models.IntegerField(blank=True, null=True)
    response_body = models.TextField(blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="PENDING")
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"[{self.status}] {self.direction} {self.action} {self.doctype}"
class CachedProduct(models.Model):
    """Local cache of an ERPNext Item."""

    item_code = models.CharField(max_length=100, unique=True)
    item_name = models.CharField(max_length=200)
    item_group = models.CharField(max_length=100, blank=True)
    is_variant = models.BooleanField(default=False)
    variant_of = models.CharField(max_length=100, blank=True)
    attributes = models.JSONField(blank=True, default=dict)
    last_synced_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["item_code"]

    def __str__(self):
        return f"{self.item_code} — {self.item_name}"    
