from datetime import timedelta
import logging
import requests

from django.db.models import Q
from django.conf import settings
from django.utils import timezone

from contratos.models import AuditoriaCdr

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
            print("❌ Resposta não é JSON:", response.text)
            return None

        return data

    except requests.exceptions.Timeout:
        print("⏱️ Timeout ao chamar API do PABX")
    except requests.exceptions.ConnectionError:
        print("🌐 Erro de conexão com API do PABX")
    except requests.exceptions.HTTPError as e:
        print("🔥 Erro HTTP:", e)
        print("Response:", response.text if 'response' in locals() else "sem response")
    except Exception as e:
        print("💥 Erro inesperado:", e)

    return None


def atualizar_status_contato_do_lead(lead):
    cdrs = AuditoriaCdr.objects.filter(
        vendedor_id=lead.vendedor_id,
        contrato_numero=str(lead.contrato_id)
    )

    houve_contato = cdrs.filter(
        Q(atendimento__isnull=False) | Q(duracao__gt=0)
    ).exists()

    campos_para_atualizar = []

    if lead.contato_realizado != houve_contato:
        lead.contato_realizado = houve_contato
        campos_para_atualizar.append("contato_realizado")

    if houve_contato and lead.status == "novo":
        lead.status = "em_contato"
        campos_para_atualizar.append("status")

    if campos_para_atualizar:
        lead.save(update_fields=campos_para_atualizar)

    return lead


def atualizar_lead_por_auditoria(lead):
    cdrs = AuditoriaCdr.objects.filter(
        vendedor_id=lead.vendedor_id,
        contrato_numero=str(lead.contrato_id)
    )

    houve_atendimento = cdrs.filter(
        Q(atendimento__isnull=False) | Q(duracao__gt=0)
    ).exists()

    campos = []

    if lead.contato_realizado != houve_atendimento:
        lead.contato_realizado = houve_atendimento
        campos.append("contato_realizado")

    if houve_atendimento and lead.status == "novo":
        lead.status = "em_contato"
        campos.append("status")

    if campos:
        lead.save(update_fields=campos)

    return lead