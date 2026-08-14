"""Constants for environmental impact reports."""

# Boavizta terminal-archetype embedded (manufacturing) GWP, kg CO2e.
# Captured 2026-08-12 from POST https://api.boavizta.org/v1/terminal/{type}
# (empty body). Each returns min == max == value with the warning
# "Generic data used for impact calculation."
BOAVIZTA_TERMINAL_GWP_KG = {
    "LAPTOP": 181.0,
    "DESKTOP": 277.0,
    "ALL_IN_ONE": 277.0,
    "TABLET": 75.9,
}

# Device types deliberately excluded from environmental reports.
# MONITOR is not yet a DeviceType choice (pending the device-type fix),
# but is listed here so it is excluded automatically once added.
EXCLUDED_DEVICE_TYPES = ("SERVER", "OTHER", "MONITOR")

METHODOLOGY_VERSION = "boavizta-terminal-v1"
