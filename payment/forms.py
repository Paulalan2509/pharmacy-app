from django import forms
from .models import ShippingAddress


class ShippingForm(forms.ModelForm):
    shipping_full_name = forms.CharField(label="Full Name", widget=forms.TextInput(
        attrs={'class': 'form-control', 'placeholder': 'Full Name'}), required=True)
    shipping_email = forms.CharField(label="Email", widget=forms.TextInput(
        attrs={'class': 'form-control', 'placeholder': 'Email Address'}), required=True)
    shipping_address1 = forms.CharField(label="Address 1", widget=forms.TextInput(
        attrs={'class': 'form-control', 'placeholder': 'Address1'}), required=True)
    shipping_address2 = forms.CharField(label="Address 2", widget=forms.TextInput(
        attrs={'class': 'form-control', 'placeholder': 'Address2'}), required=False)
    shipping_city = forms.CharField(label="City",
                                    widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'City'}),
                                    required=True)
    shipping_region = forms.CharField(label="Region",
                                     widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Region'}),
                                     required=False)
    shipping_zipcode = forms.CharField(label="Zipcode", widget=forms.TextInput(
        attrs={'class': 'form-control', 'placeholder': 'Zipcode'}), required=False)
    shipping_country = forms.CharField(label="Country", widget=forms.TextInput(
        attrs={'class': 'form-control', 'placeholder': 'Country'}), required=True)
    shipping_phone = forms.CharField(label="Phone", widget=forms.TextInput(
        attrs={'class': 'form-control', 'placeholder': 'Phone'}), required=True)

    class Meta:
        model = ShippingAddress
        fields = ['shipping_full_name', 'shipping_email', 'shipping_address1', 'shipping_address2', 'shipping_city',
                  'shipping_region', 'shipping_zipcode', 'shipping_country', 'shipping_phone']

