from datetime import timedelta
import requests

from django.conf import settings
from django.utils import timezone

from comunicacao.models import TentativaLigacao, SessaoLigacao
from comunicacao.utils import mapear_status_por_cdr, listar_numeros_contato
from contratos.models import Cdr

def chamar_api_ligacao(ramal, numero):
    url = f"{settings.PABX_API_URL}?origem={ramal}&destino={numero}"

    response = requests.get(url, timeout=30)
    response.raise_for_status()

    return response.json()


def criar_tentativa(sessao, tipo_numero, numero, ordem):
    return TentativaLigacao.objects.create(
        sessao=sessao,
        tipo_numero=tipo_numero,
        numero=numero,
        ordem=ordem,
        status="em_andamento",
        iniciada_em=timezone.now()
    )


def registrar_retorno_api(tentativa, retorno):
    tentativa.ligacao_id = retorno.get("id")
    tentativa.status_api = retorno.get("resultado", {}.get("status"))
    tentativa.payload_api = retorno
    tentativa.save(update_fields=["ligacao_id", "status_api", "payload_api"])


def buscar_cdr_da_tentativa(tentativa):
    inicio = tentativa.iniciada_em - timedelta(seconds=10)
    fim = tentativa.iniciada_em + timedelta(minutes=2)

    return (
        Cdr.objects.using("asterisk")
        .filter(
            dst=tentativa.numero,
            calldate__range=(inicio, fim),
        )
        .order_by("calldate")
        .first()
    )


def atualizar_tentativa_com_cdr(tentativa, cdr):
    tentativa.disposition_cdr = cdr.disposition
    tentativa.billsec = cdr.billsec
    tentativa.duration = cdr.duration
    tentativa.uniqueid = cdr.uniqueid
    tentativa.linkedid = cdr.linkedid
    tentativa.status = mapear_status_por_cdr(
        cdr.disposition,
        cdr.billsec,
        cdr.duration,
    )
    tentativa.finalizada_em = timezone.now()

    tentativa.save(update_fields=[
        "disposition_cdr",
        "billsec",
        "duration",
        "uniqueid",
        "linkedid",
        "status",
        "finalizada_em",
    ])


def finalizar_sessao_com_sucesso(sessao, tentativa):
    sessao.status = "atendida"
    sessao.numero_atendido = tentativa.numero
    sessao.tentativa_atendida = tentativa.ordem
    sessao.finalizado_em = timezone.now()
    sessao.save(update_fields=[
        "status",
        "numero_atendido",
        "tentativa_atendida",
        "finalizado_em",
    ])


def finalizar_sessao_sem_resposta(sessao):
    sessao.status = "sem_resposta"
    sessao.finalizado_em = timezone.now()
    sessao.save(update_fields=["status", "finalizado_em"])


import time
from django.utils import timezone


def processar_sessao_ligacao(contrato, vendedor, ramal):
    sessao = SessaoLigacao.objects.create(
        contrato_id=contrato.contrato,
        vendedor=vendedor,
        status="em_andamento",
    )

    numeros = listar_numeros_contato(contrato)

    if not numeros:
        sessao.status = "falha"
        sessao.finalizado_em = timezone.now()
        sessao.save(update_fields=["status", "finalizado_em"])
        return sessao

    for ordem, (tipo_numero, numero) in enumerate(numeros, start=1):
        tentativa = criar_tentativa(sessao, tipo_numero, numero, ordem)

        try:
            retorno = chamar_api_ligacao(ramal, numero)
            registrar_retorno_api(tentativa, retorno)
        except Exception:
            tentativa.status = "falha"
            tentativa.finalizada_em = timezone.now()
            tentativa.save(update_fields=["status", "finalizada_em"])
            continue

        cdr = None
        for _ in range(12):  # até 1 minuto, consultando a cada 5s
            time.sleep(5)
            cdr = buscar_cdr_da_tentativa(tentativa)
            if cdr:
                break

        if not cdr:
            tentativa.status = "desconhecido"
            tentativa.finalizada_em = timezone.now()
            tentativa.save(update_fields=["status", "finalizada_em"])
            continue

        atualizar_tentativa_com_cdr(tentativa, cdr)

        if tentativa.status == "atendida":
            finalizar_sessao_com_sucesso(sessao, tentativa)
            return sessao

    finalizar_sessao_sem_resposta(sessao)
    return sessao