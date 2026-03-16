from datetime import timedelta
from django.utils import timezone


def calcular_score_contrato(contrato):
    hoje = timezone.now().date()
    seis_meses = hoje - timedelta(days=180)
    um_ano = hoje - timedelta(days=365)
    dois_anos = hoje - timedelta(days=730)
    tres_anos = hoje - timedelta(days=1095)

    status = str(getattr(contrato, "status", "") or "").upper()
    valor = getattr(contrato, "valor", 0) or 0
    devedor = getattr(contrato, "devedor", 0) or 0
    cancelamento = getattr(contrato, "cancelamento", None)

    if cancelamento and hasattr(cancelamento, "date"):
        cancelamento = cancelamento.date()

    score_status = 0
    if status == "ATIVO":
        if devedor == 0:
            score_status = 35
        elif devedor <= 100:
            score_status = 20
        else:
            score_status = -20

    elif status == "CANCELADO":
        if devedor > 0:
            score_status = -25
        elif cancelamento:
            if cancelamento <= um_ano:
                score_status = 30
            else:
                score_status = 10

    score_valor = 0
    if valor >= 200:
        score_valor = 20
    elif valor >= 120:
        score_valor = 15
    elif valor >= 80:
        score_valor = 10
    elif valor > 0:
        score_valor = 5

    score_divida = 0
    if devedor == 0:
        score_divida = 15
    elif devedor <= 100:
        score_divida = 5
    elif devedor <= 300:
        score_divida = -10
    else:
        score_divida = -20

    score_cancelamento = 0
    if status == "CANCELADO" and cancelamento:
        if cancelamento > seis_meses:
            score_cancelamento = 0
        elif cancelamento > um_ano:
            score_cancelamento = 4
        elif cancelamento > dois_anos:
            score_cancelamento = 8
        elif cancelamento > tres_anos:
            score_cancelamento = 12
        else:
            score_cancelamento = 15

    score_total = score_status + score_valor + score_divida + score_cancelamento
    score_total = max(0, min(100, score_total))

    return {
        "score_total": score_total,
        "score_status": score_status,
        "score_valor": score_valor,
        "score_divida": score_divida,
        "score_cancelamento": score_cancelamento,
    }