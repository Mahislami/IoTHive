from django.utils.translation import gettext_lazy as _


APPLIANCE_SPECS = {
    "dishwasher": {
        "power_rating": 1800,
        "idle": (2, 5),
        "active": (900, 1500),
        "temp_range": (45, 70),
        "heats": True,
        "modes": ["eco", "normal", "intense"],
        "cycles": ["rinse", "wash", "dry"],
    },
    "washing_machine": {
        "power_rating": 2000,
        "idle": (3, 6),
        "active": (500, 1200),
        "temp_range": (30, 60),
        "heats": True,
        "modes": ["cold", "warm", "hot"],
        "cycles": ["prewash", "wash", "spin"],
    },
    "dryer": {
        "power_rating": 2500,
        "idle": (4, 7),
        "active": (1200, 2500),
        "temp_range": (40, 75),
        "heats": True,
        "modes": ["gentle", "normal", "boost"],
        "cycles": ["dry", "cooldown"],
    },
    "oven": {
        "power_rating": 3200,
        "idle": (5, 10),
        "active": (1500, 3200),
        "temp_range": (120, 230),
        "heats": True,
        "modes": ["bake", "broil", "fan"],
    },
    "microwave": {
        "power_rating": 1600,
        "idle": (2, 4),
        "active": (800, 1400),
        "temp_range": (60, 110),
        "heats": True,
        "modes": ["defrost", "medium", "high"],
    },
    "kettle": {
        "power_rating": 2200,
        "idle": (1, 2),
        "active": (1800, 2200),
        "temp_range": (60, 100),
        "heats": True,
        "modes": ["keep-warm", "boil"],
    },
    "gas": {
        "power_rating": 500,
        "idle": (1, 3),
        "active": (200, 800),
        "temp_range": (80, 200),
        "heats": True,
        "modes": ["simmer", "medium", "high"],
    },
    "fridge": {
        "power_rating": 180,
        "idle": (70, 120),
        "active": (120, 200),
        "temp_range": (2, 6),
        "heats": False,
        "modes": ["normal", "boost", "vacation"],
    },
    "tv": {
        "power_rating": 220,
        "idle": (5, 18),
        "active": (120, 220),
        "heats": False,
        "modes": ["cinema", "standard", "game", "vivid"],
    },
}

APPLIANCE_DEVICE_TYPES = tuple(APPLIANCE_SPECS.keys())
AMBIENT_TEMPERATURE = 24.0


def get_appliance_spec(device_type):
    return APPLIANCE_SPECS.get(device_type)


# ---------------------------------------------------------------------------
# UI schemas for appliance-specific forms + lightweight line-art illustrations
# ---------------------------------------------------------------------------

APPLIANCE_FORM_FIELDS = {
    "dishwasher": [
        {"name": "rack_count", "label": _("Rack Count"), "type": "int", "min": 1, "max": 3, "help": _("Number of racks inside the washer.")},
        {"name": "water_usage_l", "label": _("Water Usage (L)"), "type": "float", "min": 5, "max": 30, "step": 0.1, "help": _("Estimated liters per cycle.")},
        {"name": "sanitize_enabled", "label": _("Sanitize Mode"), "type": "bool", "help": _("Supports high-temp sanitize.")},
    ],
    "washing_machine": [
        {"name": "drum_capacity_kg", "label": _("Drum Capacity (kg)"), "type": "float", "min": 3, "max": 15, "step": 0.5},
        {"name": "spin_speed_rpm", "label": _("Spin Speed (RPM)"), "type": "int", "min": 400, "max": 1600, "help": _("Maximum spin cycle speed.")},
    ],
    "dryer": [
        {"name": "drum_capacity_kg", "label": _("Drum Capacity (kg)"), "type": "float", "min": 3, "max": 12, "step": 0.5},
        {"name": "has_heat_pump", "label": _("Heat Pump"), "type": "bool", "help": _("Indicates if unit uses heat pump tech.")},
    ],
    "oven": [
        {"name": "max_temperature_c", "label": _("Max Temperature (°C)"), "type": "int", "min": 150, "max": 320},
        {"name": "shelf_levels", "label": _("Shelf Levels"), "type": "int", "min": 1, "max": 5},
        {"name": "has_convection", "label": _("Convection Fan"), "type": "bool"},
    ],
    "microwave": [
        {"name": "magnetron_watts", "label": _("Magnetron Watts"), "type": "int", "min": 600, "max": 1800},
        {"name": "sensor_cook", "label": _("Sensor Cook"), "type": "bool"},
    ],
    "kettle": [
        {"name": "capacity_liters", "label": _("Capacity (L)"), "type": "float", "min": 0.3, "max": 3.0, "step": 0.1},
        {"name": "keep_warm_minutes", "label": _("Keep Warm (min)"), "type": "int", "min": 0, "max": 60},
    ],
    "gas": [
        {"name": "burner_count", "label": _("Burner Count"), "type": "int", "min": 1, "max": 6},
        {"name": "fuel_type", "label": _("Fuel Type"), "type": "choice", "choices": ["natural_gas", "propane"], "help": _("Primary fuel source.")},
    ],
    "fridge": [
        {"name": "volume_liters", "label": _("Volume (L)"), "type": "int", "min": 100, "max": 800},
        {"name": "has_ice_maker", "label": _("Ice Maker"), "type": "bool"},
    ],
    "tv": [
        {"name": "screen_size_in", "label": _("Screen Size (inches)"), "type": "int", "min": 24, "max": 120},
        {"name": "default_volume", "label": _("Default Volume"), "type": "int", "min": 0, "max": 100},
        {"name": "default_brightness", "label": _("Default Brightness"), "type": "int", "min": 0, "max": 100},
        {"name": "input_source", "label": _("Preferred Input"), "type": "choice", "choices": ["hdmi1", "hdmi2", "hdmi3", "tv", "streaming_box"], "help": _("Default input when the TV powers on.")},
    ],
}

