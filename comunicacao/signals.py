from django.db.models.signals import post_save
from django.dispatch import receiver

from contratos.models import AuditoriaCdr
from core.models import Lead


@receiver(post_save, sender=AuditoriaCdr)
def sincronizar_lead_apos_nova_ligacao(sender, instance, created, **kwargs):
    if not created:
        return

    if not instance.vendedor_id or not instance.contrato_numero:
        return

    lead = (
        Lead.objects
        .filter(
            vendedor__usuario_id=instance.vendedor_id,
            contrato_id=instance.contrato_numero,
        )
        .first()
    )

    if not lead:
        return

    lead.sincronizar_status_por_tentativas()