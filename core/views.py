import json
import requests
from datetime import date, datetime, timedelta
from decimal import Decimal
from functools import reduce
from operator import and_
from time import perf_counter

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import Group
from django.contrib.auth.views import PasswordChangeView
from django.contrib.messages.views import SuccessMessageMixin
from django.db.models import Avg, Case, Count, F, IntegerField, OuterRef, Q, Subquery, Sum, Value, When
from django.db.models.functions import Coalesce
from django.db import transaction, connection
from django.shortcuts import get_object_or_404, redirect, render
from django.http import HttpResponse, JsonResponse, StreamingHttpResponse
from django.urls import reverse_lazy, reverse
from django.utils import timezone
from django.utils.timezone import now
from django.views import View
from django.utils.decorators import method_decorator
from django.views.decorators.http import require_POST
from django.views.generic import ListView, TemplateView, View
from django.views.generic.detail import DetailView
from django.views.generic.edit import FormMixin

from .decorators import admin_required
from .forms import FormCadastrarVendedor, FormEditarUsuarioVendedor, FormEditarVendedor
from .mixins import GroupRequiredMixin
from .models import Vendedor, Lead, ScoreLead
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


@login_required
def listar_ramais_disponiveis(request):
    resultado = buscar_ramais_disponiveis()

    if not resultado["sucesso"]:
        return JsonResponse({
            "sucesso": False,
            "erro": resultado["erro"],
            "total": 0,
            "ramais": []
        }, status=400)

    return JsonResponse({
        "sucesso": True,
        "total": resultado["total"],
        "ramais": resultado["ramais"]
    })


def parse_ultima_chamada_data(ultima_chamada):
    if not ultima_chamada:
        return None

    try:
        return datetime.strptime(ultima_chamada, "%H:%M:%S %d/%m/%Y").date()
    except ValueError:
        return None


def fetch_claro_vendedor_estatisticas():
    api_base = getattr(settings, "PABX_API_URL", "").rstrip("/")
    if not api_base:
        return []

    url = f"{api_base}/estatisticas_vendedor"

    try:
        response = requests.get(url, timeout=8)
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, ValueError):
        return []

    if isinstance(payload, dict):
        vendedores = payload.get("vendedores", [])
        if isinstance(vendedores, list):
            return vendedores

    return []


