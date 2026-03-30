from django.utils import timezone

from .models import Cliente


def limpar_ramal_usuario(user):
    if not user:
        return
    
    vendedor = getattr(user, "perfil_vendedor", None)

    if vendedor and vendedor.ramal is not None:
        vendedor.ramal = None
        vendedor.ultimo_acesso = timezone.now()
        vendedor.save(update_fields=["ramal", "ultimo_acesso"])

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