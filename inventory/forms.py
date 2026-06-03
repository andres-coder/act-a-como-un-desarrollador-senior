from django import forms

from inventory.models import PurchaseOrder, Supplier


class SupplierForm(forms.ModelForm):
    class Meta:
        model = Supplier
        fields = ['name', 'contact_name', 'email', 'phone', 'address', 'is_active']


class PurchaseOrderForm(forms.ModelForm):
    class Meta:
        model = PurchaseOrder
        fields = ['supplier', 'branch', 'notes']
