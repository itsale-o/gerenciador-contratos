import time
from datetime import date, timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import UserPassesTestMixin
from django.contrib.auth.models import User, Group
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.db.models import Avg, Case, F, IntegerField, Q, Sum, Value, When, Count
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.http import JsonResponse
from django.urls import reverse_lazy
from django.utils import timezone
from django.utils.timezone import now
from django.views import View
from django.views.generic import ListView, TemplateView
from django.views.generic.detail import DetailView
from django.views.generic.edit import FormMixin
from django.views.decorators.http import require_POST

from .forms import FormCadastrarVendedor
from .models import Vendedor, Lead, SessaoLigacao, TentativaLigacao
from contratos.models import Contrato, ClaroEndereco
from .utils import criar_chamada


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

    def get_queryset(self):
        t0 = time.perf_counter()

        cidade = self.request.GET.get("cidade")
        bairro = self.request.GET.get("bairro")
        rua = self.request.GET.get("rua")

        t1 = time.perf_counter()
        print(f"[PERF] parâmetros: {t1 - t0:.4f}s")

        hoje = timezone.now().date()
        seis_meses = hoje - timedelta(days=180)
        um_ano = hoje - timedelta(days=365)
        dois_anos = hoje - timedelta(days=730)
        tres_anos = hoje - timedelta(days=1095)

        score_divida = Case(
            When(devedor=0, then=Value(40)),
            When(devedor__lte=100, then=Value(10)),
            When(devedor__gt=100, then=Value(-50)),
            default=Value(0),
            output_field=IntegerField()
        )

        score_cancelamento = Case(
            When(status="CANCELADO", cancelamento__lte=dois_anos, then=Value(40)),
            When(status="CANCELADO", cancelamento__lte=um_ano, then=Value(30)),
            When(status="CANCELADO", cancelamento__lte=seis_meses, then=Value(15)),
            When(status="CANCELADO", then=Value(5)),
            default=Value(0),
            output_field=IntegerField()
        )

        score_fidelidade = Case(
            When(ativacao__lte=tres_anos, then=Value(30)),
            When(ativacao__lte=dois_anos, then=Value(20)),
            When(ativacao__lte=um_ano, then=Value(10)),
            default=Value(0),
            output_field=IntegerField()
        )

        score_valor = Case(
            When(valor__gte=150, then=Value(25)),
            When(valor__gte=100, then=Value(15)),
            When(valor__gte=70, then=Value(10)),
            default=Value(0),
            output_field=IntegerField()
        )

        queryset = Contrato.objects.filter(
            cidade=cidade,
            bairro=bairro
        )

        if rua:
            termos = rua.split()
            filtro = Q()
            for t in termos:
                filtro &= Q(endereco__icontains=t)
            queryset = queryset.filter(filtro)

        t2 = time.perf_counter()
        print(f"[PERF] queryset base montado: {t2 - t1:.4f}s")

        queryset = queryset.annotate(
            score_divida=score_divida,
            score_cancelamento=score_cancelamento,
            score_fidelidade=score_fidelidade,
            score_valor=score_valor
        ).annotate(
            lead_score=(
                F("score_divida") +
                F("score_cancelamento") +
                F("score_fidelidade") +
                F("score_valor")
            )
        ).order_by("-lead_score", "endereco")

        t3 = time.perf_counter()
        print(f"[PERF] annotate/order_by montado: {t3 - t2:.4f}s")

        return queryset

    def get_context_data(self, **kwargs):
        t0 = time.perf_counter()

        contexto = super().get_context_data(**kwargs)

        t1 = time.perf_counter()
        print(f"[PERF] super().get_context_data: {t1 - t0:.4f}s")

        cidade = self.request.GET.get("cidade")
        bairro = self.request.GET.get("bairro")

        contratos = contexto["contratos"]
        contratos_ids_pagina = [c.contrato for c in contratos]

        contratos_atribuidos = set(
            Lead.objects.filter(contrato_id__in=contratos_ids_pagina)
            .values_list("contrato_id", flat=True)
        )

        t2 = time.perf_counter()
        print(f"[PERF] leads atribuídos: {t2 - t1:.4f}s")

        for c in contratos:
            score = c.lead_score

            if score >= 90:
                c.score_badge_class = "badge-score-premium"
            elif score >= 70:
                c.score_badge_class = "badge-score-quente"
            elif score >= 40:
                c.score_badge_class = "badge-score-bom"
            elif score >= 10:
                c.score_badge_class = "badge-score-fraco"
            else:
                c.score_badge_class = "badge-score-ruim"

            c.ja_atribuido = c.contrato in contratos_atribuidos

        t3 = time.perf_counter()
        print(f"[PERF] loop contratos: {t3 - t2:.4f}s")

        contexto["cidade"] = cidade
        contexto["bairro"] = bairro
        contexto["ruas"] = []

        contexto["vendedores"] = Vendedor.objects.all()
        contexto["total_contratos"] = Contrato.objects.using("contratos").filter(bairro=bairro).count()

        t4 = time.perf_counter()
        print(f"[PERF] restante contexto: {t4 - t3:.4f}s")
        print(f"[PERF] total get_context_data: {t4 - t0:.4f}s")

        return contexto


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

    lead.status_contato = status

    if observacao:
        lead.observacao = observacao

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

