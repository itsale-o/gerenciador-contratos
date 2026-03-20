import time
import json
from datetime import date, timedelta
from decimal import Decimal
from functools import reduce
from operator import and_

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import UserPassesTestMixin
from django.contrib.auth.models import User, Group
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.db.models import Avg, Case, Count, F, IntegerField, OuterRef, Q, Subquery, Sum, Value, When
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

from .forms import FormCadastrarVendedor, FormEditarUsuarioVendedor, FormEditarVendedor
from .mixins import GroupRequiredMixin
from .models import Vendedor, Lead, ScoreLead
from comunicacao.models import SessaoLigacao, TentativaLigacao
from contratos.models import Contrato, ClaroEndereco, AuditoriaCdr
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


class DashboardAdmin(GroupRequiredMixin, TemplateView):
    template_name = "dashboard_admin.html"
    group_required = "Admin"

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)

        hoje = now().date()
        inicio_mes = date(hoje.year, hoje.month, 1)

        total_leads_distribuidos = Lead.objects.count()
        vendedores_ativos = Vendedor.objects.filter(status="ativo").count()
        leads_com_contato = Lead.objects.filter(contato_realizado=True).count()
        leads_sem_contato = Lead.objects.filter(contato_realizado=False).count()
        leads_com_venda = Lead.objects.filter(status="venda").count()
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
                    Case(When(status="venda", then=1), output_field=IntegerField())
                ),
                sem_contato=Count(
                    Case(When(contato_realizado=False, then=1), output_field=IntegerField())
                ),
            )
            .order_by("-total")
        )

        leads_mes = Lead.objects.filter(data_atribuicao__date__gte=inicio_mes)
        vendas_mes = leads_mes.filter(status="venda").count()
        sessoes_ligacao_mes = SessaoLigacao.objects.filter(criado_em__date__gte=inicio_mes).count()
        tentativas_ligacao_mes = TentativaLigacao.objects.filter(iniciada_em__date__gte=inicio_mes).count()
        leads_pendentes_retorno = Lead.objects.filter(proximo_contato__isnull=False,resolvido=False).count()
        retornos_urgentes = Lead.objects.filter(proximo_contato__lte=now(), resolvido=False).count()
        leads_nao_venda = Lead.objects.filter(
            contato_realizado=True
            ).exclude(
                status_contato__in=["nao_atendeu", "ligar_mais_tarde"]
            ).exclude(
                status__in=["venda",]
            )

        leads_caro = Lead.objects.filter(status_contato="caro")
        leads_sem_interesse = Lead.objects.filter(status_contato__in=["sem_interesse", "nao_virou_venda"])

        contexto.update({
            "leads_nao_venda": leads_nao_venda.count(),
            "leads_caro": leads_caro.count(),
            "leads_sem_interesse": leads_sem_interesse.count(),
            # "total_contratos": total_contratos,
            # "total_contratos_ativos": total_contratos_ativos,
            # "total_contratos_encerrados": total_contratos_encerrados,
            # "total_contratos_suspensos": total_contratos_suspensos,
            # "receita_mensal": receita_mensal,
            # "total_em_aberto": total_em_aberto,
            # "ticket_medio": ticket_medio,
            # "contratos_inadimplentes": contratos_inadimplentes,
            # "cancelamentos_mes": cancelamentos_mes,
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


class DashboardVendedor(GroupRequiredMixin, TemplateView):
    template_name = "dashboard_vendedor.html"
    group_required = "Vendedor"

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
            iniciada_em__date__gte=inicio_mes
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
            "vendedor": self.request.user.perfil_vendedor,
            "mostrar_modal_ramal": not bool(vendedor.ramal)
        })
        
        return contexto


@login_required
@require_POST
def definir_ramal(request):
    ramal = request.POST.get("ramal")
    vendedor = getattr(request.user, "perfil_vendedor", None)

    if not vendedor:
        messages.error(request, "Perfil de vendedor não encontrado.")
        return redirect("core:dashboard_vendedor")
    
    if not ramal:
        messages.error(request, "Selecione um ramal.")
        return redirect("core:dashboard_vendedor")

    vendedor.ramal = ramal
    vendedor.save(update_fields=["ramal"])

    messages.success(request, f"Ramal {ramal} definido com sucesso.")
    return redirect("core:dashboard_vendedor")


