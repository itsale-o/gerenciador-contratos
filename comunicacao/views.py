import re

from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_POST

from contratos.models import Contrato, AuditoriaCdr
from core.models import Vendedor, Lead
from .services.telefonia import *
from .utils import *

def limpar_numero(numero):
    return re.sub(r"\D", "", str(numero or ""))


@require_POST
def contatar_cliente(request, contrato_id):
    contrato = get_object_or_404(Contrato, contrato=contrato_id)
    vendedor = get_object_or_404(Vendedor, usuario=request.user)
    lead = get_object_or_404(Lead, vendedor=vendedor, contrato_id=contrato_id)

    numero_escolhido = limpar_numero(request.POST.get("telefone"))
    telefones_disponiveis = [
        contrato.celular1,
        contrato.celular2,
        contrato.telefone1,
        contrato.telefone2
    ]
    telefones_disponiveis = [limpar_numero(t) for t in telefones_disponiveis if t]

    if not telefones_disponiveis:
        return JsonResponse(
            {"erro": "Nenhum telefone disponível"},
            status=400
        )
    
    if not numero_escolhido:
        return JsonResponse(
            {"erro": "Nenhum telefone foi enviado"},
            status=400
        )
    
    if numero_escolhido not in telefones_disponiveis:
        return JsonResponse(
            {"erro": "Telefone inválido para este contrato"},
            status=400
        )

    if lead.resolvido:
        return JsonResponse(
            {"erro": "Este lead já está resolvido."},
            status=400
        )

    ramal = vendedor.ramal

    if not ramal:
        return JsonResponse(
            {"erro": "O vendedor está sem ramal configurado"},
            status=400
        )
    
    campos_para_atualizar = []

    if not lead.contato_realizado:
        lead.contato_realizado = True
        campos_para_atualizar.append("contato_realizado")
    
    if lead.status == "novo":
        lead.status = "em_contato"
        campos_para_atualizar.append("status")
    
    if campos_para_atualizar:
        lead.save(update_fields=campos_para_atualizar)

    resposta = criar_chamada(ramal, numero_escolhido)

    if not resposta or not resposta.get("id"):
        return JsonResponse(
            {"erro": "Não foi possível iniciar a ligação"},
            status=400
        )

    return JsonResponse({
        "status": "calling",
        "numero": numero_escolhido,
        "ligaçao_id": resposta.get("id")
    })

