from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

from .models import Vendedor


class FormCadastrarVendedor(UserCreationForm):
    ramal = forms.CharField(max_length=10, required=False, label="Ramal")

    class Meta:
        model = User
        fields = ["username", "first_name", "last_name", "email", "ramal"]

    def save(self, commit=True):
        user = super().save(commit)

        if commit:
            Vendedor.objects.create(
                usuario=user,
                ramal=self.cleaned_data.get("ramal") or "000"
            )
        
        return user


class FormEditarUsuarioVendedor(forms.ModelForm):
    class Meta:
        model = User
        fields = ["username", "first_name", "last_name", "email"]


class FormEditarVendedor(forms.ModelForm):
    class Meta:
        model = Vendedor
        fields = ["status", "data_contratacao", "ramal"]