class ListaVendedores(LoginRequiredMixin, UserPassesTestMixin, FormMixin, ListView):
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

            messages.success(request, "Vendedor(a) cadastrado(a) com sucesso.")
            return self.form_valid(form)
        
        messages.error(request, "Erro ao cadastrar vendedor(a). Verifique os dados.")

        self.object_list = self.get_queryset()
        return self.form_invalid(form)


class DetalhesVendedor(LoginRequiredMixin, UserPassesTestMixin, View):
    template_name = "detalhes_vendedor.html"

    def test_func(self):
        return self.request.user.groups.filter(name="Admin").exists()

    def get_vendedor(self, pk):
        return get_object_or_404(
            Vendedor.objects.select_related("usuario"),
            pk=pk
        )
    
    def get(self, request, pk):
        vendedor = self.get_vendedor(pk)
        leads = Lead.objects.filter(vendedor=vendedor).order_by("-id")
        total_leads = leads.count()
        
        form_usuario = FormEditarUsuarioVendedor(instance=vendedor.usuario)
        form_vendedor = FormEditarVendedor(instance=vendedor)

        contexto = {
            "vendedor": vendedor,
            "leads": leads,
            "total_leads": total_leads,
            "form_usuario": form_usuario,
            "form_vendedor": form_vendedor,
        }

        return render(request, self.template_name, contexto)
    
    def post(self, request, pk):
        vendedor = self.get_vendedor(pk)

        form_usuario = FormEditarUsuarioVendedor(
            request.POST,
            instance=vendedor.usuario
        )
        form_vendedor = FormEditarVendedor(
            request.POST,
            instance=vendedor
        )

        leads = Lead.objects.filter(vendedor=vendedor).order_by("-id")
        total_leads = leads.count()
        total_convertidos = leads.filter(status="venda").count()  

        percentual_conversao = 0
        if total_leads > 0:
            percentual_conversao = (total_convertidos / total_leads) * 100

        if form_usuario.is_valid() and form_vendedor.is_valid():
            with transaction.atomic():
                form_usuario.save()
                form_vendedor.save()

            messages.success(request, "Informações do vendedor atualizadas com sucesso.")
            return redirect("core:detalhes_vendedor", pk=vendedor.pk)

        messages.error(request, "Erro ao atualizar os dados do vendedor.")

        contexto = {
            "vendedor": vendedor,
            "leads": leads,
            "total_leads": total_leads,
            "total_convertidos": total_convertidos,
            "percentual_conversao": percentual_conversao,
            "form_usuario": form_usuario,
            "form_vendedor": form_vendedor,
        }
        return render(request, self.template_name, contexto)


class ListaLeadsVendedor(LoginRequiredMixin, TemplateView):
    template_name = "lista_leads.html"

    def get_slug_coluna(self, lead):
        status = (lead.status or "").strip().lower()

        mapa = {
            "novo": "novo",
            "em_contato": "em_contato",
            "em_negociacao": "negociacao",
            "perdido": "perdido",
            "venda": "venda",
        }

        return mapa.get(status, "em_contato")

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)

        vendedor = get_object_or_404(Vendedor, usuario=self.request.user)

        leads = Lead.objects.filter(
            vendedor=vendedor
        ).order_by("-id")

        colunas_map = {
            "novo": {
                "slug": "novo",
                "titulo": "Novos Leads",
                "leads": [],
                "quantidade": 0,
                "valor_total": Decimal("0.00"),
            },
            "em_contato": {
                "slug": "em_contato",
                "titulo": "Em Contato",
                "leads": [],
                "quantidade": 0,
                "valor_total": Decimal("0.00"),
            },
            "negociacao": {
                "slug": "negociacao",
                "titulo": "Em Negociação",
                "leads": [],
                "quantidade": 0,
                "valor_total": Decimal("0.00"),
            },
            "perdido": {
                "slug": "perdido",
                "titulo": "Leads Perdidos",
                "leads": [],
                "quantidade": 0,
                "valor_total": Decimal("0.00"),
            },
            "venda": {
                "slug": "venda",
                "titulo": "Venda Realizada",
                "leads": [],
                "quantidade": 0,
                "valor_total": Decimal("0.00"),
            },
        }

        for lead in leads:
            coluna = self.get_slug_coluna(lead)
            colunas_map[coluna]["leads"].append(lead)
            colunas_map[coluna]["quantidade"] += 1

            contrato = lead.get_contrato()
            valor = getattr(contrato, "valor", 0) or 0
            colunas_map[coluna]["valor_total"] += valor

        contexto["vendedor"] = vendedor
        contexto["colunas"] = [
            colunas_map["novo"],
            colunas_map["em_contato"],
            colunas_map["negociacao"],
            colunas_map["perdido"],
            colunas_map["venda"],
        ]

        return contexto


