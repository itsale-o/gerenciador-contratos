import re


from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_POST

from contratos.models import Contrato
from core.models import Vendedor, Lead
from .services.telefonia import *


def limpar_numero(numero):
    return re.sub(r"\D", "", str(numero or ""))


@require_POST
def contatar_cliente(request, contrato_id):
    contrato = get_object_or_404(Contrato, contrato=contrato_id)
    vendedor = get_object_or_404(Vendedor, usuario=request.user)
    lead = get_object_or_404(Lead, vendedor=vendedor, contrato_id=contrato_id)
    numero_escolhido = limpar_numero(request.POST.get("telefone"))

    if not vendedor.ramal:
        return JsonResponse(
            {
                "erro": "Vendedor sem ramal configurado"
            },
            status=400
        )
    
    if not numero_escolhido:
        return JsonResponse(
            {
                "erro": "Telefone não informado."
            },
            status=400
        )
    
    resposta = criar_chamada(vendedor.ramal, numero_escolhido)

    if not resposta or not resposta.get("id"):
        return JsonResponse(
            {
                "erro": "Não foi possível iniciar a ligação."
            },
            status=400
        )
    
    call_id = resposta["id"]
    uuid = extrair_uuid_call_id(call_id)

    return JsonResponse({
        "sucesso": True,
        "call_id": call_id,
        "uuid": uuid,
        "estado_inicial": resposta.get("status"),
    })


@require_POST
def cancelar_ligacao(request):
    vendedor = get_object_or_404(Vendedor, usuario=request.user)

    ramal = vendedor.ramal

    if not ramal:
        return JsonResponse(
            {"erro": "Nenhum ramal disponível para cancelar a ligação."},
            status=400
        )

    resposta = derrubar_chamada(ramal)

    if not resposta:
        return JsonResponse(
            {"erro": "Não foi possível cancelar a ligação."},
            status=400
        )

    return JsonResponse({
        "sucesso": True,
        "mensagem": "Ligação cancelada com sucesso.",
        "ramal": ramal,
        "resposta_api": resposta
    })


