import logging
import requests

from django.db.models import Q
from django.conf import settings


logger = logging.getLogger(__name__)


def criar_chamada(ramal, numero):
    url = f"{settings.PABX_API_URL}/criar_chamada?origem={ramal}&destino={numero}"

    print("Chamando API:", url)

    try:
        response = requests.get(url, timeout=10)

        print("Status code:", response.status_code)
        print("Response text:", response.text)

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


def derrubar_chamada(ramal):
    url = f"{settings.PABX_API_URL}/derrubar_ramal?ramal={ramal}"

    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print("Erro inesperado:", e)
        return None