import requests

from .models import TentativaLigacao
from contratos.models import Contrato

def criar_chamada(origem, destino):
    try:
        url = "https://claro.dominioz.com.br/api/criar_chamada"
        params = {
            "origem": origem,
            "destino": destino
        }
        response = requests.get(url, params=params, timeout=5)

        return response.json() if response.headers.get("Content-Type") == "application/json" else response.text
    except Exception:
        return {"erro": "falha na chamada"}


def consultar_status(id_ligacao):
    try:
        url = "https://claro.dominioz.com.br/api/status"
        params = {"id": id_ligacao}
        response = requests.get(url, params=params, timeout=5)
        data = response.json()

        return data["resultado"]["status"].lower()
    except Exception:
        return "failed"


def ligar_proximo_numero(tentativa):
    sessao = tentativa.sessao
    contrato = Contrato.objects.using("contratos").get(contrato=sessao.contrato_id)
    vendedor = sessao.vendedor

    telefones = [
        contrato.celular1,
        contrato.celular2,
        contrato.telefone1,
        contrato.telefone2
    ]

    telefones = [t for t in telefones if t]

    proxima_ordem = tentativa.ordem + 1

    if proxima_ordem > len(telefones):

        sessao.status = "failed"
        sessao.save()

        return

    telefone = telefones[proxima_ordem - 1]

    nova = TentativaLigacao.objects.create(
        sessao=sessao,
        numero_discado=telefone,
        ordem=proxima_ordem,
        ramal=vendedor.ramal,
        status="calling"
    )

    resposta = criar_chamada(vendedor.ramal, telefone)

    nova.id_ligacao_pabx = resposta.get("id")
    nova.save()


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