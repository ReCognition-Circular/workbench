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
    default_zone = models.CharField(
        max_length=10,
        blank=True,
        help_text="Expected racking zone (e.g., A, B, C)"
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
    from django.db import models
from django.conf import settings


class StageTransition(models.Model):
    """Records every stage change for a device."""

    device = models.ForeignKey(
        "devices.Device",
        on_delete=models.CASCADE,
        related_name="stage_transitions",
    )
    from_stage = models.ForeignKey(
        Stage,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="transitions_from",
    )
    to_stage = models.ForeignKey(
        Stage,
        on_delete=models.SET_NULL,
        null=True,
        related_name="transitions_to",
    )
    transitioned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        from_code = self.from_stage.code if self.from_stage else "(start)"
        return f"{self.device.inventory_number}: {from_code} → {self.to_stage.code}"
