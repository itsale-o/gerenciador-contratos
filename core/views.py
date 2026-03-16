import time
from datetime import date, timedelta

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import UserPassesTestMixin
from django.contrib.auth.models import User, Group
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.db.models import Avg, Case, F, IntegerField, OuterRef, Q, Subquery, Sum, Value, When, Count
from django.db.models.functions import Coalesce
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.http import JsonResponse
from django.urls import reverse_lazy
from django.utils import timezone
from django.utils.timezone import now
from django.views import View
from django.utils.decorators import method_decorator
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
        vendedores_ativos = Vendedor.objects.filter(status="ativo").count()

        leads_com_contato = Lead.objects.filter(
            contato_realizado=True
        ).count()

        leads_sem_contato = Lead.objects.filter(
            contato_realizado=False
        ).count()

        leads_com_venda = Lead.objects.filter(
            status_contato="venda"
        ).count()

        leads_sem_venda = leads_com_contato - leads_com_venda

        if total_leads_distribuidos > 0:
            taxa_contato = round((leads_com_contato / total_leads_distribuidos) * 100, 1)
            taxa_venda = round((leads_com_venda / total_leads_distribuidos) * 100, 1)
        else:
            taxa_contato = 0
            taxa_venda = 0

        distribuicao_leads = (
            Lead.objects
            .values("vendedor__usuario__username")
            .annotate(
                total=Count("id"),
                com_contato=Count(
                    Case(When(contato_realizado=True, then=1), output_field=IntegerField())
                ),
                com_venda=Count(
                    Case(When(status_contato="venda", then=1), output_field=IntegerField())
                ),
                sem_contato=Count(
                    Case(When(contato_realizado=False, then=1), output_field=IntegerField())
                ),
            )
            .order_by("-total")
        )

        leads_mes = Lead.objects.filter(
            data_atribuicao__date__gte=inicio_mes
        )
        
        vendas_mes = leads_mes.filter(
            status_contato="venda"
        ).count()

        sessoes_ligacao_mes = SessaoLigacao.objects.filter(
            criado_em__date__gte=inicio_mes
        ).count()

        tentativas_ligacao_mes = TentativaLigacao.objects.filter(
            criado_em__date__gte=inicio_mes
        ).count()

        leads_pendentes_retorno = Lead.objects.filter(
            proximo_contato__isnull=False,
            resolvido=False
        ).count()

        retornos_urgentes = Lead.objects.filter(
            proximo_contato__lte=now(),
            resolvido=False
        ).count()

        leads_nao_venda = Lead.objects.filter(
            contato_realizado=True
        ).exclude(status_contato__in=["venda", "nao_atendeu", "ligar_mais_tarde"])

        leads_caro = Lead.objects.filter(status_contato="caro")

        leads_sem_interesse = Lead.objects.filter(
            status_contato__in=["sem_interesse", "nao_virou_venda"]
        )

        contexto.update({
            "leads_nao_venda": leads_nao_venda.count(),
            "leads_caro": leads_caro.count(),
            "leads_sem_interesse": leads_sem_interesse.count(),
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
            "leads_com_contato": leads_com_contato,
            "leads_sem_contato": leads_sem_contato,
            "leads_com_venda": leads_com_venda,
            "leads_sem_venda": leads_sem_venda,
            "taxa_contato": taxa_contato,
            "taxa_venda": taxa_venda,
            "distribuicao_leads": distribuicao_leads,
            "vendas_mes": vendas_mes,
            "sessoes_ligacao_mes": sessoes_ligacao_mes,
            "tentativas_ligacao_mes": tentativas_ligacao_mes,
            "leads_pendentes_retorno": leads_pendentes_retorno,
            "retornos_urgentes": retornos_urgentes,
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
        usuario = self.request.user
        
        try:
            vendedor = Vendedor.objects.get(usuario=usuario)
        except Vendedor.DoesNotExist:
            contexto.update({
                "total_leads": 0,
                "leads_com_vendas": 0,
                "leads_pendentes_retorno": 0,
                "leads_sem_resposta": 0,
                "leads_respondidos": 0,
                "taxa_resposta": 0,
                "taxa_conversao": 0,
                "retornos_urgentes": [],
                "retornos_hoje": [],
                "proximos_retornos": [],
                "leads_recentes": [],
                "vendas_mes": 0,
                "sessoes_ligacao": 0,
                "tentativas_ligacao": 0,
            })
            return contexto
        
        hoje = now()
        hoje_date = hoje.date()
        inicio_mes = date(hoje_date.year, hoje_date.month, 1)

        leads = Lead.objects.filter(vendedor=vendedor).select_related('vendedor')
        total_leads = leads.count()

        leads_com_vendas = leads.filter(
            status_contato="venda"
        ).count()
        
        leads_respondidos = leads.filter(
            contato_realizado=True
        ).count()
        
        leads_sem_resposta = leads.filter(
            contato_realizado=False
        ).count()

        leads_pendentes_retorno = leads.filter(
            proximo_contato__isnull=False,
            resolvido=False
        ).count()
        
        retornos_urgentes = leads.filter(
            proximo_contato__lte=hoje,
            resolvido=False
        ).order_by("proximo_contato")[:5]
        
        retornos_hoje = leads.filter(
            proximo_contato__date=hoje_date,
            resolvido=False
        ).order_by("proximo_contato")[:5]
        
        proxima_semana = hoje_date + timedelta(days=7)
        proximos_retornos = leads.filter(
            proximo_contato__date__gt=hoje_date,
            proximo_contato__date__lte=proxima_semana,
            resolvido=False
        ).order_by("proximo_contato")[:10]
        
        leads_recentes = leads.filter(
            Q(contato_realizado=True) |
            Q(observacao__isnull=False) |
            Q(proximo_contato__isnull=False)
        ).order_by("-id")[:5]
        
        if total_leads > 0:
            taxa_resposta = round((leads_respondidos / total_leads) * 100, 1)
            taxa_conversao = round((leads_com_vendas / total_leads) * 100, 1)
        else:
            taxa_resposta = 0
            taxa_conversao = 0
        
        leads_mes = leads.filter(
            data_atribuicao__date__gte=inicio_mes
        )
        vendas_mes = leads_mes.filter(
            status_contato="venda"
        ).count()
        
        sessoes_ligacao = SessaoLigacao.objects.filter(
            vendedor=vendedor,
            criado_em__date__gte=inicio_mes
        ).count()
        
        tentativas_ligacao = TentativaLigacao.objects.filter(
            sessao__vendedor=vendedor,
            criado_em__date__gte=inicio_mes
        ).count()

        leads_nao_venda = leads.filter(
            contato_realizado=True
        ).exclude(status_contato="venda")

        leads_caro = leads.filter(status_contato="caro")

        leads_sem_interesse = leads.filter(
            status_contato__in=["sem_interesse", "nao_virou_venda"]
        )

        contexto.update({
            "leads_nao_venda": leads_nao_venda.count(),
            "leads_caro": leads_caro.count(),
            "leads_sem_interesse": leads_sem_interesse.count(),
            "total_leads": total_leads,
            "leads_com_vendas": leads_com_vendas,
            "leads_pendentes_retorno": leads_pendentes_retorno,
            "leads_sem_resposta": leads_sem_resposta,
            "leads_respondidos": leads_respondidos,
            "taxa_resposta": taxa_resposta,
            "taxa_conversao": taxa_conversao,
            "retornos_urgentes": retornos_urgentes,
            "retornos_hoje": retornos_hoje,
            "proximos_retornos": proximos_retornos,
            "leads_recentes": leads_recentes,
            "vendas_mes": vendas_mes,
            "sessoes_ligacao": sessoes_ligacao,
            "tentativas_ligacao": tentativas_ligacao,
        })
        
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
        status = self.request.GET.get("status", "todos")

        queryset = Lead.objects.filter(vendedor__usuario=usuario).select_related("vendedor")

        if status == "novos":
            queryset = queryset.filter(contato_realizado=False)
        elif status == "contatados":
            queryset = queryset.filter(contato_realizado=True, status_contato__isnull=True)
        elif status == "vendas":
            queryset = queryset.filter(status_contato="venda")
        elif status == "nao_venda":
            queryset = queryset.filter(contato_realizado=True).exclude(status_contato__in=["venda", "nao_atendeu", "ligar_mais_tarde"])
        elif status == "sem_interesse":
            queryset = queryset.filter(status_contato="sem_interesse")

        return queryset.order_by("-data_atribuicao")

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
        contratos = request.POST.get("contratos")  # string "804703,804368"

        vendedor = Vendedor.objects.get(pk=vendedor_id)

        lista_contratos = contratos.split(",")

        for contrato_id in lista_contratos:
            Lead.objects.get_or_create(
                vendedor=vendedor,
                contrato_id=contrato_id
            )

        return redirect(request.META.get("HTTP_REFERER"))

@require_POST
@login_required
def salvar_status_lead(request, contrato_id):

    vendedor = Vendedor.objects.get(usuario=request.user)

    lead = get_object_or_404(
        Lead,
        vendedor=vendedor,
        contrato_id=contrato_id
    )

    status = request.POST.get("status")
    observacao = request.POST.get("observacao")
    proximo = request.POST.get("proximo_contato")

    if status:
        lead.status_contato = status

    # Marca por padrão como contato realizado quando há status definitivo
    if status in ["venda", "caro", "sem_interesse", "nao_virou_venda", "numero_invalido", "nao_atendeu"]:
        lead.contato_realizado = True

    # Considera resolvido para status não em atendimento
    if status in ["venda", "caro", "sem_interesse", "nao_virou_venda", "numero_invalido"]:
        lead.resolvido = True

    if observacao:
        lead.observacao = observacao
    elif status in ["caro", "sem_interesse", "nao_virou_venda"]:
        lead.observacao = {
            "caro": "Cliente considerou caro",
            "sem_interesse": "Cliente sem interesse",
            "nao_virou_venda": "Lead não virou venda"
        }.get(status, lead.observacao)

    if proximo:
        lead.proximo_contato = proximo

    lead.save()

    return JsonResponse({"ok": True})


def contatar_cliente(request, contrato_id):
    contrato = Contrato.objects.using("contratos").get(contrato=contrato_id)
    vendedor = Vendedor.objects.get(usuario=request.user)

    lead = Lead.objects.get(
    vendedor=vendedor,
    contrato_id=contrato_id
    )

    lead.contato_realizado = True
    lead.save(update_fields=["contato_realizado"])

    ramal = 202

    telefones = [
        "12996485077",
        "37988446185"
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
        status="calling"
    )

    resposta = criar_chamada(ramal, telefone)

    tentativa.id_ligacao = resposta.get("id")
    tentativa.save()

    return JsonResponse({"status": "calling"})

class DashboardDrilldownMixin:

    def dispatch(self, request, *args, **kwargs):
        if not (request.user.groups.filter(name="Admin").exists() or request.user.groups.filter(name="Vendedor").exists()):
            return JsonResponse(
                {"status": "error", "message": "Acesso negado"},
                status=403,
            )
        return super().dispatch(request, *args, **kwargs)


class DashboardLeadsDistribuicaoAPI(LoginRequiredMixin, DashboardDrilldownMixin, View):
    
    def get(self, request):
        try:
            distribuicao = Lead.objects
            if request.user.groups.filter(name="Vendedor").exists():
                vendedor = Vendedor.objects.get(usuario=request.user)
                distribuicao = Lead.objects.filter(vendedor=vendedor)

            distribuicao = (
                distribuicao
                .values("vendedor__usuario__username", "vendedor__id")
                .annotate(
                    total=Count("id"),
                    com_contato=Count(
                        Case(When(contato_realizado=True, then=1), output_field=IntegerField())
                    ),
                    com_venda=Count(
                        Case(When(status_contato="venda", then=1), output_field=IntegerField())
                    ),
                    sem_contato=Count(
                        Case(When(contato_realizado=False, then=1), output_field=IntegerField())
                    ),
                )
                .order_by("-total")
            )
            
            dados = []
            for item in distribuicao:
                vendedor_id = item["vendedor__id"]
                leads_vendedor = Lead.objects.filter(vendedor_id=vendedor_id)
                contratos_ids = [lead.contrato_id for lead in leads_vendedor]
                
                contratos = (
                    Contrato.objects
                    .filter(contrato__in=contratos_ids)
                    .annotate(cliente=F("nome"))
                    .values("contrato", "cliente", "valor", "status")
                )[:10]
                
                dados.append({
                    "vendedor": item["vendedor__usuario__username"],
                    "total_leads": item["total"],
                    "com_contato": item["com_contato"],
                    "com_venda": item["com_venda"],
                    "sem_contato": item["sem_contato"],
                    "contratos": list(contratos),
                })
            
            return JsonResponse({
                "status": "success",
                "data": dados,
            })
        except Exception as e:
            return JsonResponse({
                "status": "error",
                "message": str(e),
            }, status=500)


class DashboardVendasMesAPI(LoginRequiredMixin, DashboardDrilldownMixin, View):
    
    def get(self, request):
        try:
            hoje = now().date()
            inicio_mes = date(hoje.year, hoje.month, 1)
            
            lead_query = Lead.objects.filter(
                data_atribuicao__date__gte=inicio_mes,
                status_contato="venda"
            )

            if request.user.groups.filter(name="Vendedor").exists():
                vendedor = Vendedor.objects.get(usuario=request.user)
                lead_query = lead_query.filter(vendedor=vendedor)

            vendas_mes = (
                lead_query
                .values("vendedor__usuario__username", "vendedor__id")
                .annotate(total_vendas=Count("id"))
                .order_by("-total_vendas")
            )
            
            dados = []
            for venda in vendas_mes:
                vendedor_id = venda["vendedor__id"]
                leads_venda = Lead.objects.filter(
                    vendedor_id=vendedor_id,
                    data_atribuicao__date__gte=inicio_mes,
                    status_contato="venda"
                )
                
                contratos_ids = [lead.contrato_id for lead in leads_venda]
                contratos = (
                    Contrato.objects
                    .filter(contrato__in=contratos_ids)
                    .annotate(cliente=F("nome"))
                    .values("contrato", "cliente", "valor", "status")
                )
                
                dados.append({
                    "vendedor": venda["vendedor__usuario__username"],
                    "total_vendas": venda["total_vendas"],
                    "contratos": list(contratos),
                })
            
            return JsonResponse({
                "status": "success",
                "data": dados,
            })
        except Exception as e:
            return JsonResponse({
                "status": "error",
                "message": str(e),
            }, status=500)


class DashboardRetornosUrgentesAPI(LoginRequiredMixin, DashboardDrilldownMixin, View):
    
    def get(self, request):
        try:
            agora = now()
            
            lead_query = Lead.objects.filter(
                proximo_contato__lte=agora,
                resolvido=False
            )

            if request.user.groups.filter(name="Vendedor").exists():
                vendedor = Vendedor.objects.get(usuario=request.user)
                lead_query = lead_query.filter(vendedor=vendedor)

            retornos = (
                lead_query
                .values("vendedor__usuario__username", "vendedor__id")
                .annotate(total_retornos=Count("id"))
                .order_by("-total_retornos")
            )
            
            dados = []
            for retorno in retornos:
                vendedor_id = retorno["vendedor__id"]
                leads_retorno = Lead.objects.filter(
                    vendedor_id=vendedor_id,
                    proximo_contato__lte=agora,
                    resolvido=False
                ).order_by("proximo_contato")
                
                contratos_info = []
                for lead in leads_retorno[:10]:
                    contrato = Contrato.objects.filter(contrato=lead.contrato_id).first()
                    if contrato:
                        contratos_info.append({
                            "contrato": contrato.contrato,
                            "cliente": contrato.nome,
                            "proximo_contato": lead.proximo_contato.strftime("%d/%m/%Y %H:%M"),
                            "observacao": lead.observacao or "Sem observações",
                        })
                
                dados.append({
                    "vendedor": retorno["vendedor__usuario__username"],
                    "total_retornos": retorno["total_retornos"],
                    "contratos": contratos_info,
                })
            
            return JsonResponse({
                "status": "success",
                "data": dados,
            })
        except Exception as e:
            return JsonResponse({
                "status": "error",
                "message": str(e),
            }, status=500)


class DashboardSessoesLigacaoAPI(LoginRequiredMixin, DashboardDrilldownMixin, View):
    """API para obter sessões de ligação por vendedor"""

    def get(self, request):
        try:
            sessoes = SessaoLigacao.objects

            if request.user.groups.filter(name="Vendedor").exists():
                vendedor = Vendedor.objects.get(usuario=request.user)
                sessoes = sessoes.filter(vendedor=vendedor)

            sessoes = (
                sessoes
                .values("vendedor__usuario__username", "vendedor__id")
                .annotate(total_sessoes=Count("id"))
                .order_by("-total_sessoes")
            )

            dados = []
            for item in sessoes:
                vendedor_id = item["vendedor__id"]
                sessoes_leads = SessaoLigacao.objects.filter(vendedor_id=vendedor_id).order_by("-criado_em")[:10]

                contratos_info = []
                for sessao in sessoes_leads:
                    contrato = Contrato.objects.filter(contrato=sessao.contrato_id).first()
                    if contrato:
                        contratos_info.append({
                            "contrato": contrato.contrato,
                            "cliente": contrato.nome,
                            "valor": contrato.valor,
                            "status": contrato.status,
                            "proximo_contato": sessao.criado_em.strftime("%d/%m/%Y %H:%M"),
                        })

                dados.append({
                    "vendedor": item["vendedor__usuario__username"],
                    "total_sessoes": item["total_sessoes"],
                    "contratos": contratos_info
                })

            return JsonResponse({"status": "success", "data": dados})
        except Exception as e:
            return JsonResponse({"status": "error", "message": str(e)}, status=500)


class DashboardTentativasLigacaoAPI(LoginRequiredMixin, DashboardDrilldownMixin, View):
    """API para obter tentativas de ligação por vendedor"""

    def get(self, request):
        try:
            tentativas = TentativaLigacao.objects.select_related("sessao__vendedor")

            if request.user.groups.filter(name="Vendedor").exists():
                vendedor = Vendedor.objects.get(usuario=request.user)
                tentativas = tentativas.filter(sessao__vendedor=vendedor)

            tentativas_agg = (
                tentativas
                .values("sessao__vendedor__usuario__username", "sessao__vendedor__id")
                .annotate(total_tentativas=Count("id"))
                .order_by("-total_tentativas")
            )

            dados = []
            for item in tentativas_agg:
                vendedor_id = item["sessao__vendedor__id"]
                tentativas_vendedor = TentativaLigacao.objects.filter(sessao__vendedor_id=vendedor_id).order_by("-criado_em")[:10]

                contratos_info = []
                for tentativa in tentativas_vendedor:
                    contrato_obj = Contrato.objects.filter(contrato=tentativa.sessao.contrato_id).first()
                    if contrato_obj:
                        contratos_info.append({
                            "contrato": contrato_obj.contrato,
                            "cliente": contrato_obj.nome,
                            "valor": contrato_obj.valor,
                            "status": contrato_obj.status,
                            "proximo_contato": tentativa.sessao.criado_em.strftime("%d/%m/%Y %H:%M"),
                        })

                dados.append({
                    "vendedor": item["sessao__vendedor__usuario__username"],
                    "total_tentativas": item["total_tentativas"],
                    "contratos": contratos_info
                })

            return JsonResponse({"status": "success", "data": dados})
        except Exception as e:
            return JsonResponse({"status": "error", "message": str(e)}, status=500)


class DashboardLeadsSemContatoAPI(LoginRequiredMixin, DashboardDrilldownMixin, View):
    
    def get(self, request):
        try:
            sem_contato = (
                Lead.objects
                .filter(contato_realizado=False)
                .values("vendedor__usuario__username", "vendedor__id")
                .annotate(total_sem_contato=Count("id"))
                .order_by("-total_sem_contato")
            )
            
            dados = []
            for item in sem_contato:
                vendedor_id = item["vendedor__id"]
                leads_sem_contato = Lead.objects.filter(
                    vendedor_id=vendedor_id,
                    contato_realizado=False
                )
                
                contratos_ids = [lead.contrato_id for lead in leads_sem_contato]
                contratos = (
                    Contrato.objects
                    .filter(contrato__in=contratos_ids)
                    .annotate(cliente=F("nome"))
                    .values("contrato", "cliente", "valor", "status")
                )[:10]
                
                dados.append({
                    "vendedor": item["vendedor__usuario__username"],
                    "total_sem_contato": item["total_sem_contato"],
                    "contratos": list(contratos),
                })
            
            return JsonResponse({
                "status": "success",
                "data": dados,
            })
        except Exception as e:
            return JsonResponse({
                "status": "error",
                "message": str(e),
            }, status=500)


class DashboardLeadsComContatoAPI(LoginRequiredMixin, DashboardDrilldownMixin, View):
    
    def get(self, request):
        try:
            com_contato = (
                Lead.objects
                .filter(contato_realizado=True)
                .values("vendedor__usuario__username", "vendedor__id")
                .annotate(total_com_contato=Count("id"))
                .order_by("-total_com_contato")
            )
            
            dados = []
            for item in com_contato:
                vendedor_id = item["vendedor__id"]
                leads_com_contato = Lead.objects.filter(
                    vendedor_id=vendedor_id,
                    contato_realizado=True
                )
                
                contratos_ids = [lead.contrato_id for lead in leads_com_contato]
                contratos = (
                    Contrato.objects
                    .filter(contrato__in=contratos_ids)
                    .annotate(cliente=F("nome"))
                    .values("contrato", "cliente", "valor", "status")
                )[:10]
                
                dados.append({
                    "vendedor": item["vendedor__usuario__username"],
                    "total_com_contato": item["total_com_contato"],
                    "contratos": list(contratos),
                })
            
            return JsonResponse({
                "status": "success",
                "data": dados,
            })
        except Exception as e:
            return JsonResponse({
                "status": "error",
                "message": str(e),
            }, status=500)


class DashboardLeadsSemVendaAPI(LoginRequiredMixin, DashboardDrilldownMixin, View):
    """API para obter detalhes de leads sem venda por vendedor"""
    
    def get(self, request):
        try:
            sem_venda = (
                Lead.objects
                .filter(
                    contato_realizado=True,
                    status_contato__isnull=True
                )
                .values("vendedor__usuario__username", "vendedor__id")
                .annotate(total_sem_venda=Count("id"))
                .order_by("-total_sem_venda")
            )
            
            dados = []
            for item in sem_venda:
                vendedor_id = item["vendedor__id"]
                leads_sem_venda = Lead.objects.filter(
                    vendedor_id=vendedor_id,
                    contato_realizado=True,
                    status_contato__isnull=True
                )
                
                contratos_ids = [lead.contrato_id for lead in leads_sem_venda]
                contratos = (
                    Contrato.objects
                    .filter(contrato__in=contratos_ids)
                    .annotate(cliente=F("nome"))
                    .values("contrato", "cliente", "valor", "status")
                )[:10]
                
                dados.append({
                    "vendedor": item["vendedor__usuario__username"],
                    "total_sem_venda": item["total_sem_venda"],
                    "contratos": list(contratos),
                })
            
            return JsonResponse({
                "status": "success",
                "data": dados,
            })
        except Exception as e:
            return JsonResponse({
                "status": "error",
                "message": str(e),
            }, status=500)


class DashboardLeadsNaoVendaAPI(LoginRequiredMixin, DashboardDrilldownMixin, View):
    """API para obter leads que não viraram venda"""

    def get(self, request):
        try:
            leads = Lead.objects.filter(contato_realizado=True).exclude(status_contato__in=["venda", "nao_atendeu", "ligar_mais_tarde"])

            if request.user.groups.filter(name="Vendedor").exists():
                vendedor = Vendedor.objects.get(usuario=request.user)
                leads = leads.filter(vendedor=vendedor)

            nao_venda = (
                leads
                .values("vendedor__usuario__username", "vendedor__id")
                .annotate(total_nao_venda=Count("id"))
                .order_by("-total_nao_venda")
            )

            dados = []
            for item in nao_venda:
                vendedor_id = item["vendedor__id"]
                leads_vendedor = Lead.objects.filter(
                    vendedor_id=vendedor_id,
                    contato_realizado=True
                ).exclude(status_contato__in=["venda", "nao_atendeu", "ligar_mais_tarde"])

                contratos_info = []
                for lead in leads_vendedor[:10]:
                    contrato = Contrato.objects.filter(contrato=lead.contrato_id).first()
                    if contrato:
                        contratos_info.append({
                            "contrato": contrato.contrato,
                            "cliente": contrato.nome,
                            "valor": contrato.valor,
                            "status": contrato.status,
                            "status_contato": lead.status_contato,
                        })

                dados.append({
                    "vendedor": item["vendedor__usuario__username"],
                    "total_nao_venda": item["total_nao_venda"],
                    "contratos": contratos_info,
                })

            return JsonResponse({
                "status": "success",
                "data": dados,
            })
        except Exception as e:
            return JsonResponse({
                "status": "error",
                "message": str(e),
            }, status=500)


class DashboardLeadsCaroAPI(LoginRequiredMixin, DashboardDrilldownMixin, View):

    def get(self, request):
        try:
            leads = Lead.objects.filter(status_contato="caro")

            if request.user.groups.filter(name="Vendedor").exists():
                vendedor = Vendedor.objects.get(usuario=request.user)
                leads = leads.filter(vendedor=vendedor)

            leads_caro = (
                leads
                .values("vendedor__usuario__username", "vendedor__id")
                .annotate(total_caro=Count("id"))
                .order_by("-total_caro")
            )

            dados = []
            for item in leads_caro:
                vendedor_id = item["vendedor__id"]
                leads_vendedor = Lead.objects.filter(
                    vendedor_id=vendedor_id,
                    status_contato="caro"
                )

                contratos_info = []
                for lead in leads_vendedor[:10]:
                    contrato = Contrato.objects.filter(contrato=lead.contrato_id).first()
                    if contrato:
                        contratos_info.append({
                            "contrato": contrato.contrato,
                            "cliente": contrato.nome,
                            "valor": contrato.valor,
                            "status": contrato.status,
                            "status_contato": lead.status_contato,
                        })

                dados.append({
                    "vendedor": item["vendedor__usuario__username"],
                    "total_caro": item["total_caro"],
                    "contratos": contratos_info,
                })

            return JsonResponse({"status": "success", "data": dados})
        except Exception as e:
            return JsonResponse({"status": "error", "message": str(e)}, status=500)


class DashboardLeadsSemInteresseAPI(LoginRequiredMixin, DashboardDrilldownMixin, View):
    """API para obter leads que não tem interesse"""

    def get(self, request):
        try:
            leads = Lead.objects.filter(status_contato="sem_interesse")

            if request.user.groups.filter(name="Vendedor").exists():
                vendedor = Vendedor.objects.get(usuario=request.user)
                leads = leads.filter(vendedor=vendedor)

            leads_sem_interesse = (
                leads
                .values("vendedor__usuario__username", "vendedor__id")
                .annotate(total_sem_interesse=Count("id"))
                .order_by("-total_sem_interesse")
            )

            dados = []
            for item in leads_sem_interesse:
                vendedor_id = item["vendedor__id"]
                leads_vendedor = Lead.objects.filter(
                    vendedor_id=vendedor_id,
                    status_contato="sem_interesse"
                )

                contratos_info = []
                for lead in leads_vendedor[:10]:
                    contrato = Contrato.objects.filter(contrato=lead.contrato_id).first()
                    if contrato:
                        contratos_info.append({
                            "contrato": contrato.contrato,
                            "cliente": contrato.nome,
                            "valor": contrato.valor,
                            "status": contrato.status,
                            "status_contato": lead.status_contato,
                        })

                dados.append({
                    "vendedor": item["vendedor__usuario__username"],
                    "total_sem_interesse": item["total_sem_interesse"],
                    "contratos": contratos_info,
                })

            return JsonResponse({"status": "success", "data": dados})
        except Exception as e:
            return JsonResponse({"status": "error", "message": str(e)}, status=500)


@method_decorator(require_POST, name='dispatch')
class DashboardReatribuirLeadAPI(LoginRequiredMixin, DashboardDrilldownMixin, View):
    """API para reatribuir lead a outro vendedor"""

    def post(self, request):
        if not request.user.groups.filter(name="Admin").exists():
            return JsonResponse({"status": "error", "message": "Acesso negado."}, status=403)

        contrato_id = request.POST.get("contrato")
        vendedor_id = request.POST.get("vendedor_id")
        observacao = request.POST.get("observacao", "").strip()

        if not contrato_id or not vendedor_id:
            return JsonResponse({"status": "error", "message": "Dados incompletos."}, status=400)

        try:
            lead = Lead.objects.filter(contrato_id=contrato_id).first()
            vendedor_destino = Vendedor.objects.get(id=vendedor_id)

            if not lead:
                return JsonResponse({"status": "error", "message": "Lead não encontrado."}, status=404)

            if lead.status_contato in ["venda", "nao_atendeu", "ligar_mais_tarde"]:
                return JsonResponse({"status": "error", "message": "Este lead não pode ser reatribuído neste momento."}, status=400)

            observacao_final = f"Reatribuído para {vendedor_destino.usuario.username} por {request.user.username}"
            if observacao:
                observacao_final += f" - Motivo: {observacao}"

            if lead.observacao:
                lead.observacao = f"{lead.observacao} | {observacao_final}"
            else:
                lead.observacao = observacao_final

            lead.vendedor = vendedor_destino
            lead.contato_realizado = False
            lead.status_contato = None
            lead.resolvido = False
            lead.resolvido_em = None
            lead.save(update_fields=["vendedor", "observacao", "contato_realizado", "status_contato", "resolvido", "resolvido_em"])

            return JsonResponse({"status": "success", "message": "Lead reatribuído com sucesso."})
        except Vendedor.DoesNotExist:
            return JsonResponse({"status": "error", "message": "Vendedor destino inválido."}, status=404)
        except Exception as e:
            return JsonResponse({"status": "error", "message": str(e)}, status=500)


class DashboardVendedoresAtivosAPI(LoginRequiredMixin, DashboardDrilldownMixin, View):
    """API para obter lista de vendedores ativos"""

    def get(self, request):
        try:
            vendedores = (
                Vendedor.objects
                .filter(status="ativo")
                .annotate(total_leads=Count("leads"))
                .select_related("usuario")
                .order_by("usuario__username")
            )

            dados = [
                {
                    "id": v.id,
                    "vendedor": v.usuario.username,
                    "ramal": v.ramal,
                    "total_leads": v.total_leads,
                    "status": v.status,
                }
                for v in vendedores
            ]

            return JsonResponse({
                "status": "success",
                "data": dados,
            })
        except Exception as e:
            return JsonResponse({
                "status": "error",
                "message": str(e),
            }, status=500)