APPLIANCE_ILLUSTRATIONS = {
    "dishwasher": """<svg viewBox='0 0 140 140' xmlns='http://www.w3.org/2000/svg'><rect x='18' y='18' width='104' height='104' rx='16' fill='#1c2333'/><rect x='28' y='36' width='84' height='58' rx='10' fill='#2b3850'/><circle cx='52' cy='66' r='14' fill='#6dd5ff'/><circle cx='88' cy='66' r='14' fill='#58bdf2'/><rect x='44' y='106' width='52' height='10' rx='5' fill='#89e0ff'/><rect x='38' y='24' width='64' height='6' rx='3' fill='#363f57'/></svg>""",
    "washing_machine": """<svg viewBox='0 0 140 140' xmlns='http://www.w3.org/2000/svg'><rect x='24' y='16' width='92' height='112' rx='18' fill='#1f2739'/><circle cx='70' cy='74' r='36' fill='#273650'/><circle cx='70' cy='74' r='28' fill='#8fe1ff'/><circle cx='70' cy='74' r='20' fill='#d7f7ff'/><rect x='40' y='28' width='60' height='8' rx='4' fill='#3c465f'/></svg>""",
    "dryer": """<svg viewBox='0 0 140 140' xmlns='http://www.w3.org/2000/svg'><rect x='24' y='18' width='92' height='108' rx='14' fill='#271d27'/><circle cx='70' cy='80' r='34' fill='#fdd9a0'/><circle cx='70' cy='80' r='22' fill='#ffaf45'/><rect x='46' y='30' width='48' height='12' rx='6' fill='#3d2b3d'/></svg>""",
    "oven": """<svg viewBox='0 0 140 140' xmlns='http://www.w3.org/2000/svg'><rect x='18' y='20' width='104' height='104' rx='16' fill='#231a2b'/><rect x='32' y='52' width='76' height='46' rx='8' fill='#3c2e45'/><rect x='38' y='60' width='64' height='30' rx='6' fill='#f67b45'/><rect x='34' y='30' width='72' height='12' rx='6' fill='#332339'/><circle cx='46' cy='36' r='4' fill='#ffb347'/><circle cx='94' cy='36' r='4' fill='#62e0ff'/></svg>""",
    "microwave": """<svg viewBox='0 0 140 140' xmlns='http://www.w3.org/2000/svg'><rect x='16' y='36' width='108' height='68' rx='12' fill='#1f2b3d'/><rect x='30' y='46' width='66' height='48' rx='6' fill='#7cd3ff'/><rect x='100' y='46' width='16' height='48' rx='6' fill='#2e384c'/><circle cx='108' cy='62' r='4' fill='#86f5ff'/><circle cx='108' cy='78' r='4' fill='#ffb347'/></svg>""",
    "kettle": """<svg viewBox='0 0 140 140' xmlns='http://www.w3.org/2000/svg'><path d='M90 38h14c9 0 16 7 16 16v10c0 9-7 16-16 16H90' stroke='#8be0ff' stroke-width='8' fill='none'/><path d='M36 42h58v66a24 24 0 0 1-24 24H60a24 24 0 0 1-24-24z' fill='#31394f'/><rect x='42' y='26' width='50' height='12' rx='6' fill='#47516c'/><path d='M64 28v16' stroke='#8be0ff' stroke-width='4'/></svg>""",
    "gas": """<svg viewBox='0 0 140 140' xmlns='http://www.w3.org/2000/svg'><rect x='18' y='24' width='104' height='92' rx='14' fill='#1b212f'/><circle cx='48' cy='60' r='18' stroke='#57d2ff' stroke-width='6' fill='none'/><circle cx='94' cy='60' r='18' stroke='#ffc460' stroke-width='6' fill='none'/><rect x='38' y='92' width='64' height='18' rx='6' fill='#31394a'/><rect x='28' y='32' width='84' height='10' rx='5' fill='#2c3446'/></svg>""",
    "fridge": """<svg viewBox='0 0 140 140' xmlns='http://www.w3.org/2000/svg'><rect x='44' y='12' width='52' height='116' rx='16' fill='#1b3142'/><line x1='44' y1='72' x2='96' y2='72' stroke='#24465b' stroke-width='6'/><rect x='50' y='34' width='10' height='16' rx='3' fill='#6ed4ff'/><rect x='80' y='86' width='10' height='18' rx='3' fill='#6ed4ff'/></svg>""",
    "tv": """<svg viewBox='0 0 140 140' xmlns='http://www.w3.org/2000/svg'><rect x='18' y='30' width='104' height='66' rx='12' fill='#111827'/><rect x='26' y='38' width='88' height='50' rx='8' fill='#1f2937'/><rect x='32' y='44' width='76' height='38' rx='6' fill='url(#tvGradient)'/><rect x='60' y='100' width='20' height='18' rx='4' fill='#1f2937'/><defs><linearGradient id='tvGradient' x1='0%' y1='0%' x2='100%' y2='100%'><stop offset='0%' stop-color='#8b5cf6'/><stop offset='50%' stop-color='#22d3ee'/><stop offset='100%' stop-color='#f97316'/></linearGradient></defs></svg>""",
}