@login_required
def gerenciamento_vendas(request):
    vendas = [
        {
            "id": 1001,
            "contrato": "CTR-2026-001",
            "vendedor": "Marcos Lima",
            "cliente": "Ana Souza",
            "fatura": "Em aberto",
            "mensagem": "Aguardando retorno para agendar instalação.",
            "motivos": "Documentação incompleta.",
            "acao": "Solicitar envio de documentos e confirmar agenda.",
            "status": "Realizada",
            "comissao_vendedor": False,
            "comissao_claro": False,
            "data": date(2026, 3, 18),
        },
        {
            "id": 1002,
            "contrato": "CTR-2026-002",
            "vendedor": "Paula Menezes",
            "cliente": "Carlos Pereira",
            "fatura": "Emitida",
            "mensagem": "Contrato aprovado e instalado no endereço.",
            "motivos": "Instalação concluída com sucesso.",
            "acao": "Registrar venda e liberar comissão.",
            "status": "Instalada",
            "comissao_vendedor": True,
            "comissao_claro": False,
            "data": date(2026, 3, 16),
        },
        {
            "id": 1003,
            "contrato": "CTR-2026-003",
            "vendedor": "João Alves",
            "cliente": "Priscila Castro",
            "fatura": "Aguardando emissão",
            "mensagem": "Cliente solicitou alteração do pacote.",
            "motivos": "Aguardando aprovação de upgrade.",
            "acao": "Verificar pacote disponível e reemitir contrato.",
            "status": "Realizada",
            "comissao_vendedor": False,
            "comissao_claro": False,
            "data": date(2026, 3, 21),
        },
        {
            "id": 1004,
            "contrato": "CTR-2026-004",
            "vendedor": "Marina Costa",
            "cliente": "Felipe Rocha",
            "fatura": "Instalada",
            "mensagem": "Venda convertida e comissão registrada.",
            "motivos": "Cliente já tinha vínculo com a Claro.",
            "acao": "Concluir atendimento e finalizar processo.",
            "status": "Instalada",
            "comissao_vendedor": True,
            "comissao_claro": True,
            "data": date(2026, 3, 10),
        },
        {
            "id": 1005,
            "contrato": "CTR-2026-005",
            "vendedor": "Renata Silva",
            "cliente": "Luiz Fernando",
            "fatura": "A definir",
            "mensagem": "Problema com endereço de instalação.",
            "motivos": "Endereço divergente no cadastro.",
            "acao": "Confirmar endereço e reagendar visita.",
            "status": "Realizada",
            "comissao_vendedor": False,
            "comissao_claro": False,
            "data": date(2026, 3, 23),
        },
    ]

    vendedores = sorted({item["vendedor"] for item in vendas})
    clientes = sorted({item["cliente"] for item in vendas})
    status_options = ["Realizada", "Instalada"]

    vendedor_selected = request.GET.get("vendedor", "")
    cliente_selected = request.GET.get("cliente", "")
    status_selected = request.GET.get("status", "")
    data_inicio = request.GET.get("data_inicio", "")
    data_fim = request.GET.get("data_fim", "")

    if vendedor_selected:
        vendas = [item for item in vendas if item["vendedor"] == vendedor_selected]

    if cliente_selected:
        vendas = [item for item in vendas if cliente_selected.lower() in item["cliente"].lower()]

    if status_selected:
        vendas = [item for item in vendas if item["status"] == status_selected]

    def parse_date(value):
        try:
            return datetime.strptime(value, "%Y-%m-%d").date()
        except (ValueError, TypeError):
            return None

    inicio = parse_date(data_inicio)
    fim = parse_date(data_fim)

    if inicio:
        vendas = [item for item in vendas if item["data"] >= inicio]
    if fim:
        vendas = [item for item in vendas if item["data"] <= fim]

    context = {
        "vendas": vendas,
        "vendedores": vendedores,
        "clientes": clientes,
        "status_options": status_options,
        "vendedor_selected": vendedor_selected,
        "cliente_selected": cliente_selected,
        "status_selected": status_selected,
        "data_inicio": data_inicio,
        "data_fim": data_fim,
    }

    return render(request, "gerenciamento_vendas.html", context)


class AlterarSenha(GroupRequiredMixin, SuccessMessageMixin, PasswordChangeView):
    template_name = "alterar_senha.html"
    success_url = reverse_lazy("core:alterar_senha")
    success_message = "Senha alterada com sucesso."
    groups_required = ["Admin", "Vendedor"]


class EditarPerfil(View):
    template_name = "editar_perfil.html"
    
    def dispatch(self, request, *args, **kwargs):
        if not request.user.groups.filter(name="Vendedor").exists():
            messages.error(request, "Você não tem permissão para acessar esta página.")
            return redirect("core:home")

        self.usuario_obj = request.user
        self.vendedor_obj = getattr(request.user, "perfil_vendedor", None)

        if not self.vendedor_obj:
            messages.error(request, "Perfil de vendedor não encontrado.")
            return redirect("core:home")
        
        return super().dispatch(request, *args, **kwargs)

    def get(self, request, *args, **kwargs):
        form_usuario = FormEditarUsuarioVendedor(instance=self.usuario_obj)
        form_vendedor = FormEditarVendedor(instance=self.vendedor_obj)

        context = {
            "form_usuario": form_usuario,
            "form_vendedor": form_vendedor,
        }

        return render(request, self.template_name, context)

    def post(self, request, *args, **kwargs):
        form_usuario = FormEditarUsuarioVendedor(
            request.POST,
            instance=self.usuario_obj
        )
        form_vendedor = FormEditarVendedor(
            request.POST,
            instance=self.vendedor_obj
        )

        if form_usuario.is_valid() and form_vendedor.is_valid():
            form_usuario.save()
            form_vendedor.save()

            messages.success(request, "Seus dados foram atualizados com sucesso.")
            return redirect("core:editar_perfil")

        context = {
            "form_usuario": form_usuario,
            "form_vendedor": form_vendedor,
        }

        return render(request, self.template_name, context)


