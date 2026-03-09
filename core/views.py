from datetime import date

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import UserPassesTestMixin
from django.contrib.auth.models import User, Group
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Q, Sum, Sum, Avg
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

from .forms import FormCadastrarVendedor
from .models import Vendedor, Lead
from contratos.models import Contrato, ClaroEndereco
from .services.asterisk import make_call


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

    def get_queryset(self):
        cidade = self.request.GET.get("cidade")
        bairro = self.request.GET.get("bairro")
        rua = self.request.GET.get("rua")

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

        contexto["total_contratos"] = Contrato.objects.using("contratos").filter(bairro=bairro).count()

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
        contrato_id = request.POST.get("contrato")

        try:
            vendedor = Vendedor.objects.get(pk=vendedor_id)

            Lead.objects.create(
                vendedor=vendedor,
                contrato_id=contrato_id
            )

            return JsonResponse({
                "status": "ok",
                "mensagem": "Lead atribuída com sucesso."
            })
        except Exception as e:
            return JsonResponse({
                "status": "erro",
                "mensagem": str(e)
            })

































def telefones_do_contrato(contrato):
    telefones = [
        contrato.celular1,
        contrato.celular2,
        contrato.telefone1,
        contrato.telefone2
    ]

    return[t.strip() for t in telefones if t]

def ligar_contrato(ramal, contrato):

    telefones = telefones_do_contrato(contrato)

    if not telefones:
        return None

    numero = telefones[0]

    sucesso = make_call(ramal, numero)

    if sucesso:
        return numero
    
    return None

@login_required
def ligar_cliente(request, contrato_id):

    contrato = get_object_or_404(Contrato, contrato=contrato_id)

    vendedor = get_object_or_404(Vendedor, usuario=request.user)

    ramal = request.POST.get("ramal") or request.GET.get("ramal") or vendedor.ramal

    if not ramal:
        return JsonResponse({
            "status": "erro",
            "mensagem": "Ramal não informado"
        })

    numero = ligar_contrato(ramal, contrato)

    if not numero:
        return JsonResponse({
            "status": "erro",
            "mensagem": "Nenhum telefone disponível"
        })

    return JsonResponse({
        "status": "ok",
        "numero": numero,
        "ramal": ramal
    })