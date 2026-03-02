from django.db.models import Q
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.shortcuts import render
from django.views.generic import ListView, TemplateView

from core.models import Lead
from .models import Contrato


class DashboardAdmin(LoginRequiredMixin, TemplateView):
    template_name = "dashboard_admin.html"
    
    def dispatch(self, request, *args, **kwargs):
        if not request.user.groups.filter(name="Admin").exists():
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        total_contratos = Contrato.objects.count()
        total_contratos_ativos = Contrato.objects.filter(status="ATIVO").count()
        total_contratos_encerrados = Contrato.objects.filter(status="CANCELADO").count()
        total_leads_distribuidos = Lead.objects.count()
        vendedores_ativos = (
            Lead.objects.values("vendedor").distinct().count()
        )


        contexto.update({
            "total_contratos": total_contratos,
            "total_contratos_ativos": total_contratos_ativos,
            "total_contratos_encerrados": total_contratos_encerrados,
            "total_leads_distribuidos": total_leads_distribuidos,
            "vendedores_ativos": vendedores_ativos,
        })

        return contexto



class ListaContratos(ListView):
    model = Contrato
    template_name = "contratos/lista_contratos.html"
    context_object_name = "contratos"
    paginate_by = 50
    ordering = ["-id"]

    def get_queryset(self):
        queryset = Contrato.objects.using("contratos").all()
        
        termo_pesquisa = self.request.GET.get("search", "").strip()
        campo = self.request.GET.get("campo", "")
        status = self.request.GET.get("status", "")

        if status:
            queryset = queryset.filter(status=status)

        if termo_pesquisa and campo:
            mapa_campos = {
                "CID": "CID__icontains",
                "Valor": "Valor__icontains",
                "Cidade": "Cidade__icontains",
            }

            if campo in mapa_campos:
                queryset = queryset.filter(
                    Q(**{
                        mapa_campos[campo]: termo_pesquisa
                    })
                )

        return queryset

    def render_to_response(self, context, **response_kwargs):
        if self.request.headers.get("HX-Request"):
            return render(self.request, "contratos/partials/contratos.html", context)
        return super().render_to_response(context, **response_kwargs)


# def lista_contratos_teste(request):
#     contratos = Contrato.objects.using("contratos").all()[:50]

#     return render(request, "contratos/lista_contratos.html", {
#         "contratos": contratos
#     })