class MoverLead(LoginRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        try:
            data = json.loads(request.body)

            lead_id = data.get("lead_id")
            coluna_destino = data.get("coluna_destino")
            status_contato = data.get("status_contato")

            if not lead_id or not coluna_destino:
                return JsonResponse(
                    {"sucesso": False, "erro": "Dados incompletos."},
                    status=400
                )

            vendedor = get_object_or_404(Vendedor, usuario=request.user)
            lead = get_object_or_404(Lead, pk=lead_id, vendedor=vendedor)

            colunas_validas = ["novo", "em_contato", "negociacao", "perdido", "venda"]
            if coluna_destino not in colunas_validas:
                return JsonResponse(
                    {"sucesso": False, "erro": "Coluna inválida."},
                    status=400
                )

            status_contato_em_contato = [
                "desligou",
                "nao_atendeu",
                "ligar_mais_tarde",
                "outros",
            ]

            status_contato_perdido = [
                "caro",
                "sem_interesse",
                "nao_virou_venda",
                "numero_invalido",
                "outros",
            ]

            if coluna_destino == "novo":
                lead.status = "novo"
                lead.contato_realizado = False
                lead.status_contato = None
                lead.resolvido = False
                lead.resolvido_em = None

            elif coluna_destino == "em_contato":
                if status_contato not in status_contato_em_contato:
                    return JsonResponse(
                        {
                            "sucesso": False,
                            "erro": "Selecione um status de contato válido para Em Contato."
                        },
                        status=400
                    )

                lead.status = "em_contato"
                lead.contato_realizado = True
                lead.status_contato = status_contato
                lead.resolvido = False
                lead.resolvido_em = None

            elif coluna_destino == "negociacao":
                lead.status = "em_negociacao"
                lead.contato_realizado = True
                lead.status_contato = None
                lead.resolvido = False
                lead.resolvido_em = None

            elif coluna_destino == "perdido":
                if status_contato not in status_contato_perdido:
                    return JsonResponse(
                        {
                            "sucesso": False,
                            "erro": "Selecione um motivo válido para Leads Perdidos."
                        },
                        status=400
                    )

                lead.status = "perdido"
                lead.contato_realizado = True
                lead.status_contato = status_contato
                lead.resolvido = True
                lead.resolvido_em = timezone.now()

            elif coluna_destino == "venda":
                lead.status = "venda"
                lead.contato_realizado = True
                lead.status_contato = None
                lead.resolvido = True
                lead.resolvido_em = timezone.now()

            lead.save()

            return JsonResponse({
                "sucesso": True,
                "lead_id": lead.id,
                "status": lead.status,
                "status_contato": lead.status_contato,
            })

        except json.JSONDecodeError:
            return JsonResponse(
                {"sucesso": False, "erro": "JSON inválido."},
                status=400
            )
        except Exception as e:
            return JsonResponse(
                {"sucesso": False, "erro": str(e)},
                status=500
            )


class DetalhesLead(LoginRequiredMixin, DetailView):
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

        historico_ligacoes = []
        try:
            historico_ligacoes = list(
                AuditoriaCdr.objects.using('contratos').filter(
                    contrato_numero=self.object.contrato
                ).values(
                    'inicio', 'duracao', 'vendedor_nome', 'contrato_numero',
                    'contrato_nome', 'hangup_text', 'gravacao'
                ).order_by('-inicio')[:50]
            )
        except Exception:
            historico_ligacoes = []

        contexto["lead"] = lead
        contexto["historico_ligacoes"] = historico_ligacoes

        return contexto


class ListaLeads(LoginRequiredMixin, ListView):
    template_name = "lista_todos_leads.html"
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


class ListaLeadsBairro(LoginRequiredMixin, ListView):
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
            "R.": "RUA",
            "DR ": "DOUTOR ",
            "DR.": "DOUTOR",
            "PROF ": "PROFESSOR ",
            "PROF.": "PROFESSOR",
            "ALF ": "ALFERES ",
            "ALF.": "ALFERES"
        }

        texto = " ".join(texto.upper().strip().split())

        for abrev, completo in mapa.items():
            if texto.startswith(abrev):
                texto = texto.replace(abrev, completo, 1)

        return texto

    def get_queryset(self):
        queryset = Contrato.objects.filter(
            cidade=self.get_cidade(),
            bairro=self.get_bairro(),
        )

        rua = self.get_rua()

        if rua:
            rua_original = rua.strip()
            rua_normalizada = self.normalizar_rua(rua_original)

            palavras = [
                p for p in rua_normalizada.split()
                if len(p) > 3
            ]

            filtro_exato = (
                Q(endereco__iexact=rua_original) |
                Q(endereco__iexact=rua_normalizada) |
                Q(endereco__icontains=rua_original) |
                Q(endereco__icontains=rua_normalizada)
            )

            filtro_palavras = Q()
            if palavras:
                filtro_palavras = reduce(
                    and_,
                    [Q(endereco__icontains=palavra) for palavra in palavras]
                )

            queryset = queryset.filter(filtro_exato | filtro_palavras)

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
            ClaroEndereco.objects
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