class DashboardAdmin(GroupRequiredMixin, TemplateView):
    template_name = "dashboard_admin.html"
    groups_required = ["Admin"]

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
        sessoes_ligacao_mes = AuditoriaCdr.objects.filter(inicio__date__gte=inicio_mes).values('contrato_numero').distinct().count()
        tentativas_ligacao_mes = AuditoriaCdr.objects.filter(inicio__date__gte=inicio_mes).count()
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

        vendedores_telefonia = fetch_claro_vendedor_estatisticas()
        ranking_vendedores_telefonia = sorted(
            vendedores_telefonia,
            key=lambda item: item.get("total_chamadas", 0),
            reverse=True,
        )[:5]

        hoje_data = now().date()
        sete_dias_atras = hoje_data - timedelta(days=7)

        ligacoes_hoje = sum(
            1
            for item in vendedores_telefonia
            if parse_ultima_chamada_data(item.get("ultima_chamada")) == hoje_data
        )
        vendedores_ativos_7dias = sum(
            1
            for item in vendedores_telefonia
            if (ultima := parse_ultima_chamada_data(item.get("ultima_chamada")))
            and sete_dias_atras <= ultima <= hoje_data
        )
        total_chamadas_7dias = sum(item.get("total_chamadas", 0) for item in vendedores_telefonia)

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
            # "sessoes_ligacao_mes": sessoes_ligacao_mes,
            # "tentativas_ligacao_mes": tentativas_ligacao_mes,
            "leads_pendentes_retorno": leads_pendentes_retorno,
            "retornos_urgentes": retornos_urgentes,
            "telefonia_ligacoes_hoje": ligacoes_hoje,
            "telefonia_total_chamadas_7dias": total_chamadas_7dias,
            "telefonia_vendedores_ativos_7dias": vendedores_ativos_7dias,
            "telefonia_ranking_vendedores": ranking_vendedores_telefonia,
        })

        return contexto


