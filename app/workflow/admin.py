from django.contrib import admin
from .models import Stage


@admin.register(Stage)
class StageAdmin(admin.ModelAdmin):
    list_display = [
        "code",
        "name",
        "sequence",
        "is_terminal",
    ]
    list_filter = ["is_terminal"]
    search_fields = ["code", "name"]
    ordering = ["sequence"]
    filter_horizontal = ["allowed_next_stages"]

    fieldsets = [
        (None, {
            "fields": ["code", "name", "sequence", "is_terminal"]
        }),
        ("Transitions", {
            "fields": ["allowed_next_stages"],
            "description": "Select which stages a device can move to from this stage."
        }),
        ("Quality Gates", {
            "fields": ["quality_gate_checklist", "required_photo_types"],
            "classes": ["collapse"],
        }),
    ]
