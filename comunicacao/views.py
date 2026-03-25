import re

from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_POST

from contratos.models import Contrato, AuditoriaCdr
from core.models import Vendedor, Lead
from .models import TentativaContato
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

    total_tentativas = (
        AuditoriaCdr.objects.filter(
            vendedor_id=vendedor.id,
            contrato_numero=str(contrato_id)
        )
        .values("uuid")
        .distinct()
        .count() 
    )

    total_tentativas_numero = TentativaContato.objects.filter(
        lead=lead,
        numero_discado=numero_escolhido
    ).count()

    if lead.resolvido:
        return JsonResponse(
            {"erro": "Este lead já está resolvido."},
            status=400
        )

    if total_tentativas_numero >= 6:
        if lead.status != "lista_negra":
            lead.status = "lista_negra"
            lead.save(update_fields=["status"])

        return JsonResponse(
            {"erro": "Este lead foi colocado em lista negra após 6 tentativas para este número."},
            status=400
        )

    if total_tentativas_numero >= 3:
        
        if lead.status != "em_contato":
            lead.status = "em_contato"
            lead.save(update_fields=["status"])

    ramal = vendedor.ramal

    if not ramal:
        return JsonResponse(
            {"erro": "O vendedor está sem ramal configurado"},
            status=400
        )
    
    resposta = criar_chamada(ramal, numero_escolhido)

    if not resposta or not resposta.get("id"):
        return JsonResponse(
            {"erro": "Não foi possível iniciar a ligação"},
            status=400
        )

    TentativaContato.objects.create(
        lead=lead,
        vendedor=vendedor,
        uuid=resposta.get("id"),
        ramal=ramal,
        numero_discado=numero_escolhido,
        status="pendente"
    )
    
    return JsonResponse({
        "status": "calling",
        "numero": numero_escolhido,
        "ligaçao_id": resposta.get("id")
    })




