from decimal import Decimal

from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import AuthenticationForm
from .models import UserProfile
from .models import Device
from .appliances import (
    APPLIANCE_DEVICE_TYPES,
    get_appliance_form_fields,
    get_appliance_illustration,
)
from .utils import load_device_metadata
from django.db import transaction

class DeviceForm(forms.ModelForm):
    # JSONField in a form gives validation; keep it optional
    metadata = forms.JSONField(required=False)

    class Meta:
        model = Device
        fields = [
            "name",
            "device_type",
            "status",
            "topic",
            "power_rating_watts",
            "target_temperature",
            "mode",
            "metadata",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        base = (
            "w-full px-4 py-2 border border-[color:var(--border)] "
            "bg-[color:var(--bg-base)] text-[color:var(--text-primary)] "
            "rounded-lg focus:outline-none focus:ring-2 focus:ring-[color:var(--accent-primary)]"
        )
        # Style all widgets
        for name, field in self.fields.items():
            cls = field.widget.attrs.get("class", "")
            field.widget.attrs["class"] = (cls + " " + base).strip()

        # Placeholders (optional)
        disallowed = set(APPLIANCE_DEVICE_TYPES)
        self.fields["device_type"].choices = [
            (value, label) for value, label in Device.DEVICE_TYPES if value not in disallowed
        ]

        self.fields["name"].widget.attrs["placeholder"] = "Kitchen Temperature"
        self.fields["topic"].widget.attrs["placeholder"] = "sensors/kitchen/temp"
        self.fields["power_rating_watts"].widget.attrs["placeholder"] = "e.g. 1800"
        self.fields["target_temperature"].widget.attrs["placeholder"] = "Optional target °C"
        self.fields["mode"].widget.attrs["placeholder"] = "eco / normal / turbo"
        self.selected_type = self._resolve_device_type()

    def clean_device_type(self):
        value = self.cleaned_data["device_type"]
        if value in APPLIANCE_DEVICE_TYPES:
            raise forms.ValidationError("Kitchen appliances must be created from the dedicated workflow.")
        return value

    def _resolve_device_type(self):
        if self.data and self.data.get("device_type"):
            return self.data["device_type"]
        if self.initial.get("device_type"):
            return self.initial["device_type"]
        if self.instance and getattr(self.instance, "pk", None):
            return self.instance.device_type
        return Device.DEVICE_TYPES[0][0]


class SignUpForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput)
    role = forms.ChoiceField(choices=UserProfile.ROLE_CHOICES)

    class Meta:
        model = User
        fields = ['username', 'email', 'password']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        base_classes = (
            'w-full px-4 py-2 border border-[color:var(--border)] '
            'bg-[color:var(--bg-base)] text-[color:var(--text-primary)] '
            'rounded-lg focus:outline-none focus:ring-2 focus:ring-[color:var(--accent-primary)]'
        )

        self.fields['username'].widget.attrs.update({
            'class': base_classes, 'placeholder': 'Enter your username'
        })
        self.fields['email'].widget.attrs.update({
            'class': base_classes, 'placeholder': 'Enter your email'
        })
        self.fields['password'].widget.attrs.update({
            'class': base_classes, 'placeholder': 'Enter your password'
        })
        self.fields['role'].widget.attrs.update({'class': base_classes})

    def save(self, commit=True):
        """Create the User and set their UserProfile.role from the form."""
        role = self.cleaned_data['role']

        with transaction.atomic():
            user = super().save(commit=False)
            user.set_password(self.cleaned_data['password'])

            # Optional: map your 'admin' role to Django staff/superuser
            if role == 'admin':
                user.is_staff = True
                # Only set superuser if you REALLY intend full control:
                # user.is_superuser = True

            if commit:
                # Save the user first, then upsert the profile with the chosen role
                user.save()
                UserProfile.objects.update_or_create(
                    user=user,
                    defaults={'role': role}
                )
        return user

