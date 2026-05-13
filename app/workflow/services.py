from django.db import transaction
from django.core.exceptions import ValidationError


class TransitionError(Exception):
    """Raised when a stage transition is invalid."""
    pass


class TransitionService:
    """Validates and executes stage transitions for devices."""

    def __init__(self, device, to_stage_code, user=None, notes=""):
        self.device = device
        self.to_stage_code = to_stage_code
        self.user = user
        self.notes = notes

    def validate(self):
        """Check if the transition is allowed. Raises TransitionError if not."""
        from workflow.models import Stage, StageTransition

        current_stage = self.device.stage
        to_stage = Stage.objects.filter(code=self.to_stage_code).first()

        if not to_stage:
            raise TransitionError(f"Stage '{self.to_stage_code}' does not exist.")

        if current_stage == to_stage:
            raise TransitionError(f"Device is already in stage '{to_stage.name}'.")

        if current_stage and current_stage.is_terminal:
            raise TransitionError(
                f"Cannot transition from terminal stage '{current_stage.name}'."
            )

        if current_stage and to_stage not in current_stage.allowed_next_stages.all():
            allowed = [s.code for s in current_stage.allowed_next_stages.all()]
            raise TransitionError(
                f"Cannot transition from '{current_stage.code}' to '{to_stage.code}'. "
                f"Allowed next stages: {', '.join(allowed) if allowed else 'none (terminal stage)'}"
            )

        return to_stage

    def execute(self):
        """Validate and execute the transition. Returns the StageTransition record."""
        from workflow.models import StageTransition

        to_stage = self.validate()

        with transaction.atomic():
            old_stage = self.device.stage

            transition = StageTransition.objects.create(
                device=self.device,
                from_stage=old_stage,
                to_stage=to_stage,
                transitioned_by=self.user,
                notes=self.notes,
            )

            self.device.stage = to_stage
            self.device.save(update_fields=["stage", "updated_at"])

        return transition