class AtribuirLead(LoginRequiredMixin, View):
    def post(self, request):
        vendedor_id = request.POST.get("vendedor")
        contrato_id = request.POST.get("contrato")

        if not vendedor_id:
            messages.error(request, "Selecione um vendedor.")
            return redirect(request.META.get("HTTP_REFERER", "core:lista_leads"))

        if not contrato_id:
            messages.error(request, "Nenhum contrato foi informado.")
            return redirect(request.META.get("HTTP_REFERER", "core:lista_leads"))

        vendedor = get_object_or_404(Vendedor, pk=vendedor_id)

        if Lead.objects.filter(contrato_id=contrato_id).exists():
            messages.warning(request, "Esse contrato já foi atribuído.")
            return redirect(request.META.get("HTTP_REFERER", "core:lista_leads"))

        Lead.objects.create(
            vendedor=vendedor,
            contrato_id=contrato_id
        )

        messages.success(request, "Lead atribuída com sucesso.")
        return redirect(request.META.get("HTTP_REFERER", "core:lista_leads"))


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

    vendedor = get_object_or_404(Vendedor, pk=vendedor_id)

    contratos_ja_atribuidos = set(
        Lead.objects.filter(contrato_id__in=contratos)
        .values_list("contrato_id", flat=True)
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
        if quantidade_criada == 1:
            messages.success(request, f"{quantidade_criada} lead atribuída com sucesso.")
        else:
            messages.success(request, f"{quantidade_criada} leads atribuídas com sucesso.")

    if quantidade_ignoradas:
        messages.warning(request, f"{quantidade_ignoradas} contrato(s) já estavam atribuídos e foram ignorados.")

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


@login_required
@require_POST
@transaction.atomic
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
    status_anterior = lead.status_contato
    lead.status_contato = status
    lead.contato_realizado = True

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

    if status == "venda":
        if not lead.resolvido:
            lead.resolvido = True
            lead.resolvido_em = timezone.now()
    else:
        lead.resolvido = False
        lead.resolvido_em = None

    lead.save()

    if status_anterior != "venda" and status == "venda":
        criar_cliente(lead)

    return JsonResponse({"ok": True})


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