import time
from datetime import date, timedelta

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
from django.views.decorators.http import require_POST
from django.views.generic import ListView, TemplateView
from django.views.generic.detail import DetailView
from django.views.generic.edit import FormMixin
from django.views.decorators.http import require_POST

from .forms import FormCadastrarVendedor, FormEditarUsuarioVendedor, FormEditarVendedor
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

        contexto.update({
            # Contratos
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
        
        # Data de hoje
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

        contexto.update({
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

            messages.success(request, "Vendedor(a) cadastrado(a) com sucesso.")
            return self.form_valid(form)
        
        messages.error(request, "Erro ao cadastrar vendedor(a). Verifique os dados.")

        self.object_list = self.get_queryset()
        return self.form_invalid(form)


class DetalhesVendedor(UserPassesTestMixin, View):
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
        total_convertidos = leads.filter(status="venda").count()  # ajuste conforme seu modelo

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

    if observacao:
        lead.observacao = observacao

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

