from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import UserPassesTestMixin
from django.contrib.auth.models import User, Group
from django.db import transaction
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.views.generic import ListView
from django.views.generic.edit import FormMixin

from .forms import FormCadastrarVendedor
from .models import Vendedor


@login_required
def dashboard_redirect(request):
    user = request.user

    if user.groups.filter(name="Admin").exists():
        return redirect("contratos:dashboard_admin")
    
    if user.groups.filter(name="Vendedor").exists():
        return redirect("contratos:dashboard_vendedor")
    
    return redirect("login")


class ListaVendedores(UserPassesTestMixin, FormMixin, ListView):
    model = User
    template_name = "lista_vendedores.html"
    context_object_name = "vendedores"
    form_class = FormCadastrarVendedor
    success_url = reverse_lazy("core:lista_vendedores")

    def get_queryset(self):
        return Vendedor.objects.select_related("usuario").order_by("usuario__username")
    
    def test_func(self):
        return self.request.user.groups.filter(name="Admin").exists()
    
    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["form"] = self.get_form()
        return contexto
    
    def post(self, request, *args, **kwargs):
        form = self.get_form()
        
        if form.is_valid():
            with transaction.atomic():
                user = form.save()

                grupo_vendedor = Group.objects.get(name="Vendedor")
                user.groups.add(grupo_vendedor)

                Vendedor.objects.create(user=User)
            return self.form_valid(form)
        return self.form_invalid(form)