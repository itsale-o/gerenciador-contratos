import requests

from .models import Cliente
from contratos.models import Contrato


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
    if Cliente.objects.filter(lead=lead).exists():
        return
    
    contrato = lead.get_contrato()

    if not contrato:
        return
    
    Cliente.objects.create(
        lead=lead,
        vendedor=lead.vendedor,
        nome=contrato.nome,
        documento=contrato.doc,
        registro=contrato.registro,
        cep=contrato.cep,
        logradouro=contrato.endereco,
        bairro=contrato.bairro,
        cidade=contrato.cidade,
        uf=contrato.uf,
        celular1=contrato.celular1,
        celular2=contrato.celular2,
        telefone1=contrato.telefone1,
        telefone2=contrato.telefone2,
    )