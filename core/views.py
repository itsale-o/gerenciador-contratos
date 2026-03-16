import time
from datetime import date, timedelta

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import UserPassesTestMixin
from django.contrib.auth.models import User, Group
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.db.models import Avg, Case, F, IntegerField, OuterRef, Q, Subquery, Sum, Value, When
from django.db.models.functions import Coalesce
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.http import JsonResponse
from django.urls import reverse_lazy
from django.utils import timezone
from django.utils.timezone import now
from django.views import View
from django.views.decorators.http import require_POST
from django.views.generic import ListView, TemplateView
from django.views.generic.detail import DetailView
from django.views.generic.edit import FormMixin

from .forms import FormCadastrarVendedor
from .models import Vendedor, Lead, SessaoLigacao, TentativaLigacao, ScoreLead
from contratos.models import Contrato, ClaroEndereco
from .utils import *


@login_required
def dashboard_redirect(request):
    user = request.user

    if user.groups.filter(name="Admin").exists():
        return redirect("core:dashboard_admin")
    
    if user.groups.filter(name="Vendedor").exists():
        return redirect("core:dashboard_vendedor")
    
    return redirect("login")


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

    return render(request, "partials/select_bairro.html", {
        "lista_bairros": bairros,
    })


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
        return Lead.objects.filter(vendedor__usuario=usuario).only("id", "contrato_id", "vendedor")

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)

        leads = contexto["leads"]
        contratos_ids = [lead.contrato_id for lead in leads]
        contratos = Contrato.objects.filter(contrato__in=contratos_ids)
        contexto["contratos_map"] = {c.contrato: c for c in contratos}

        return contexto


class DetalhesLead(DetailView):
    model = Contrato
    template_name = "detalhes_lead.html"
    context_object_name = "contrato"

    def get_object(self):
        numero_contrato = self.kwargs["pk"]
        return get_object_or_404(Contrato, contrato=numero_contrato)

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)

        lead = get_object_or_404(
            Lead, 
            vendedor__usuario=self.request.user, 
            contrato_id=self.object.contrato
        )

        contexto["lead"] = lead

        return contexto
    
    def post(self, request, *args, **kwargs):
        contrato = self.get_object()

        lead = get_object_or_404(
            Lead, 
            vendedor__usuario=request.user, 
            contrato_id=contrato.contrato
        )

        if not lead.resolvido:
            lead.resolvido = True
            lead.resolvido_em = timezone.now()
            lead.save(update_fields=["resolvido", "resolvido_em"])
        return redirect("core:detalhes_lead", pk=contrato.contrato)


class ListaContratos(ListView):
    model = Contrato
    template_name = "lista_contratos.html"
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
            return render(self.request, "partials/contratos.html", context)
        return super().render_to_response(context, **response_kwargs)


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
            return render(self.request, "partials/arruamento.html", context)
        return super().render_to_response(context, **response_kwargs)
    
    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)

        contexto["total_contratos"] = Contrato.objects.using("contratos").all().count()

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


class ListaLeadsBairro(ListView):
    model = Contrato
    template_name = "leads_endereco.html"
    context_object_name = "contratos"
    paginate_by = 50

    def get_cidade(self):
        return self.request.GET.get("cidade")

    def get_bairro(self):
        return self.request.GET.get("bairro")

    def get_rua(self):
        return self.request.GET.get("rua")
    
    def score_prod(self):
        return getattr(settings, "PROD", False)
    
    def normalizar_rua(self, texto):
        if not texto:
            return texto

        mapa = {
            "AV ": "AVENIDA ",
            "R ": "RUA ",
            "DR ": "DOUTOR ",
            "PROF ": "PROFESSOR ",
            "ALF ": "ALFERES ",
        }

        texto = texto.upper().strip()

        for abrev, completo in mapa.items():
            if texto.startswith(abrev):
                texto = texto.replace(abrev, completo, 1)

        return texto

    def get_queryset(self):
        queryset = Contrato.objects.using("contratos").filter(
            cidade=self.get_cidade(),
            bairro=self.get_bairro(),
        )

        rua = self.get_rua()

        rua = self.get_rua()
        if rua:
            rua_original = rua.strip()
            rua_normalizada = self.normalizar_rua(rua_original)

            palavras = [
                p for p in rua_normalizada.split()
                if len(p) > 2
            ]

            filtro = (
                Q(endereco__icontains=rua_original) |
                Q(endereco__icontains=rua_normalizada)
            )

            for palavra in palavras:
                filtro |= Q(endereco__icontains=palavra)

            queryset = queryset.filter(filtro)

        if self.score_prod():
            score_subquery = ScoreLead.objects.filter(
                contrato_id=OuterRef("contrato")
            ).values("score_total")[:1]

            queryset = queryset.annotate(
                score_total=Coalesce(
                    Subquery(score_subquery, output_field=IntegerField()),
                    Value(0)
                )
            ).order_by("-score_total", "endereco")
        else:
            queryset = queryset.order_by("endereco")

        return queryset

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        cidade = self.get_cidade()
        bairro = self.get_bairro()

        contexto["cidade"] = cidade
        contexto["bairro"] = bairro
        contexto["rua_atual"] = self.get_rua()

        contexto["ruas"] = (
            ClaroEndereco.objects.using("contratos")
            .filter(
                cidade=cidade,
                bairro=bairro
            )
            .values_list("logradouro", flat=True)
            .distinct()
            .order_by("logradouro")
        )

        contratos = contexto["page_obj"].object_list
        contratos_ids_pagina = [c.contrato for c in contratos]
        contratos_atribuidos = set(
            Lead.objects.filter(contrato_id__in=contratos_ids_pagina)
            .values_list("contrato_id", flat=True)
        )

        for c in contratos:
            c.ja_atribuido = c.contrato in contratos_atribuidos

        contexto["total_contratos"] = contexto["page_obj"].paginator.count
        contexto["vendedores"] = Vendedor.objects.all()
        
        if not self.score_prod():
            contratos_page = list(contexto["page_obj"].object_list)
            contratos_ids = [contrato.contrato for contrato in contratos_page]

            scores = ScoreLead.objects.filter(
                contrato_id__in=contratos_ids
            ).values("contrato_id", "score_total")

            scores_map = {
                item["contrato_id"]: item["score_total"]
                for item in scores
            }

            for contrato in contratos_page:
                contrato.score_total = scores_map.get(contrato.contrato, 0)

            contratos_page.sort(
                key=lambda contrato: (-contrato.score_total, contrato.endereco or "")
            )

            contexto["contratos"] = contratos_page
            contexto["page_obj"].object_list = contratos_page
        else:
            contexto["contratos"] = contexto["page_obj"].object_list

        return contexto


