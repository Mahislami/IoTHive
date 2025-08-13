from django import forms
from django.contrib.auth.models import User
from django.db import transaction
# change 'yourapp' to the app where UserProfile lives
from devices.models import UserProfile

class UserAdminForm(forms.ModelForm):
    role = forms.ChoiceField(choices=UserProfile.ROLE_CHOICES, required=True)

    class Meta:
        model = User
        fields = ["username", "email", "is_active"]  # add "first_name", "last_name" if you want

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # preload role from profile for initial render
        profile = getattr(self.instance, "userprofile", None)
        if profile and "role" not in self.initial:
            self.initial["role"] = profile.role

        base_classes = (
            "w-full px-4 py-2 border border-[color:var(--border)] "
            "bg-[color:var(--bg-base)] text-[color:var(--text-primary)] "
            "rounded-lg focus:outline-none focus:ring-2 focus:ring-[color:var(--accent-primary)]"
        )
        for name, field in self.fields.items():
            field.widget.attrs.setdefault("class", base_classes)

    def save(self, commit=True):
        role = self.cleaned_data["role"]
        with transaction.atomic():
            user = super().save(commit=commit)
            # upsert profile with chosen role
            UserProfile.objects.update_or_create(
                user=user, defaults={"role": role}
            )
            # optional: map role->staff flag
            if role == "admin" and not user.is_staff:
                user.is_staff = True
                if commit:
                    user.save(update_fields=["is_staff"])
            if role != "admin" and user.is_staff:
                user.is_staff = False
                if commit:
                    user.save(update_fields=["is_staff"])
        return user
