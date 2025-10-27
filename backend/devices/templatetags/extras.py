# your_app/templatetags/extras.py
from django import template
register = template.Library()

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
