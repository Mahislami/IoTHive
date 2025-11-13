# your_app/templatetags/extras.py
from django import template
from django.utils.translation import gettext, gettext_lazy as _

register = template.Library()

APPLIANCE_LABEL_MAP = {
    "eco": _("Eco"),
    "normal": _("Normal"),
    "intense": _("Intense"),
    "cold": _("Cold"),
    "warm": _("Warm"),
    "hot": _("Hot"),
    "gentle": _("Gentle"),
    "boost": _("Boost"),
    "bake": _("Bake"),
    "broil": _("Broil"),
    "fan": _("Fan"),
    "defrost": _("Defrost"),
    "medium": _("Medium"),
    "high": _("High"),
    "keep-warm": _("Keep Warm"),
    "boil": _("Boil"),
    "simmer": _("Simmer"),
    "cinema": _("Cinema"),
    "standard": _("Standard"),
    "game": _("Game"),
    "vivid": _("Vivid"),
    "vacation": _("Vacation"),
    "rinse": _("Rinse"),
    "wash": _("Wash"),
    "dry": _("Dry"),
    "cooldown": _("Cooldown"),
    "prewash": _("Prewash"),
    "spin": _("Spin"),
}

@register.filter
def get_item(d, key):
    if hasattr(d, 'get'):
        return d.get(key)
    if hasattr(d, '__getitem__'):
        try:
            return d[key]
        except Exception:
            return None
    return None


@register.filter(name="add_class")
def add_class(field, css):
    existing = field.field.widget.attrs.get("class", "")
    new_class = f"{existing} {css}".strip()
    field.field.widget.attrs["class"] = new_class
    return field


@register.filter
def appliance_label(value):
    if value is None:
        return ""
    key = str(value)
    label = APPLIANCE_LABEL_MAP.get(key.lower())
    if label:
        return label
    normalized = key.replace("_", " ").replace("-", " ").title()
    return gettext(normalized)
