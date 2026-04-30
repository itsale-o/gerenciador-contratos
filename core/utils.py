import calendar
import holidays
import requests
from datetime import date, datetime

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import HttpResponse, JsonResponse, StreamingHttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from .decorators import admin_required
from .models import Cliente, Lead, Vendedor
from contratos.models import ClaroEndereco, AuditoriaCdr



# Define o ramal do usuário como None após a expiração da sessão/logout
def limpar_ramal_usuario(user):
    if not user:
        return
    
    vendedor = getattr(user, "perfil_vendedor", None)

    if vendedor and vendedor.ramal is not None:
        vendedor.ramal = None
        vendedor.ultimo_acesso = timezone.now()
        vendedor.save(update_fields=["ramal", "ultimo_acesso"])


# Normaliza as abreviações de nomes de ruas para fazer a busca dinâmica
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


# Cria um cliente quando um lead é convertido em venda
def criar_cliente(lead):
    if lead.status != "venda":
        return None

    contrato = lead.get_contrato()
    if not contrato:
        return None

    documento = (contrato.doc or "").strip()
    if not documento:
        return None

    cliente, criado = Cliente.objects.get_or_create(
        documento=documento,
        defaults={
            "nome": contrato.nome or "",
            "registro": contrato.registro or "",
            "cep": contrato.cep or "",
            "logradouro": contrato.endereco or "",
            "bairro": contrato.bairro or "",
            "cidade": contrato.cidade or "",
            "uf": contrato.uf or "",
            "celular1": contrato.celular1 or "",
            "celular2": contrato.celular2 or "",
            "telefone1": contrato.telefone1 or "",
            "telefone2": contrato.telefone2 or "",
        }
    )

    return cliente


# Busca os ramais livres com a API
def buscar_ramais_disponiveis():
    url = f"{settings.PABX_API_URL}/ramais_disponiveis"

    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()

        ramais = [
            item["ramal"]
            for item in data.get("ramais_disponiveis", [])
            if item.get("registrado") and not item.get("ocupado")
        ]

        return {
            "sucesso": True,
            "total": data.get("total", 0),
            "ramais": ramais
        }
    except requests.RequestException:
        return {
            "sucesso": False,
            "total": 0,
            "ramais": ramais,
            "erro": "Não foi possível consultar os ramais disponíveis no momento."
        }


# Lista os ramais disponíveis
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


# Redireciona o usuário baseado em qual grupo pertence
@login_required
def dashboard_redirect(request):
    user = request.user

    if user.groups.filter(name="Admin").exists():
        return redirect("core:dashboard_admin")
    
    if user.groups.filter(name="Vendedor").exists():
        return redirect("core:dashboard_vendedor")
    
    return redirect("login")


# Carrega o template com os bairros filtrados
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


# Busca a data da última ligação com o cliente
def parse_ultima_chamada_data(ultima_chamada):
    if not ultima_chamada:
        return None

    try:
        return datetime.strptime(ultima_chamada, "%H:%M:%S %d/%m/%Y").date()
    except ValueError:
        return None


# Busca as estatísticas dos vendedores com a API
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


# Dados de vendas fictícios
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


# Define o ramal para o vendedor
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


# Faz o download das gravações das ligações
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


# Atribui vários leads a um vendedor
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


# Salva o status dos leads
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


# Altera o status do lead
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


def dias_uteis_no_mes(ano, mes, dia_atual):
    feriados = holidays.Brazil(years=ano, subdiv="SP")

    total = 0
    restantes = 0

    _, ultimo_dia = calendar.monthrange(ano, mes)

    for dia in range(1, ultimo_dia + 1):
        d = date(ano, mes, dia)

        if d.weekday() < 5 and d not in feriados:
            total += 1

            if dia >= dia_atual:  
                restantes += 1

    passados = total - restantes

    return {
        "total": total,
        "restantes": restantes,
        "passados": passados
    }