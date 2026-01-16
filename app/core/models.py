from django.db import models

# Location (barcode tracking)
class Location(models.Model):
    code = models.CharField(max_length=50, primary_key=True)
    name = models.CharField(max_length=200)
    address = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    deactivated_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.name

# Stage (workflow states)
class Stage(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    order = models.PositiveIntegerField(default=0)

    def __str__(self):
        return self.name

# Device (core entity)
class Device(models.Model):
    serial_number = models.CharField(max_length=100, unique=True)
    inventory_number = models.CharField(max_length=50, unique=True)
    location = models.ForeignKey(Location, on_delete=models.SET_NULL, null=True, blank=True)
    stage = models.ForeignKey(Stage, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    notes = models.TextField(blank=True)

    def __str__(self):
        return f"{self.inventory_number} ({self.serial_number})"
  

