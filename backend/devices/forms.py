from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import AuthenticationForm
from .models import UserProfile
from .models import Device
from django.db import transaction

from django import forms
from .models import Device

class DeviceForm(forms.ModelForm):
    # JSONField in a form gives validation; keep it optional
    metadata = forms.JSONField(required=False)

    class Meta:
        model = Device
        fields = ["name", "device_type", "status", "topic", "metadata"]

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
        self.fields["name"].widget.attrs["placeholder"] = "Kitchen Temperature"
        self.fields["topic"].widget.attrs["placeholder"] = "sensors/kitchen/temp"


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