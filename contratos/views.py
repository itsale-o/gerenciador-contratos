from django.db.models import Count, Q, Sum
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.shortcuts import render
from django.views.generic import ListView, TemplateView

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


class ListaArruamentoBairro(TemplateView):
    template_name = "arruamento_bairro.html"

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        cidade = self.request.GET.get("cidade")
        bairro = self.request.GET.get("bairro")

        contexto["cidades"] = (
            ClaroEndereco.objects
            .values_list("cidade", flat=True)
            .distinct()
            .order_by("cidade")
        )

        if cidade and bairro:
            enderecos = ClaroEndereco.objects.filter(
                cidade=cidade,
                bairro=bairro
            )

            total_enderecos = enderecos.count()

            total_contratos = enderecos.aggregate(
                total=Sum("total")
            )["total"] or 0

            total_livres = enderecos.aggregate(
                livres=Sum["livres"]
            )["livres"] or 0

            penetracao = 0
            if total_enderecos > 0:
                penetracao = round((total_contratos / total_enderecos) * 100, 2)

            contexto.update({
                "cidade": cidade,
                "bairro": bairro,
                "total_enderecos": total_enderecos,
                "total_contratos": total_contratos,
                "total_livres": total_livres,
                "penetracao": penetracao
            })

        return contexto


class ListaArruamento(ListView):
    model = ClaroEndereco
    template_name = "claro_enderecos.html"
    context_object_name = "enderecos"
    paginate_by = 50
    ordering = ["-id"]

    def get_queryset(self):
        queryset = ClaroEndereco.objects.all()

        cidade = self.request.GET.get("cidade")
        bairro = self.request.GET.get("bairro")
        rua = self.request.GET.get("rua")

        if rua:
            return queryset.filter(
                cidade=cidade,
                bairro=bairro,
                logradouro=rua
            )
        
        if bairro:
            return queryset.filter(
                cidade=cidade,
                bairro=bairro
            )
        
        if cidade:
            return (
                queryset
                .filter(cidade=cidade)
                .values("bairro")
                .annotate(
                    total=Count("id"),
                )
                .order_by("bairro")
            )

        return (
            queryset
            .values("cidade")
            .annotate(total=Count("id"))
            .order_by("cidade")
        )

    def render_to_response(self, context, **response_kwargs):
        if self.request.headers.get("HX-Request"):
            return render(
                self.request,
                "contratos/partials/arruamento.html",
                context
            )
        return super().render_to_response(context, **response_kwargs)

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        total_enderecos = ClaroEndereco.objects.count()
        cidades = (
            ClaroEndereco.objects
            .values_list("cidade", flat=True)
            .distinct()
            .order_by("cidade")
        )

        contexto.update({
            "total_enderecos": total_enderecos,
            "cidades": cidades,
        })

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
        "bairros": bairros,
        "cidade": cidade
    })


def carregar_ruas(request):
    cidade = request.GET.get("cidade")
    bairro = request.GET.get("bairro")
    ruas = []

    if cidade and bairro:
        ruas = (
            ClaroEndereco.objects
            .filter(cidade=cidade, bairro=bairro)
            .values_list("logradouro", flat=True)
            .distinct()
            .order_by("logradouro")
        )
    
    return render(request, "contratos/partials/select_rua.html", {
        "ruas": ruas
    })



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