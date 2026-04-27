import json
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal
from functools import reduce
from operator import and_

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.models import Group
from django.contrib.auth.views import LoginView, PasswordChangeView
from django.contrib.messages.views import SuccessMessageMixin
from django.db.models import Avg, Case, Count, IntegerField, OuterRef, Q, Subquery, Sum, Value, When
from django.db.models.functions import Coalesce
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.http import JsonResponse
from django.urls import reverse_lazy
from django.utils import timezone
from django.utils.timezone import now
from django.views import View
from django.views.generic import ListView, TemplateView, View
from django.views.generic.detail import DetailView
from django.views.generic.edit import FormMixin

from .forms import FormCadastrarVendedor, FormEditarUsuarioVendedor, FormEditarVendedor
from .mixins import GroupRequiredMixin
from .models import Vendedor, Lead, ScoreLead, Fatura
from .utils import parse_ultima_chamada_data, fetch_claro_vendedor_estatisticas
from contratos.models import Contrato, ClaroEndereco, AuditoriaCdr, BaseArrecadacao, BaseConexao

# Views gerais
class CustomLogin(LoginView):
    template_name = "login.html"

    def form_invalid(self, form):
        messages.error(self.request, "Usuário ou senha inválidos")
        return super().form_invalid(form)


class AlterarSenha(GroupRequiredMixin, SuccessMessageMixin, PasswordChangeView):
    template_name = "alterar_senha.html"
    success_url = reverse_lazy("core:alterar_senha")
    success_message = "Senha alterada com sucesso."
    groups_required = ["Admin", "Vendedor"]


class EditarPerfil(GroupRequiredMixin, View):
    template_name = "editar_perfil.html"
    groups_required = ["Admin", "Vendedor"]
    
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


# Views de admin
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


class ListaVendas(GroupRequiredMixin, ListView):
    model = BaseArrecadacao
    template_name = "lista_vendas.html"
    context_object_name = "vendas"
    groups_required = ["Admin"]

    def get_queryset(self):
        return BaseArrecadacao.objects.all()

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        vendas = contexto["vendas"]
        contratos = [v.domicilios_nr_contrato for v in vendas]
        conexoes = BaseConexao.objects.filter(
            contrato=contratos
        )

        conexao_por_contrato = {
            c.contrato: c
            for c in conexoes
        }

        faturas = Fatura.objects.filter(
            contrato__in=contratos,
            parcela__lte=5
        ).order_by("contrato", "parcela")

        faturas_por_contrato = defaultdict(list)

        for f in faturas:
            faturas_por_contrato[f.contrato].append(f)

        vendas_formatadas = []

        for venda in vendas:
            contrato = venda.domicilios_nr_contrato
            conexao = conexao_por_contrato.get(contrato)
            faturas_contrato = faturas_por_contrato.get(contrato, [])
            status = self.calcular_status(faturas_contrato)

            cliente = getattr(conexao, "cliente", "-") if conexao else "-"
            vendedor = getattr(conexao, "vendedor", "-") if conexao else "-"
            
            vendas_formatadas.append({
                "contrato": contrato,
                "cliente": cliente,
                "vendedor": vendedor,
                "status": status,
                "faturas": faturas_contrato
            })

            contexto["vendas_formatadas"] = vendas_formatadas
            contexto["total"] = len(vendas_formatadas)
            contexto["saudaveis"] = sum(1 for v in vendas_formatadas if v["status"] == "OK")
            contexto["risco"] = sum(1 for v in vendas_formatadas if v["status"] == "RISCO")
            contexto["critico"] = sum(1 for v in vendas_formatadas if v["status"] == "CRITICO")

        return contexto

    def calcular_status(self, faturas):
        atrasadas = 0

        for f in faturas:
            if not f.paga and f.data_vencimento:
                from django.utils import timezone
                if timezone.now().date() > f.data_vencimento:
                    atrasadas += 1

        if atrasadas >= 2:
            return "CRITICO"
        elif atrasadas == 1:
            return "RISCO"
        return "OK"


class DetalhesVenda(GroupRequiredMixin, DetailView):
    model = BaseArrecadacao
    template_name = "detalhes_venda.html"
    context_object_name = "venda"
    groups_required = ["Admin"]

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["faturas"] = Fatura.objects.filter(contrato=self.object.domicilios_nr_contrato).order_by("parcela")
        
        return contexto



# Views de vendedor
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
        contexto = super().get_context_data(**kwargs)
        vendedor = get_object_or_404(Vendedor, usuario=self.request.user)
        leads = list(
            Lead.objects.filter(vendedor=vendedor)
            .order_by("data_atribuicao", "id")
        )

        contratos_ids = [lead.contrato_id for lead in leads if lead.contrato_id]
        contratos = Contrato.objects.filter(contrato__in=contratos_ids)
        contratos_map = {
            c.contrato: c
            for c in contratos
        }

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
            lead.total_tentativas_cache = total_tentativas

            resto = total_tentativas % 3
            lead.tentativas_no_ciclo_cache = 0 if total_tentativas == 0 else (3 if resto == 0 else resto)

            contrato = contratos_map.get(lead.contrato_id)
            lead.contrato_cache = contrato
            coluna = self.get_slug_coluna(lead)

            colunas_map[coluna]["leads"].append(lead)
            colunas_map[coluna]["quantidade"] += 1
            colunas_map[coluna]["valor_total"] += getattr(contrato, "valor", 0) or 0

        # ordena dentro de cada coluna
        for coluna in colunas_map.values():
            coluna["leads"].sort(
                key=lambda l: (
                    l._prioridade_cache,  
                    l.data_atribuicao, 
                    l.id,  
                )
            )

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

