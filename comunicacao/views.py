from django.http import JsonResponse
from django.views.decorators.http import require_POST

from contratos.models import Contrato
from core.models import Lead, Vendedor

@require_POST
def contatar_cliente(request, contrato_id):
    contrato = Contrato.objects.using("contratos").get(contrato=contrato_id)
    vendedor = Vendedor.objects.get(usuario=request.user)

    lead = Lead.objects.get(
        vendedor=vendedor,
        contrato_id=contrato_id
    )

    lead.contato_realizado = True
    lead.save(update_fields=["contato_realizado"])

    ramal = 100
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