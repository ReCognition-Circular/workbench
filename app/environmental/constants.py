"""Constants for environmental impact reports."""

# Boavizta terminal-archetype endpoint. We use the manufacturing ("embedded")
# phase only; use-phase is ignored (see the methodology in the report template).
BOAVIZTA_TERMINAL_URL = "https://api.boavizta.org/v1/terminal/{slug}"

# The six impact categories reported, in display order.
# Each entry: (key, name, unit, description). Keys match Boavizta impact_criteria.
IMPACT_CATEGORIES = [
    ("gwp", "Global Warming Potential", "kg CO2eq", "Total climate change"),
    ("adpe", "Abiotic Depletion Potential (minerals/metals)", "kg Sb eq", "Use of mineral and metal resources"),
    ("ir", "Ionising Radiations", "kg U235 eq", "Emissions of ionising substances"),
    ("odp", "Ozone Layer Depletion", "kg CFC-11 eq", "Depletion of the ozone layer"),
    ("ap", "Acidification", "mol H+ eq", "Acidification"),
    ("ept", "Terrestrial Eutrophication", "mol N eq", "Terrestrial eutrophication"),
]

# Map device types to Boavizta terminal slugs.
# ALL_IN_ONE has no terminal endpoint, so it is treated as a desktop.
TERMINAL_SLUG = {
    "LAPTOP": "laptop",
    "DESKTOP": "desktop",
    "TABLET": "tablet",
    "ALL_IN_ONE": "desktop",
}

# Device types deliberately excluded from environmental reports.
EXCLUDED_DEVICE_TYPES = ("SERVER", "OTHER", "MONITOR")

METHODOLOGY_VERSION = "boavizta-terminal-v2"