@require_POST
def atribuir_leads_massa(request):
    vendedor_id = request.POST.get("vendedor")
    contratos = request.POST.getlist("contratos")

    if not vendedor_id:
        messages.error(request, "Selecione um vendedor.")
        return redirect(request.META.get("HTTP_REFERER", "core:lista_leads"))

    if not contratos:
        messages.error(request, "Selecione pelo menos um contrato.")
        return redirect(request.META.get("HTTP_REFERER", "core:lista_leads"))

    vendedor = Vendedor.objects.get(id=vendedor_id)

    contratos_ja_atribuidos = set(
        Lead.objects.filter(contrato_id__in=contratos).values_list("contrato_id", flat=True)
    )

    leads_para_criar = [
        Lead(contrato_id=contrato, vendedor=vendedor)
        for contrato in contratos
        if str(contrato) not in {str(c) for c in contratos_ja_atribuidos}
    ]

    if leads_para_criar:
        Lead.objects.bulk_create(leads_para_criar)

    quantidade_criada = len(leads_para_criar)
    quantidade_ignoradas = len(contratos) - quantidade_criada

    if quantidade_criada:
        messages.success(
            request,
            f"{quantidade_criada} lead(s) atribuída(s) com sucesso."
        )

    if quantidade_ignoradas:
        messages.warning(
            request,
            f"{quantidade_ignoradas} contrato(s) já estavam atribuídos e foram ignorados."
        )

    return redirect(request.META.get("HTTP_REFERER", "core:lista_leads"))


class DetalhesContrato(DetailView):
    model = Contrato
    template_name = "detalhes_contrato.html"
    context_object_name = "contrato"

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["vendedores"] = Vendedor.objects.all().order_by("usuario__username")
        lead = Lead.objects.filter(contrato_id=self.object.contrato).first()

        contexto["lead"] = lead
        contexto["lead_atribuida"] = lead is not None
        
        return contexto


class AtribuirLead(View):
    def post(self, request):
        vendedor_id = request.POST.get("vendedor")
        contrato_id = request.POST.get("contrato")

        vendedor = Vendedor.objects.get(pk=vendedor_id)

        Lead.objects.create(
            vendedor=vendedor,
            contrato_id=contrato_id
        )

        return redirect(request.META.get("HTTP_REFERER"))



def contatar_cliente(request, contrato_id):
    contrato = Contrato.objects.using("contratos").get(contrato=contrato_id)
    vendedor = Vendedor.objects.get(usuario=request.user)

    ramal = 202

    telefones = [
        "12996485077"
    ]

    telefones = [t for t in telefones if t]

    if not telefones:
        return JsonResponse({"erro": "Nenhum telefone disponível"})

    sessao = SessaoLigacao.objects.create(
        contrato_id=contrato_id,
        vendedor=vendedor
    )

    telefone = telefones[0]

    tentativa = TentativaLigacao.objects.create(
        sessao=sessao,
        numero_discado=telefone,
        ordem=1,
        ramal=ramal,
        status="calling"
    )

    resposta = criar_chamada(ramal, telefone)

    tentativa.id_ligacao_pabx = resposta.get("id", None)
    tentativa.save()

    return JsonResponse({"status": "calling"})

