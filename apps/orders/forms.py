from django import forms
from django.contrib.auth import get_user_model, password_validation

from apps.core.phone import normalize_pk_mobile
from apps.shipping.models import City

from .models import Order

# Browser autofill hints, so a phone fills the checkout form in a few taps.
AUTOCOMPLETE = {
    "full_name": "name",
    "phone": "tel",
    "email": "email",
    "address": "street-address",
    "password": "new-password",
}


class CheckoutForm(forms.Form):
    full_name = forms.CharField(max_length=120)
    phone = forms.CharField(
        max_length=20, help_text="We call this number to confirm your order.", label="Mobile number"
    )
    email = forms.EmailField(required=False)
    city = forms.ModelChoiceField(
        queryset=City.objects.filter(is_active=True, cod_allowed=True), empty_label="Choose a city"
    )
    address = forms.CharField(widget=forms.Textarea(attrs={"rows": 3}), label="Full address")
    landmark = forms.CharField(max_length=200, required=False, label="Nearest landmark")
    notes = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 2}), required=False, label="Order notes"
    )
    create_account = forms.BooleanField(
        required=False, label="Create an account with these details"
    )
    password = forms.CharField(
        widget=forms.PasswordInput, required=False, help_text="At least 8 characters."
    )

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        for name, hint in AUTOCOMPLETE.items():
            self.fields[name].widget.attrs["autocomplete"] = hint
        self.fields["phone"].widget.attrs.update(
            {"inputmode": "tel", "placeholder": "0300 1234567"}
        )
        self.fields["landmark"].widget.attrs["placeholder"] = "For example, near the mosque gate"
        self.fields["city"].widget.attrs.update(
            {
                "hx-get": "",
                "hx-target": "#order-summary",
                "hx-trigger": "change",
                "hx-include": "this",
            }
        )
        if user and user.is_authenticated:
            del self.fields["create_account"], self.fields["password"]

    def clean_phone(self):
        return normalize_pk_mobile(self.cleaned_data["phone"])

    def clean(self):
        data = super().clean()
        if data.get("create_account"):
            phone, password = data.get("phone"), data.get("password")
            if phone and get_user_model().objects.filter(username=phone).exists():
                self.add_error(
                    "create_account", "An account with this number exists. Log in to use it."
                )
            elif not password:
                self.add_error("password", "Choose a password for your account.")
            else:
                try:
                    password_validation.validate_password(password)
                except forms.ValidationError as exc:
                    self.add_error("password", exc)
        return data


class AdvanceProofForm(forms.ModelForm):
    class Meta:
        model = Order
        fields = ["advance_proof"]
        labels = {"advance_proof": "Screenshot of your payment"}

    def clean_advance_proof(self):
        image = self.cleaned_data.get("advance_proof")
        if not image:
            raise forms.ValidationError("Choose an image.")
        if image.size > 5 * 1024 * 1024:
            raise forms.ValidationError("The image must be 5 MB or smaller.")
        return image
