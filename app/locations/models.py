from django.db import models
import uuid

class Site(models.Model):
    """
    Site - Physical premises
    From specification: Supports multi-site operations
    """
    code = models.CharField(
        max_length=50,
        primary_key=True,
        help_text="Site code (e.g., RECOGNITION_DIGBETH)"
    )
    
    name = models.CharField(
        max_length=200,
        help_text="Site name (e.g., ReCognition - Digbeth)"
    )
    
    address = models.TextField(
        help_text="Full postal address"
    )
    
    is_active = models.BooleanField(
        default=True,
        help_text="Currently in use"
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When site was added"
    )
    
    deactivated_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When site was closed if applicable"
    )
    
    def __str__(self):
        return f"{self.code} - {self.name}"

class Location(models.Model):
    """
    Location - Physical storage location
    From specification: Hierarchical structure with barcode tracking
    """
    code = models.CharField(
        max_length=20,
        primary_key=True,
        help_text="Location code (e.g., A1-1 or B2-3)"
    )
    
    site = models.ForeignKey(
        Site,
        on_delete=models.CASCADE,
        related_name='locations',
        help_text="Which premises"
    )
    
    zone = models.CharField(
        max_length=10,
        help_text="Top level such as A, B, C"
    )
    
    shelf = models.CharField(
        max_length=10,
        help_text="Second level such as 1, 2, 3, 4"
    )
    
    section = models.CharField(
        max_length=10,
        help_text="Third level such as 1, 2, 3"
    )
    
    description = models.CharField(
        max_length=200,
        blank=True,
        help_text="Human-readable name (optional)"
    )
    
    barcode = models.CharField(
        max_length=50,
        unique=True,
        help_text="Location barcode (unique)"
    )
    
    is_active = models.BooleanField(
        default=True,
        help_text="Available for use"
    )
    
    parent = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='children',
        help_text="For hierarchy (optional)"
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When location was added"
    )
    
    deactivated_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When decommissioned if applicable"
    )
    
    class Meta:
        ordering = ['zone', 'shelf', 'section']
    
    def __str__(self):
        return f"{self.code} ({self.site.code})"
