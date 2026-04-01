import logging
import requests

from django.db.models import Q
from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.http import require_GET

from contratos.models import AuditoriaChamadas


logger = logging.getLogger(__name__)


def criar_chamada(ramal, numero):
    url = f"{settings.PABX_API_URL}/criar_chamada?origem={ramal}&destino={numero}"

    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()

        try:
            data = response.json()
            print("JSON recebido:", data)
        except ValueError:
            print("Resposta não é JSON:", response.text)
            return None

        return data

    except requests.exceptions.Timeout:
        print("Timeout ao chamar API do PABX")
    except requests.exceptions.ConnectionError:
        print("Erro de conexão com API do PABX")
    except requests.exceptions.HTTPError as e:
        print("Erro HTTP:", e)
        print("Response:", response.text if 'response' in locals() else "sem response")
    except Exception as e:
        print("Erro inesperado:", e)

    return None


def extrair_uuid_call_id(call_id):
    if not call_id:
        return None
    
    partes = str(call_id).split("_")
    if len(partes) < 3:
        return None
    
    return partes[-1]


@require_GET
@require_GET
def acompanhar_chamada(request):
    uuid = request.GET.get("uuid")

    print("\n===== ACOMPANHAR CHAMADA =====")
    print("UUID recebido:", uuid)

    if not uuid:
        print("Erro: UUID não informado.")
        return JsonResponse({"erro": "UUID não informado."}, status=400)

    eventos_qs = (
        AuditoriaChamadas.objects
        .filter(uuid__startswith=uuid)
        .order_by("datahora")  # ou pelo campo de data/hora, se tiver um melhor
    )

    eventos = list(
        eventos_qs.values("id", "uuid", "evento")
    )

    print("Quantidade de eventos encontrados:", len(eventos))
    print("Eventos encontrados:", eventos)

    ultimo_evento = eventos[-1]["evento"] if eventos else None
    finalizada = ultimo_evento in ["FIM", "AGENTE_HANGUP", "AGENTE_NAO_ATENDEU"]

    print("Último evento:", ultimo_evento)
    print("Finalizada?:", finalizada)

    return JsonResponse({
        "uuid": uuid,
        "eventos": eventos,
        "ultimo_evento": ultimo_evento,
        "finalizada": finalizada,
    })



def derrubar_chamada(ramal):
    url = f"{settings.PABX_API_URL}/derrubar_ramal?ramal={ramal}"

    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print("Erro inesperado:", e)
        return None