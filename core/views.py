from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import UserPassesTestMixin
from django.contrib.auth.models import User, Group
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.db.models import Count
from django.db import transaction
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.views.generic import ListView, TemplateView
from django.views.generic.edit import FormMixin

from .forms import FormCadastrarVendedor
from .models import Vendedor, Lead


@login_required
def dashboard_redirect(request):
    user = request.user

    if user.groups.filter(name="Admin").exists():
        return redirect("contratos:dashboard_admin")
    
    if user.groups.filter(name="Vendedor").exists():
        return redirect("core:dashboard_vendedor")
    
    return redirect("login")

class DashboardVendedor(LoginRequiredMixin, TemplateView):
    template_name = "dashboard_vendedor.html"

    def dispatch(self, request, *args, **kwargs):

        if not request.user.groups.filter(name="Vendedor").exists():
            raise PermissionDenied

        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)

        vendedor = Vendedor.objects.get(usuario=self.request.user)

        leads = Lead.objects.filter(vendedor=vendedor)

        total_leads = leads.count()

        leads_pendentes = leads.filter(resolvido=False).count()

        leads_resolvidos = leads.filter(resolvido=True).count()

        contexto["total_leads"] = total_leads
        contexto["leads_pendentes"] = leads_pendentes
        contexto["leads_resolvidos"] = leads_resolvidos

        return contexto

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

                Vendedor.objects.create(usuario=user)
            messages.success(request, "Vendedor(a) cadastrado(a) com sucesso.")
            return self.form_valid(form)
        
        messages.error(request, "Erro ao cadastrar vendedor(a). Verifique os dados.")

        self.object_list = self.get_queryset()
        return self.form_invalid(form)


class ListaLeadsVendedor(ListView):
    model = Lead
    template_name = "lista_leads.html"
    context_object_name = "leads"
    
    def get_queryset(self):
        usuario = self.request.user
        return Lead.objects.filter(vendedor__usuario=usuario)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        contratos_ids = [lead.contrato_id for lead in context["leads"]]

        from contratos.models import Contrato
        contratos = Contrato.objects.filter(contrato__in=contratos_ids)

        contratos_map = {c.contrato: c for c in contratos}

        context["contratos_map"] = contratos_map

        return context
    
