from django.db.models import Q

from contratos.models import AuditoriaCdr


def get_cdrs_do_lead(lead):
    return AuditoriaCdr.objects.filter(
        vendedor_id=lead.vendedor_id,
        contrato_numero=str(lead.contrato_id)
    ).order_by("-inicio", "-created_at")

def total_tentativas_lead(lead):
    return get_cdrs_do_lead(lead).count()

def existe_atendimento_lead(lead):
    return get_cdrs_do_lead(lead).filter(
        Q(atendimento__isnull=False) | Q(duracao__gt=0)
    ).exists()

def ultima_tentativa_lead(lead):
    return get_cdrs_do_lead(lead).first()

def pode_ligar_lead(lead):
    if lead.resolvido:
        return False
    return total_tentativas_lead(lead) < 3

