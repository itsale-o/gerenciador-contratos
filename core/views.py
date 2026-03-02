from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import UserPassesTestMixin
from django.contrib.auth.models import User
from django.shortcuts import redirect
from django.views.generic import ListView


@login_required
def dashboard_redirect(request):
    user = request.user

    if user.groups.filter(name="Admin").exists():
        return redirect("contratos:dashboard_admin")
    
    if user.groups.filter(name="Vendedor").exists():
        return redirect("contratos:dashboard_vendedor")
    
    return redirect("login")


class ListaVendedores(UserPassesTestMixin, ListView):
    model = User
    template_name = "lista_vendedores.html"
    context_object_name = "vendedores"

    def get_queryset(self):
        return User.objects.filter(groups__name="Vendedor").order_by("username")
    
    def test_func(self):
        return self.request.user.groups.filter(name="Admin").exists()