from django.db import models
import uuid

class Donor(models.Model):
    """
    Donor - Source organisation
    From specification: Organisation that provides devices
    """
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )
    
    name = models.CharField(
        max_length=200,
        help_text="Organisation name"
    )
    
    dolibarr_id = models.IntegerField(
        null=True,
        blank=True,
        help_text="Reference to Dolibarr third party"
    )
    
    contact_name = models.CharField(
        max_length=100,
        blank=True,
        help_text="Primary contact"
    )
    
    contact_email = models.EmailField(
        blank=True,
        help_text="Contact email"
    )
    
    default_ownership_type = models.CharField(
        max_length=20,
        choices=[
            ('DONATION', 'Ownership transfers to ReCognition'),
            ('RAAS', 'Refurb-as-a-Service where ownership stays with donor'),
            ('LEASE_ASSET', 'ReCognition-owned asset for leasing'),
            ('INTERNAL', 'Internal use device')
        ],
        default='DONATION',
        help_text="Default for devices from this donor"
    )
    
    requires_wipe_certificate = models.BooleanField(
        default=True,
        help_text="Send wipe cert automatically"
    )
    
    requires_environmental_report = models.BooleanField(
        default=False,
        help_text="Send impact report"
    )
    
    def __str__(self):
        return self.name
