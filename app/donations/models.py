from django.db import models
from django.conf import settings


class DonationPledge(models.Model):
    donor_name = models.CharField(max_length=200)
    donor_contact = models.CharField(max_length=200, blank=True)
    donor_email = models.EmailField()
    donor_erpnext_id = models.CharField(max_length=50, blank=True)
    reference_number = models.CharField(max_length=50, unique=True)

    source = models.CharField(max_length=20, choices=[
        ('WEBFORM', 'Webform'),
        ('STAFF', 'Staff Entry'),
        ('CSV_IMPORT', 'CSV Import'),
    ], default='STAFF')

    status = models.CharField(max_length=20, choices=[
        ('PENDING', 'Pending'),
        ('PARTIAL', 'Partial'),
        ('COMPLETE', 'Complete'),
        ('CANCELLED', 'Cancelled'),
    ], default='PENDING')
        
    storage_removed = models.BooleanField(
        default=False,
        help_text="Donor confirmed storage has been removed or devices already wiped"
    )
    transfer_of_title_signed = models.BooleanField(default=False)
    transfer_of_title_signed_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)

    device_list_file = models.FileField(
        upload_to='donation_csv/',
        null=True, blank=True,
        help_text="CSV file with make, model, serial_number, device_type"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.reference_number} - {self.donor_name}"


class ExpectedDevice(models.Model):
    donation_pledge = models.ForeignKey(
        DonationPledge,
        on_delete=models.CASCADE,
        related_name='expected_devices'
    )
    make = models.CharField(max_length=100)
    model = models.CharField(max_length=200)
    serial_number = models.CharField(max_length=200)
    device_type = models.CharField(
        max_length=20,
        choices=[
            ('LAPTOP', 'Laptop'),
            ('NOTEBOOK', 'Notebook'),
            ('DESKTOP', 'Desktop'),
            ('SERVER', 'Server'),
            ('TABLET', 'Tablet'),
            ('SMARTPHONE', 'Smartphone'),
            ('MONITOR', 'Monitor'),
            ('NETWORK', 'Network Equipment'),
            ('OTHER', 'Other'),
        ],
        default='LAPTOP'
    )

    matched_device = models.ForeignKey(
        'devices.Device',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='expected_device_records'
    )

    status = models.CharField(max_length=20, choices=[
        ('EXPECTED', 'Expected'),
        ('RECEIVED', 'Received'),
        ('MISSING', 'Missing'),
        ('UNEXPECTED', 'Unexpected'),
    ], default='EXPECTED')

    interim_id = models.CharField(max_length=50, blank=True)
    notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    class Meta:
        ordering = ["donation_pledge", "serial_number"]

    def __str__(self):
        return f"{self.serial_number} ({self.make} {self.model})"
