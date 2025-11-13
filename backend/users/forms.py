from django import forms
from django.contrib.auth.models import User
from django.db import transaction
from django.utils.translation import gettext_lazy as _

# change 'yourapp' to the app where UserProfile lives
from devices.models import UserProfile

class UserAdminForm(forms.ModelForm):
    role = forms.ChoiceField(choices=UserProfile.ROLE_CHOICES, required=True)
    password1 = forms.CharField(
        widget=forms.PasswordInput,
        required=False,
        label=_("New password"),
        help_text=_("Leave blank to keep the existing password."),
    )
    password2 = forms.CharField(
        widget=forms.PasswordInput,
        required=False,
        label=_("Confirm new password"),
    )

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
        new_password = self.cleaned_data.get("password1")
        if new_password:
            user.set_password(new_password)
            if commit:
                user.save(update_fields=["password"])
        return user

    def clean(self):
        cleaned = super().clean()
        pw1 = cleaned.get("password1")
        pw2 = cleaned.get("password2")
        if pw1 or pw2:
            if not pw1 or not pw2:
                raise forms.ValidationError(_("Please enter the new password twice."))
            if pw1 != pw2:
                raise forms.ValidationError(_("The two password fields didn’t match."))
        return cleaned

class UserCreateForm(forms.ModelForm):
    role = forms.ChoiceField(choices=UserProfile.ROLE_CHOICES, required=True)
    password1 = forms.CharField(widget=forms.PasswordInput, required=True, label="Password")
    password2 = forms.CharField(widget=forms.PasswordInput, required=True, label="Confirm password")

    class Meta:
        model = User
        fields = ["username", "email", "is_active"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        base = (
            "w-full px-4 py-2 border border-[color:var(--border)] "
            "bg-[color:var(--bg-base)] text-[color:var(--text-primary)] "
            "rounded-lg focus:outline-none focus:ring-2 focus:ring-[color:var(--accent-primary)]"
        )
        for f in self.fields.values():
            f.widget.attrs["class"] = base

    def clean(self):
        data = super().clean()
        if data.get("password1") != data.get("password2"):
            self.add_error("password2", "Passwords do not match.")
        return data

    def save(self, commit=True):
        role = self.cleaned_data["role"]
        with transaction.atomic():
            user = super().save(commit=False)
            user.set_password(self.cleaned_data["password1"])

            # Optional: map role->staff
            if role == "admin":
                user.is_staff = True

            if commit:
                user.save()
                UserProfile.objects.update_or_create(user=user, defaults={"role": role})
        return user
