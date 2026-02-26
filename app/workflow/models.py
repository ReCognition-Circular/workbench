from django.db import models
from django.contrib.auth.models import User
import uuid

class Stage(models.Model):
    """
    Stage - Workflow stage definition
    From specification: Defines workflow stages with quality gates
    """
    code = models.CharField(
        max_length=50,
        primary_key=True,
        help_text="Stage code (e.g., RECEIVED, DATA_WIPE)"
    )
    
    name = models.CharField(
        max_length=100,
        help_text="Display name"
    )
    
    sequence = models.IntegerField(
        help_text="Order in workflow"
    )
    
    is_terminal = models.BooleanField(
        default=False,
        help_text="True if no further transitions allowed"
    )
    
    quality_gate_checklist = models.JSONField(
        default=dict,
        blank=True,
        help_text="Required checks before exit"
    )
    
    required_photo_types = models.JSONField(
        default=list,
        blank=True,
        help_text="Photo types required before exit"
    )
    
    # Self-referential for allowed transitions
    allowed_next_stages = models.ManyToManyField(
        'self',
        symmetrical=False,
        blank=True,
        help_text="Valid transitions from this stage"
    )
    
    class Meta:
        ordering = ['sequence']
    
    def __str__(self):
        return f"{self.code} - {self.name}"
