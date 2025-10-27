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
        {"name": "rack_count", "label": "Rack Count", "type": "int", "min": 1, "max": 3, "help": "Number of racks inside the washer."},
        {"name": "water_usage_l", "label": "Water Usage (L)", "type": "float", "min": 5, "max": 30, "step": 0.1, "help": "Estimated liters per cycle."},
        {"name": "sanitize_enabled", "label": "Sanitize Mode", "type": "bool", "help": "Supports high-temp sanitize."},
    ],
    "washing_machine": [
        {"name": "drum_capacity_kg", "label": "Drum Capacity (kg)", "type": "float", "min": 3, "max": 15, "step": 0.5},
        {"name": "spin_speed_rpm", "label": "Spin Speed (RPM)", "type": "int", "min": 400, "max": 1600, "help": "Maximum spin cycle speed."},
    ],
    "dryer": [
        {"name": "drum_capacity_kg", "label": "Drum Capacity (kg)", "type": "float", "min": 3, "max": 12, "step": 0.5},
        {"name": "has_heat_pump", "label": "Heat Pump", "type": "bool", "help": "Indicates if unit uses heat pump tech."},
    ],
    "oven": [
        {"name": "max_temperature_c", "label": "Max Temperature (°C)", "type": "int", "min": 150, "max": 320},
        {"name": "shelf_levels", "label": "Shelf Levels", "type": "int", "min": 1, "max": 5},
        {"name": "has_convection", "label": "Convection Fan", "type": "bool"},
    ],
    "microwave": [
        {"name": "magnetron_watts", "label": "Magnetron Watts", "type": "int", "min": 600, "max": 1800},
        {"name": "sensor_cook", "label": "Sensor Cook", "type": "bool"},
    ],
    "kettle": [
        {"name": "capacity_liters", "label": "Capacity (L)", "type": "float", "min": 0.3, "max": 3.0, "step": 0.1},
        {"name": "keep_warm_minutes", "label": "Keep Warm (min)", "type": "int", "min": 0, "max": 60},
    ],
    "gas": [
        {"name": "burner_count", "label": "Burner Count", "type": "int", "min": 1, "max": 6},
        {"name": "fuel_type", "label": "Fuel Type", "type": "choice", "choices": ["natural_gas", "propane"], "help": "Primary fuel source."},
    ],
    "fridge": [
        {"name": "volume_liters", "label": "Volume (L)", "type": "int", "min": 100, "max": 800},
        {"name": "has_ice_maker", "label": "Ice Maker", "type": "bool"},
    ],
}

APPLIANCE_ILLUSTRATIONS = {
    "dishwasher": """<svg viewBox='0 0 120 120' xmlns='http://www.w3.org/2000/svg'><rect x='10' y='10' width='100' height='100' rx='12' fill='#202737'/><rect x='20' y='25' width='80' height='60' rx='8' fill='#2f3a52'/><circle cx='45' cy='55' r='12' fill='#47b3ff'/><circle cx='75' cy='55' r='12' fill='#47b3ff'/><rect x='30' y='90' width='60' height='8' fill='#47b3ff'/></svg>""",
    "washing_machine": """<svg viewBox='0 0 120 120' xmlns='http://www.w3.org/2000/svg'><rect x='15' y='10' width='90' height='100' rx='14' fill='#212b3a'/><circle cx='60' cy='60' r='32' fill='#324463'/><circle cx='60' cy='60' r='22' fill='#4cd4ff'/></svg>""",
    "dryer": """<svg viewBox='0 0 120 120' xmlns='http://www.w3.org/2000/svg'><rect x='15' y='10' width='90' height='100' rx='10' fill='#2a222a'/><circle cx='60' cy='70' r='30' fill='#ff9f43'/><circle cx='60' cy='70' r='18' fill='#fff3e0'/></svg>""",
    "oven": """<svg viewBox='0 0 120 120' xmlns='http://www.w3.org/2000/svg'><rect x='10' y='15' width='100' height='90' rx='12' fill='#1f1b2d'/><rect x='22' y='45' width='76' height='40' rx='6' fill='#3a2f4d'/><rect x='25' y='55' width='70' height='20' fill='#d86c3d'/></svg>""",
    "microwave": """<svg viewBox='0 0 120 120' xmlns='http://www.w3.org/2000/svg'><rect x='8' y='30' width='104' height='60' rx='8' fill='#1f2a38'/><rect x='18' y='40' width='64' height='40' rx='4' fill='#5bb1ff'/><rect x='88' y='40' width='18' height='40' rx='4' fill='#303b4e'/></svg>""",
    "kettle": """<svg viewBox='0 0 120 120' xmlns='http://www.w3.org/2000/svg'><path d='M80 30h10c8 0 14 6 14 14v10c0 8-6 14-14 14H80' stroke='#5bb1ff' stroke-width='6' fill='none'/><path d='M30 35h50v60a20 20 0 0 1-20 20H50a20 20 0 0 1-20-20z' fill='#2f3649'/></svg>""",
    "gas": """<svg viewBox='0 0 120 120' xmlns='http://www.w3.org/2000/svg'><rect x='12' y='18' width='96' height='84' rx='10' fill='#1d222f'/><circle cx='40' cy='50' r='16' stroke='#4ad5ff' stroke-width='6' fill='none'/><circle cx='80' cy='50' r='16' stroke='#ffcf4d' stroke-width='6' fill='none'/><rect x='28' y='80' width='64' height='12' fill='#333a4a'/></svg>""",
    "fridge": """<svg viewBox='0 0 120 120' xmlns='http://www.w3.org/2000/svg'><rect x='30' y='10' width='60' height='100' rx='12' fill='#1d2f3d'/><line x1='30' y1='60' x2='90' y2='60' stroke='#233f52' stroke-width='4'/><rect x='36' y='30' width='8' height='12' rx='4' fill='#4ad5ff'/><rect x='76' y='75' width='8' height='12' rx='4' fill='#4ad5ff'/></svg>""",
}

DEFAULT_APPLIANCE_ILLUSTRATION = """<svg viewBox='0 0 120 120' xmlns='http://www.w3.org/2000/svg'><rect x='15' y='15' width='90' height='90' rx='18' fill='#1f2635'/><circle cx='60' cy='60' r='26' stroke='#4ad5ff' stroke-width='6' fill='none'/></svg>"""


def get_appliance_form_fields(device_type):
    return APPLIANCE_FORM_FIELDS.get(device_type, [])


def get_appliance_illustration(device_type):
    return APPLIANCE_ILLUSTRATIONS.get(device_type, DEFAULT_APPLIANCE_ILLUSTRATION)
