from django import forms
from django.contrib.auth import get_user_model, password_validation
from django.contrib.auth.forms import AuthenticationForm
from django.core.exceptions import ValidationError

from apps.core.phone import normalize_pk_mobile

from .models import WholesaleProfile


def _style(form):
    """Autofill hints for the phone and password fields."""
    for name, hint in [("username", "tel"), ("phone", "tel"), ("password", "current-password")]:
        if name in form.fields:
            form.fields[name].widget.attrs.setdefault("autocomplete", hint)


class PhoneLoginForm(AuthenticationForm):
    """Customers log in with their mobile number. Staff can still use their username."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].label = "Mobile number or username"
        _style(self)

    def clean_username(self):
        value = self.cleaned_data["username"]
        try:
            return normalize_pk_mobile(value)
        except ValidationError:
            return value


class SignupForm(forms.Form):
    full_name = forms.CharField(max_length=120)
    phone = forms.CharField(max_length=20, label="Mobile number")
    email = forms.EmailField(required=False)
    password = forms.CharField(widget=forms.PasswordInput, help_text="At least 8 characters.")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _style(self)

    def clean_phone(self):
        phone = normalize_pk_mobile(self.cleaned_data["phone"])
        if get_user_model().objects.filter(username=phone).exists():
            raise ValidationError("An account with this number exists. Log in instead.")
        return phone

    def clean_password(self):
        password = self.cleaned_data["password"]
        password_validation.validate_password(password)
        return password

    def save(self):
        data = self.cleaned_data
        return get_user_model().objects.create_user(
            username=data["phone"],
            email=data.get("email", ""),
            password=data["password"],
            first_name=data["full_name"][:150],
        )


class WholesaleForm(forms.ModelForm):
    class Meta:
        model = WholesaleProfile
        fields = ["business_name", "city", "details"]
        widgets = {"details": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _style(self)


class TrackOrderForm(forms.Form):
    number = forms.CharField(max_length=20, label="Order number")
    phone = forms.CharField(max_length=20, label="Mobile number used for the order")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _style(self)

    def clean_phone(self):
        return normalize_pk_mobile(self.cleaned_data["phone"])