DEFAULT_APPLIANCE_ILLUSTRATION = """<svg viewBox='0 0 140 140' xmlns='http://www.w3.org/2000/svg'><rect x='24' y='24' width='92' height='92' rx='20' fill='#1d2535'/><circle cx='70' cy='70' r='30' stroke='#70d8ff' stroke-width='6' fill='none'/><circle cx='70' cy='70' r='12' fill='#70d8ff'/></svg>"""

GENERIC_DEVICE_ILLUSTRATIONS = {
    "sensor": """<svg viewBox='0 0 140 140' xmlns='http://www.w3.org/2000/svg'><rect x='28' y='30' width='84' height='80' rx='18' fill='#222c3b'/><rect x='44' y='44' width='52' height='30' rx='10' fill='#81e1ff'/><rect x='50' y='84' width='40' height='14' rx='6' fill='#39465b'/><circle cx='88' cy='52' r='4' fill='#1b2433'/></svg>""",
    "actuator": """<svg viewBox='0 0 140 140' xmlns='http://www.w3.org/2000/svg'><rect x='22' y='50' width='96' height='40' rx='12' fill='#2a2c45'/><rect x='18' y='64' width='104' height='12' rx='6' fill='#3e4163'/><circle cx='42' cy='70' r='10' fill='#8de3ff'/><circle cx='98' cy='70' r='10' fill='#ff9f68'/><rect x='64' y='36' width='12' height='68' rx='6' fill='#474b6d'/></svg>""",
    "light": """<svg viewBox='0 0 140 140' xmlns='http://www.w3.org/2000/svg'><defs><radialGradient id='glow'><stop offset='0%' stop-color='#ffe58b'/><stop offset='60%' stop-color='#f6c15a'/><stop offset='100%' stop-color='#c57a27'/></radialGradient></defs><rect x='62' y='20' width='16' height='36' rx='8' fill='#414c60'/><circle cx='70' cy='82' r='34' fill='url(#glow)'/><rect x='60' y='108' width='20' height='16' rx='6' fill='#414c60'/></svg>""",
    "thermostat": """<svg viewBox='0 0 140 140' xmlns='http://www.w3.org/2000/svg'><circle cx='70' cy='70' r='46' fill='#1d2835'/><circle cx='70' cy='70' r='36' fill='#273445'/><circle cx='70' cy='70' r='26' fill='#64d4ff'/><line x1='70' y1='26' x2='70' y2='14' stroke='#64d4ff' stroke-width='6' stroke-linecap='round'/><text x='70' y='76' font-size='18' text-anchor='middle' fill='#10202b'>22°</text></svg>""",
    "switch": """<svg viewBox='0 0 140 140' xmlns='http://www.w3.org/2000/svg'><rect x='40' y='24' width='60' height='92' rx='18' fill='#1f2533'/><rect x='50' y='34' width='40' height='72' rx='14' fill='#2f394c'/><rect x='56' y='44' width='28' height='28' rx='10' fill='#7ce0ff'/><rect x='56' y='78' width='28' height='24' rx='10' fill='#394254'/></svg>""",
}

DEVICE_ILLUSTRATIONS = {**GENERIC_DEVICE_ILLUSTRATIONS, **APPLIANCE_ILLUSTRATIONS}


def get_appliance_form_fields(device_type):
    return APPLIANCE_FORM_FIELDS.get(device_type, [])


def get_device_illustration(device_type):
    return DEVICE_ILLUSTRATIONS.get(device_type, DEFAULT_APPLIANCE_ILLUSTRATION)


def get_appliance_illustration(device_type):
    return get_device_illustration(device_type)