class DashboardVendedor(GroupRequiredMixin, TemplateView):
    template_name = "dashboard_vendedor.html"
    groups_required = ["Vendedor"]

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
            status="venda"
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
        
        sessoes_ligacao = AuditoriaCdr.objects.filter(
            vendedor_id=vendedor.id,
            inicio__date__gte=inicio_mes
        ).values('contrato_numero').distinct().count()
        
        tentativas_ligacao = AuditoriaCdr.objects.filter(
            vendedor_id=vendedor.id,
            inicio__date__gte=inicio_mes
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


class ListaVendedores(GroupRequiredMixin, FormMixin, ListView):
    model = Vendedor
    template_name = "lista_vendedores.html"
    context_object_name = "vendedores"
    form_class = FormCadastrarVendedor
    success_url = reverse_lazy("core:lista_vendedores")
    groups_required = ["Admin"]

    def get_queryset(self):
        return Vendedor.objects.select_related("usuario").order_by("usuario__username")

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


class DetalhesVendedor(GroupRequiredMixin, View):
    template_name = "detalhes_vendedor.html"
    groups_required = ["Admin"]

    def get_vendedor(self, id_vendedor):
        return get_object_or_404(
            Vendedor.objects.select_related("usuario"),
            id=id_vendedor
        )
    
    def get(self, request, id_vendedor):
        vendedor = self.get_vendedor(id_vendedor)
        leads = Lead.objects.filter(vendedor=vendedor).order_by("-id")
        total_leads = leads.count()
        
        form_usuario = FormEditarUsuarioVendedor(instance=vendedor.usuario)
        form_vendedor = FormEditarVendedor(instance=vendedor)

        contexto = {
            "vendedor": vendedor,
            "id_vendedor": vendedor.id,
            "leads": leads,
            "total_leads": total_leads,
            "form_usuario": form_usuario,
            "form_vendedor": form_vendedor,
        }

        return render(request, self.template_name, contexto)
    
    def post(self, request, id_vendedor):
        vendedor = self.get_vendedor(id_vendedor)

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
            return redirect("core:detalhes_vendedor", id_vendedor=vendedor.id)

        messages.error(request, "Erro ao atualizar os dados do vendedor.")

        contexto = {
            "vendedor": vendedor,
            "id_vendedor": vendedor.id,
            "leads": leads,
            "total_leads": total_leads,
            "total_convertidos": total_convertidos,
            "percentual_conversao": percentual_conversao,
            "form_usuario": form_usuario,
            "form_vendedor": form_vendedor,
        }
        return render(request, self.template_name, contexto)


class HistoricoLeadsVendedor(GroupRequiredMixin, ListView):
    model = Lead
    template_name = "historico_leads_vendedor.html"
    context_object_name = "leads"
    paginate_by = 50
    groups_required = ["Admin"]

    def dispatch(self, request, *args, **kwargs):
        self.vendedor = get_object_or_404(
            Vendedor,
            id=self.kwargs["id_vendedor"]
        )
        
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        queryset = (
            Lead.objects
            .filter(vendedor=self.vendedor)
        ).order_by("-id")

        return queryset

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        leads = contexto["leads"]
        contratos_ids = [
            lead.contrato_id
            for lead in leads
            if lead.contrato_id
        ]
        contratos = Contrato.objects.filter(
            contrato__in=contratos_ids
        )
        contratos_map = {
            contrato.contrato: contrato
            for contrato in contratos
        }
        queryset = self.get_queryset()
        total_leads = queryset.count()
        total_convertidos = queryset.filter(status="venda").count()
        percentual_conversao = 0

        if total_leads > 0:
            percentual_conversao = (total_convertidos / total_leads) * 100

        contexto.update({
            "vendedor": self.vendedor,
            "contratos_map": contratos_map,
            "total_leads": total_leads,
            "total_convertidos": total_convertidos,
            "percentual_conversao": percentual_conversao,
        })

        return contexto


class HistoricoLigacoesVendedor(GroupRequiredMixin, ListView):
    model = AuditoriaCdr
    template_name = "historico_ligacoes_vendedor.html"
    context_object_name = "ligacoes"
    paginate_by = 50
    groups_required = ["Admin"]

    def dispatch(self, request, *args, **kwargs):
        self.vendedor = get_object_or_404(
            Vendedor,
            pk=self.kwargs["pk"]
        )
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        queryset = (
            AuditoriaCdr.objects
            .filter(vendedor_id=self.vendedor.usuario_id)
            .order_by("-inicio", "-created_at")
        )

        data_inicial = self.request.GET.get("data_inicial")
        data_final = self.request.GET.get("data_final")

        if data_inicial:
            queryset = queryset.filter(inicio__date__gte=data_inicial)

        if data_final:
            queryset = queryset.filter(inicio__date__lte=data_final)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        queryset = self.get_queryset()

        context["vendedor"] = self.vendedor

        total_tentativas = queryset.values("uuid").distinct().count()

        total_atendidas = (
            queryset.filter(
                Q(atendimento__isnull=False) | Q(duracao__gt=0)
            )
            .values("uuid")
            .distinct()
            .count()
        )

        total_sem_resposta = (
            queryset.filter(
                Q(atendimento__isnull=True) & (
                    Q(duracao__isnull=True) | Q(duracao=0)
                )
            )
            .values("uuid")
            .distinct()
            .count()
        )

        context.update({
            "total_tentativas": total_tentativas,
            "total_atendidas": total_atendidas,
            "total_sem_resposta": total_sem_resposta,
            "PABX_API_URL": settings.PABX_API_URL
        })

        return context

@login_required
def baixar_gravacao(request, uuid):
    url = f"{settings.PABX_API_URL}/stream_gravacao?uuid={uuid}"
    response = requests.get(url, stream=True)
    ligacao = AuditoriaCdr.objects.get(uuid=uuid)
    contrato = ligacao.contrato_numero
    filename = f"contrato_{contrato}_gravacao_{uuid}.wav"

    if response.status_code != 200:
        return HttpResponse("Erro ao baixar arquivo", status=400)

    return StreamingHttpResponse(
        response.iter_content(chunk_size=8192),
        content_type="audio/wav",
        headers={
            "Content-Disposition": f"attachment; filename='{filename}'"
        }
    )


class ListaLeadsVendedor(GroupRequiredMixin, TemplateView):
    template_name = "lista_leads.html"
    groups_required = ["Vendedor"]

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
        t0 = perf_counter()
        contexto = super().get_context_data(**kwargs)
        vendedor = get_object_or_404(Vendedor, usuario=self.request.user)

        t1 = perf_counter()

        leads = list(
            Lead.objects.filter(vendedor=vendedor)
            .order_by("data_atribuicao", "id")
        )
        t2 = perf_counter()

        contratos_ids = [lead.contrato_id for lead in leads if lead.contrato_id]
        t3 = perf_counter()
        contratos = Contrato.objects.filter(contrato__in=contratos_ids)
        contratos_map = {
            c.contrato: c
            for c in contratos
        }

        t4 = perf_counter()

        tentativas_qs = (
            AuditoriaCdr.objects
            .filter(
                vendedor_id=vendedor.usuario_id,
                contrato_numero__in=[str(cid) for cid in contratos_ids]
            )
            .values("contrato_numero")
            .annotate(total=Count("uuid", distinct=True))
        )

        tentativas_map = {
            int(item["contrato_numero"]): item["total"]
            for item in tentativas_qs
            if item["contrato_numero"]
        }

        t5 = perf_counter()

        colunas_map = {
            "novo": {"slug": "novo", "titulo": "Novos Leads", "leads": [], "quantidade": 0, "valor_total": Decimal("0.00"),},
            "em_contato": {"slug": "em_contato", "titulo": "Em Contato", "leads": [], "quantidade": 0, "valor_total": Decimal("0.00"),},
            "negociacao": {"slug": "negociacao", "titulo": "Em Negociação", "leads": [], "quantidade": 0, "valor_total": Decimal("0.00"),},
            "perdido": {"slug": "perdido", "titulo": "Leads Perdidos", "leads": [], "quantidade": 0, "valor_total": Decimal("0.00"),},
            "venda": {"slug": "venda", "titulo": "Venda Realizada", "leads": [], "quantidade": 0, "valor_total": Decimal("0.00"),},
        }

        for lead in leads:
            total_tentativas = tentativas_map.get(lead.contrato_id, 0)
            ciclos_tentativas = total_tentativas // 3
            lead._prioridade_cache = 1 if ciclos_tentativas > lead.ciclos_resetados else 0
            contrato = contratos_map.get(lead.contrato_id)
            lead._contrato_cache = contrato
            coluna = self.get_slug_coluna(lead)

            colunas_map[coluna]["leads"].append(lead)
            colunas_map[coluna]["quantidade"] += 1
            colunas_map[coluna]["valor_total"] += getattr(contrato, "valor", 0) or 0

        t6 = perf_counter()
        # ordena dentro de cada coluna
        for coluna in colunas_map.values():
            coluna["leads"].sort(
                key=lambda l: (
                    l._prioridade_cache,  # normal primeiro, rebaixado depois
                    l.data_atribuicao,  # mais antigos primeiro
                    l.id,               # desempate
                )
            )
        t7 = perf_counter()

        print(f"[PERF] vendedor: {t1 - t0:.4f}s")
        print(f"[PERF] leads: {t2 - t1:.4f}s")
        print(f"[PERF] ids contratos: {t3 - t2:.4f}s")
        print(f"[PERF] contratos_map: {t4 - t3:.4f}s")
        print(f"[PERF] tentativas_map: {t5 - t4:.4f}s")
        print(f"[PERF] montagem colunas: {t6 - t5:.4f}s")
        print(f"[PERF] sort final: {t7 - t6:.4f}s")
        print(f"[PERF] total: {t7 - t0:.4f}s")

        contexto["vendedor"] = vendedor
        contexto["total_leads_perdidos"] = Lead.objects.filter(vendedor=vendedor, status="perdido").count()
        contexto["total_leads_venda"] = Lead.objects.filter(vendedor=vendedor, status="venda").count()
        contexto["colunas"] = [
            colunas_map["novo"],
            colunas_map["em_contato"],
            colunas_map["negociacao"],
            # colunas_map["perdido"],
            # colunas_map["venda"],
        ]

        return contexto


class ListaLeadsPerdidos(GroupRequiredMixin, TemplateView):
    template_name = "lista_leads_perdidos.html"
    groups_required = ["Vendedor"]

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        vendedor = get_object_or_404(Vendedor, usuario=self.request.user)
        contexto["leads_perdidos"] = Lead.objects.filter(vendedor=vendedor, status="perdido").order_by("-resolvido_em")

        return contexto


class ListaLeadsVenda(GroupRequiredMixin, TemplateView):
    template_name = "lista_leads_venda.html"
    groups_required = ["Vendedor"]

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        vendedor = get_object_or_404(Vendedor, usuario=self.request.user)
        contexto["leads_venda"] = Lead.objects.filter(vendedor=vendedor, status="venda").order_by("-resolvido_em")

        return contexto


class MoverLead(GroupRequiredMixin, View):
    groups_required = ["Vendedor"]

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

            colunas_validas = ["novo", "em_contato", "negociacao"]
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


class DetalhesLead(GroupRequiredMixin, DetailView):
    model = Contrato
    template_name = "detalhes_lead.html"
    context_object_name = "contrato"
    groups_required = ["Vendedor"]

    def get_object(self):
        numero_contrato = self.kwargs["pk"]
        return get_object_or_404(Contrato, contrato=numero_contrato)

    def get_lead(self):
        return get_object_or_404(
            Lead,
            vendedor__usuario=self.request.user,
            contrato_id=self.get_object().contrato
        )

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)

        lead = get_object_or_404(
            Lead,
            vendedor__usuario=self.request.user,
            contrato_id=self.object.contrato
        )

        historico_ligacoes = []
        total_tentativas = 0
        vendedor = lead.vendedor
        user_id = vendedor.usuario_id

        try:
            ligacoes_qs = (
                AuditoriaCdr.objects.filter(
                    contrato_numero=str(self.object.contrato),
                    vendedor_id=user_id
                )
                .order_by("-inicio", "-created_at")[:50]
            )

            historico_ligacoes = list(ligacoes_qs)

            total_tentativas = (
                AuditoriaCdr.objects.filter(
                    contrato_numero=str(self.object.contrato),
                    vendedor_id=user_id
                )
                .values("uuid")
                .distinct()
                .count()
            )

            contexto["debug_info"] = {
                "contrato_id": str(self.object.contrato),
                "total_encontrado": len(historico_ligacoes),
                "total_tentativas": total_tentativas,
                "primeiro_registro": str(historico_ligacoes[0]) if historico_ligacoes else "Sem registros",
            }

        except Exception as e:
            contexto["debug_info"] = {"erro": str(e)}

        contexto["lead"] = lead
        contexto["status_lead"] = lead.get_status_display
        contexto["historico_ligacoes"] = historico_ligacoes
        contexto["total_tentativas"] = total_tentativas
        contexto["foi_para_fim_da_fila"] = total_tentativas > 3

        return contexto


