import requests

from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.http import require_GET


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


def consultar_status_da_chamada(call_id):
    url = f"{settings.PABX_API_URL}/status"
    params = {"id": call_id}

    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        return response.json(), None
    except requests.Timeout:
        return None, "Timeout ao consultar a API"
    except requests.HTTPError as e:
        return None, f"Erro HTTP na API: {e}"
    except requests.RequestException as e:
        return None, f"Erro ao consultar a API: {e}"
    except ValueError:
        return None, "Resposta inválida da API"


@require_GET
def acompanhar_chamada(request):
    call_id = request.GET.get("id")

    # print("\n===== ACOMPANHAR CHAMADA =====")
    # print("ID recebido: ", call_id)

    if not call_id:
        # print("Erro: ID da chamada não recebido.")
        return JsonResponse({
            "erro": "ID da chamada não recebido."
        }, status=400)
    
    data, erro = consultar_status_da_chamada(call_id)

    if erro:
        # print("Erro ao consultar status: ", erro)
        return JsonResponse({
            "erro": erro
        }, status=502)

    # print("Resposta da API:", data)
    
    detalhes = data.get("detalhes", {})
    estado = (data.get("estado") or "").lower()
    status_raw = (detalhes.get("status_raw") or "").strip()
    status_humano = detalhes.get("status_humano") or ""
    local = data.get("local")
    mensagem = data.get("mensagem") or ""
    finalizada = estado == "finished"

    # print("Resposta final da view:", {
    #     "estado": estado,
    #     "status_raw": status_raw,
    #     "finalizada": finalizada,
    # })

    return JsonResponse({
        "id": data.get("id"),
        "estado": estado,
        "local": local,
        "status_raw": status_raw,
        "status_humano": status_humano,
        "mensagem": mensagem,
        "tentativas": detalhes.get("tentativas", []),
        "total_tentativas": detalhes.get("total_tentativas", 0),
        "aguardando_retry": detalhes.get("aguardando_retry", False),
        "finalizada": finalizada,
        "detalhes": detalhes
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