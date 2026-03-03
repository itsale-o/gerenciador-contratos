from django.db.models import Count, Q, Sum, Sum, Avg
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.shortcuts import render
from django.views.generic import ListView, TemplateView
from django.utils.timezone import now
from datetime import date

from core.models import Lead
from .models import Contrato, ClaroEndereco


class DashboardAdmin(LoginRequiredMixin, TemplateView):
    template_name = "dashboard_admin.html"
    
    def dispatch(self, request, *args, **kwargs):
        if not request.user.groups.filter(name="Admin").exists():
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)

        contratos = Contrato.objects.using("contratos").all()

        hoje = now().date()
        inicio_mes = date(hoje.year, hoje.month, 1)

        total_contratos = contratos.count()
        total_contratos_ativos = contratos.filter(status="ATIVO").count()
        total_contratos_encerrados = contratos.filter(status="CANCELADO").count()
        total_contratos_suspensos = contratos.filter(status="SUSPENSÃO PARCIAL").count()

        receita_mensal = (
            contratos.filter(status="ATIVO")
            .aggregate(total=Sum("valor"))["total"] or 0
        )

        total_em_aberto = (
            contratos.aggregate(total=Sum("devedor"))["total"] or 0
        )

        ticket_medio = (
            contratos.filter(status="ATIVO")
            .aggregate(media=Avg("valor"))["media"] or 0
        )

        contratos_inadimplentes = contratos.filter(devedor__gt=0).count()

        cancelamentos_mes = contratos.filter(
            status="CANCELADO",
            cancelamento__gte=inicio_mes
        ).count()

        total_leads_distribuidos = Lead.objects.count()
        vendedores_ativos = Lead.objects.values("vendedor").distinct().count()

        contexto.update({
            "total_contratos": total_contratos,
            "total_contratos_ativos": total_contratos_ativos,
            "total_contratos_encerrados": total_contratos_encerrados,
            "total_contratos_suspensos": total_contratos_suspensos,
            "receita_mensal": receita_mensal,
            "total_em_aberto": total_em_aberto,
            "ticket_medio": ticket_medio,
            "contratos_inadimplentes": contratos_inadimplentes,
            "cancelamentos_mes": cancelamentos_mes,
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


class ListaLeadsBairro(ListView):
    model = Contrato
    template_name = "leads_endereco.html"
    context_object_name = "contratos"
    paginate_by = 50

    def get_queryset(self):
        cidade = self.request.GET.get("cidade")
        bairro = self.request.GET.get("bairro")
        rua = self.request.GET.get("rua")

        queryset = Contrato.objects.filter(
            cidade=cidade,
            bairro=bairro
        )

        if rua:
            queryset = queryset.filter(endereco=rua)

        return queryset.order_by("endereco")
    
    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        cidade = self.request.GET.get("cidade")
        bairro = self.request.GET.get("bairro")

        contexto["cidade"] = cidade
        contexto["bairro"] = bairro
        
        contexto["ruas"] = (
            ClaroEndereco.objects
            .filter(cidade=cidade, bairro=bairro)
            .values_list("logradouro", flat=True)
            .distinct()
            .order_by("logradouro")
        )

        return contexto


class ListaArruamento(ListView):
    template_name = "claro_enderecos.html"
    context_object_name = "bairros"
    paginate_by = 50

    def get_queryset(self):
        queryset = (
            ClaroEndereco.objects
            .values("cidade", "bairro")
            .annotate(
                total_portas=Sum("total"),
                total_livres=Sum("livres"),
                media_penetracao=Avg("penetracao"),
            )
            .order_by("cidade", "bairro")
        )

        cidade = self.request.GET.get("cidade")
        bairro = self.request.GET.get("bairro")

        if cidade:
            queryset = queryset.filter(cidade=cidade)
        
        if bairro:
            queryset = queryset.filter(bairro=bairro)

        return queryset

    def render_to_response(self, context, **response_kwargs):
        if self.request.headers.get("HX-Request"):
            return render(self.request, "contratos/partials/arruamento.html", context)
        return super().render_to_response(context, **response_kwargs)
    
    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)

        contexto["cidades"] = (
            ClaroEndereco.objects
            .values_list("cidade", flat=True)
            .distinct()
            .order_by("cidade")
        )

        cidade = self.request.GET.get("cidade")

        if cidade:
            contexto["lista_bairros"] = (
                ClaroEndereco.objects
                .filter(cidade=cidade)
                .values_list("bairro", flat=True)
                .distinct()
                .order_by("bairro")
            )
        else:
            contexto["lista_bairros"] = []

        return contexto


def carregar_bairros(request):
    cidade = request.GET.get("cidade")
    bairros = []

    if cidade:
        bairros = (
            ClaroEndereco.objects
            .filter(cidade=cidade)
            .values_list("bairro", flat=True)
            .distinct()
            .order_by("bairro")
        )

    return render(request, "contratos/partials/select_bairro.html", {
        "lista_bairros": bairros,
    })


# def carregar_ruas(request):
#     cidade = request.GET.get("cidade")
#     bairro = request.GET.get("bairro")
#     ruas = []

#     if cidade and bairro:
#         ruas = (
#             ClaroEndereco.objects
#             .filter(cidade=cidade, bairro=bairro)
#             .values_list("logradouro", flat=True)
#             .distinct()
#             .order_by("logradouro")
#         )
    
#     return render(request, "contratos/partials/select_rua.html", {
#         "ruas": ruas
#     })



class LeadsEndereco(TemplateView):
    template_name = "leads_endereco.html"

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        endereco_id = self.kwargs.get("pk")
        endereco = ClaroEndereco.objects.get(pk=endereco_id)

        contratos_rua = Contrato.objects.filter(
            cidade=endereco.cidade,
            bairro=endereco.bairro,
            endereco=endereco.logradouro
        )

        contratos_bairro = Contrato.objects.filter(
            cidade=endereco.cidade,
            bairro=endereco.bairro
        ).exclude(endereco=endereco.logradouro)

        contexto.update({
            "endereco_obj": endereco,
            "contratos_rua": contratos_rua,
            "contratos_bairro": contratos_bairro,
        })

        return contexto