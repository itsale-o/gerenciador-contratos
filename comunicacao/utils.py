import re
import requests


def mapear_status_por_cdr(disposition, billsec, duration):
    disposition = (disposition or "").upper()

    if billsec and billsec > 0:
        return "atendida"
    
    if disposition in {"ANSWERED"}:
        return "atendida"
    
    if disposition in {"BUSY"}:
        return "ocupado"
    
    if disposition in {"NO ANSWER", "NOANSWER"}:
        return "sem_resposta"
    
    if disposition in {"FAILED", "CONGESTION"}:
        return "falha"
    
    return "desconhecido"


def limpar_numero(numero):
    if not numero:
        return None
    
    numero = re.sub(r"\D", "", str(numero))

    if not numero:
        return None
    
    return None


def listar_numeros_contato(contrato):
    candidatos = [
        ("celular1", contrato.celular1),
        ("celular2", contrato.celular2),
        ("telefone1", contrato.telefone1),
        ("telefone2", contrato.telefone2)
    ]

    numeros = []
    vistos = set()

    for tipo, numero in candidatos:
        numero_limpo = limpar_numero(numero)

        if not numero_limpo:
            continue

        if numero_limpo in vistos:
            continue

        vistos.add(numero_limpo)
        numeros.append((tipo, numero_limpo))

    return numeros