class ListaLeads(GroupRequiredMixin, ListView):
    template_name = "lista_todos_leads.html"
    context_object_name = "bairros"
    groups_required = ["Admin"]
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

        contexto["total_contratos"] = Contrato.objects.all().count()

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


class ListaLeadsBairro(GroupRequiredMixin, ListView):
    model = Contrato
    template_name = "leads_endereco.html"
    context_object_name = "contratos"
    groups_required = ["Admin"]
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


class AtribuirLead(GroupRequiredMixin, View):
    groups_required = ["Admin"]

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
@admin_required
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

    contratos_ja_atribuidos_str = {str(c) for c in contratos_ja_atribuidos}

    leads_para_criar = [
        Lead(contrato_id=contrato, vendedor=vendedor)
        for contrato in contratos
        if str(contrato) not in contratos_ja_atribuidos_str
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


class DetalhesContrato(GroupRequiredMixin, DetailView):
    model = Contrato
    template_name = "detalhes_contrato.html"
    context_object_name = "contrato"
    groups_required = ["Admin"]

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


def alterar_status_lead(request, contrato_id):
    if request.method != "POST":
        return JsonResponse({"erro": "Método não permitido"}, status=405)
    
    vendedor = Vendedor.objects.get(usuario=request.user)
    lead = get_object_or_404(
        Lead,
        vendedor=vendedor,
        contrato_id=contrato_id
    )
    
    novo_status = request.POST.get("status")
    if novo_status not in ["venda", "perdido"]:
        return JsonResponse({"erro": "Status inválido"}, status=400)
    
    lead.status = novo_status
    if novo_status == "venda":
        lead.resolvido = True
        lead.resolvido_em = timezone.now()
        criar_cliente(lead)
    elif novo_status == "perdido":
        lead.resolvido = True
        lead.resolvido_em = timezone.now()
    
    lead.save()
    
    return JsonResponse({
        "ok": True,
        "redirect_url": reverse(f"core:lista_leads_{novo_status}")
    })


class DashboardLeadsDistribuicaoAPI(GroupRequiredMixin, View):
    groups_required = ["Admin", "Vendedor"]
    return_json = True

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
                        Case(When(status="venda", then=1), output_field=IntegerField())
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
                contratos_ids = list(
                    Lead.objects.filter(vendedor_id=vendedor_id)
                    .values_list("contrato_id", flat=True)
                )
                
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


class DashboardVendasMesAPI(GroupRequiredMixin, View):
    groups_required = ["Admin", "Vendedor"]
    return_json = True

    def get(self, request):
        try:
            hoje = now().date()
            inicio_mes = date(hoje.year, hoje.month, 1)
            
            lead_query = Lead.objects.filter(
                data_atribuicao__date__gte=inicio_mes,
                status="venda"
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


class DashboardRetornosUrgentesAPI(GroupRequiredMixin, View):
    groups_required = ["Admin", "Vendedor"]
    return_json = True

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


class DashboardSessoesLigacaoAPI(GroupRequiredMixin, View):
    """API para obter sessões de ligação por vendedor"""
    groups_required = ["Admin", "Vendedor"]
    return_json = True

    def get(self, request):
        try:
            sessoes = AuditoriaCdr.objects

            if request.user.groups.filter(name="Vendedor").exists():
                vendedor = Vendedor.objects.get(usuario=request.user)
                sessoes = sessoes.filter(vendedor_id=vendedor.usuario_id)

            sessoes = (
                sessoes
                .values("vendedor_nome", "vendedor_id")
                .annotate(total_sessoes=Count("contrato_numero", distinct=True))
                .order_by("-total_sessoes")
            )

            dados = []
            for item in sessoes:
                vendedor_id = item["vendedor_id"]
                sessoes_leads = (
                    AuditoriaCdr.objects.filter(vendedor_id=vendedor_id)
                    .values('contrato_numero', 'contrato_nome', 'inicio')
                    .distinct()
                    .order_by("-inicio")[:10]
                )

                contratos_info = []
                for sessao in sessoes_leads:
                    contratos_info.append({
                        "contrato": sessao['contrato_numero'],
                        "cliente": sessao['contrato_nome'],
                        "valor": None,  # Não temos valor na auditoria_cdr
                        "status": None,  # Não temos status na auditoria_cdr
                        "proximo_contato": sessao['inicio'].strftime("%d/%m/%Y %H:%M") if sessao['inicio'] else "",
                    })

                dados.append({
                    "vendedor": item["vendedor_nome"],
                    "total_sessoes": item["total_sessoes"],
                    "contratos": contratos_info
                })

            return JsonResponse({"status": "success", "data": dados})
        except Exception as e:
            return JsonResponse({"status": "error", "message": str(e)}, status=500)


class DashboardTentativasLigacaoAPI(GroupRequiredMixin, View):
    """API para obter tentativas de ligação por vendedor"""
    groups_required = ["Admin", "Vendedor"]
    return_json = True

    def get(self, request):
        try:
            tentativas = AuditoriaCdr.objects

            if request.user.groups.filter(name="Vendedor").exists():
                vendedor = Vendedor.objects.get(usuario=request.user)
                tentativas = tentativas.filter(vendedor_id=vendedor.usuario_id)

            tentativas_agg = (
                tentativas
                .values("vendedor_nome", "vendedor_id")
                .annotate(total_tentativas=Count("uuid"))
                .order_by("-total_tentativas")
            )

            dados = []
            for item in tentativas_agg:
                vendedor_id = item["vendedor_id"]
                tentativas_vendedor = (
                    AuditoriaCdr.objects.filter(vendedor_id=vendedor_id)
                    .order_by("-inicio")[:10]
                )

                contratos_info = []
                for tentativa in tentativas_vendedor:
                    contratos_info.append({
                        "contrato": tentativa.contrato_numero,
                        "cliente": tentativa.contrato_nome,
                        "valor": None,  # Não temos valor na auditoria_cdr
                        "status": None,  # Não temos status na auditoria_cdr
                        "proximo_contato": tentativa.inicio.strftime("%d/%m/%Y %H:%M") if tentativa.inicio else "",
                    })

                dados.append({
                    "vendedor": item["vendedor_nome"],
                    "total_tentativas": item["total_tentativas"],
                    "contratos": contratos_info
                })

            return JsonResponse({"status": "success", "data": dados})
        except Exception as e:
            return JsonResponse({"status": "error", "message": str(e)}, status=500)


class DashboardTelefoniaAPI(GroupRequiredMixin, View):
    groups_required = ["Admin", "Vendedor"]
    return_json = True

    def get(self, request):
        try:
            vendedores = fetch_claro_vendedor_estatisticas()
            dados = []

            for item in vendedores:
                dados.append({
                    "vendedor_id": item.get("vendedor_id"),
                    "vendedor_nome": item.get("vendedor_nome"),
                    "total_chamadas": item.get("total_chamadas", 0),
                    "atendidas": item.get("atendidas", 0),
                    "nao_atendidas": item.get("nao_atendidas", 0),
                    "tma": item.get("tma", "00:00:00"),
                    "tempo_total": item.get("tempo_total", 0),
                    "ultima_chamada": item.get("ultima_chamada", ""),
                    "tma_segundos": item.get("tma_segundos", 0),
                })

            return JsonResponse({"status": "success", "data": dados})
        except Exception as e:
            return JsonResponse({"status": "error", "message": str(e)}, status=500)


class DashboardLeadsSemContatoAPI(GroupRequiredMixin, View):
    groups_required = ["Admin", "Vendedor"]
    return_json = True

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


class DashboardLeadsComContatoAPI(GroupRequiredMixin, View):
    groups_required = ["Admin", "Vendedor"]
    return_json = True

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


class DashboardLeadsSemVendaAPI(GroupRequiredMixin, View):
    """API para obter detalhes de leads sem venda por vendedor"""
    groups_required = ["Admin", "Vendedor"]
    return_json = True

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


class DashboardLeadsNaoVendaAPI(GroupRequiredMixin, View):
    """API para obter leads que não viraram venda"""
    groups_required = ["Admin", "Vendedor"]
    return_json = True

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


class DashboardLeadsCaroAPI(GroupRequiredMixin, View):
    groups_required = ["Admin", "Vendedor"]
    return_json = True

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


class DashboardLeadsSemInteresseAPI(GroupRequiredMixin, View):
    """API para obter leads que não tem interesse"""
    groups_required = ["Admin", "Vendedor"]
    return_json = True

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
class DashboardReatribuirLeadAPI(GroupRequiredMixin, View):
    """API para reatribuir lead a outro vendedor"""

    groups_required = ["Admin"]
    return_json = True

    def post(self, request):
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


class DashboardVendedoresAtivosAPI(GroupRequiredMixin, View):
    """API para obter lista de vendedores ativos"""
    groups_required = ["Admin"]
    return_json = True

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