class StyledAuthenticationForm(AuthenticationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        base_classes = (
            'w-full px-4 py-2 border border-[color:var(--border)] '
            'bg-[color:var(--bg-base)] text-[color:var(--text-primary)] '
            'rounded-lg focus:outline-none focus:ring-2 focus:ring-[color:var(--accent-primary)]'
        )

        self.fields['username'].widget.attrs.update({
            'class': base_classes,
            'placeholder': 'Enter your username'
        })
        self.fields['password'].widget.attrs.update({
            'class': base_classes,
            'placeholder': 'Enter your password'
        })


class KitchenApplianceForm(forms.ModelForm):
    """Dynamic form that exposes appliance-specific fields and artwork."""

    class Meta:
        model = Device
        fields = [
            "name",
            "device_type",
            "status",
            "topic",
            "power_rating_watts",
            "target_temperature",
            "mode",
        ]

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop("request", None)
        super().__init__(*args, **kwargs)
        self.fields["device_type"].choices = [
            (key, key.replace("_", " ").title()) for key in APPLIANCE_DEVICE_TYPES
        ]
        current_classes = self.fields["device_type"].widget.attrs.get("class", "")
        self.fields["device_type"].widget.attrs["class"] = (current_classes + " capitalize").strip()
        self.fields["topic"].widget.attrs.setdefault("placeholder", "kitchen/device/topic")
        self.fields["mode"].widget.attrs.setdefault("placeholder", "eco")

        self.appliance_field_names = []
        self.appliance_field_configs = []
        self.selected_type = self._resolve_device_type()
        self.illustration_svg = get_appliance_illustration(self.selected_type)
        for cfg in get_appliance_form_fields(self.selected_type):
            field = self._build_dynamic_field(cfg)
            self.fields[cfg["name"]] = field
            self.appliance_field_names.append(cfg["name"])
            self.appliance_field_configs.append(cfg)

    def _resolve_device_type(self):
        if self.data and self.data.get("device_type"):
            return self.data["device_type"]
        if self.initial.get("device_type"):
            return self.initial["device_type"]
        if self.instance and self.instance.pk:
            return self.instance.device_type
        return APPLIANCE_DEVICE_TYPES[0]

    def _build_dynamic_field(self, cfg):
        field_type = cfg.get("type", "float")
        kwargs = {
            "label": cfg.get("label", cfg["name"].replace("_", " ").title()),
            "required": cfg.get("required", True),
            "help_text": cfg.get("help"),
        }
        initial = None
        if self.instance and self.instance.pk:
            meta = load_device_metadata(self.instance)
            initial = meta.get(cfg["name"])
        elif self.initial.get(cfg["name"]):
            initial = self.initial[cfg["name"]]
        if field_type == "bool":
            field = forms.BooleanField(**kwargs)
            field.initial = bool(initial)
            field.required = False
            return field
        if field_type == "choice":
            field = forms.ChoiceField(choices=[(c, c.replace("_", " ").title()) for c in cfg.get("choices", [])], **kwargs)
            field.initial = initial or (cfg.get("choices") or [None])[0]
            return field
        if field_type == "int":
            field = forms.IntegerField(min_value=cfg.get("min"), max_value=cfg.get("max"), **kwargs)
        else:
            field = forms.DecimalField(min_value=cfg.get("min"), max_value=cfg.get("max"), decimal_places=cfg.get("decimal_places", 2), **kwargs)
            field.widget.attrs.setdefault("step", cfg.get("step", 0.1))
        if initial is not None:
            field.initial = initial
        return field

    def clean_device_type(self):
        device_type = self.cleaned_data["device_type"]
        if device_type not in APPLIANCE_DEVICE_TYPES:
            raise forms.ValidationError("Invalid appliance type selected.")
        return device_type

    def save(self, commit=True):
        device = super().save(commit=False)
        meta = load_device_metadata(device)
        for name in self.appliance_field_names:
            value = self.cleaned_data.get(name)
            if isinstance(value, Decimal):
                value = float(value)
            meta[name] = value
        device.metadata = meta
        if commit:
            device.save()
        return device
