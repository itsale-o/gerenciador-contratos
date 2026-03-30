from django.contrib.auth.signals import user_logged_out, user_logged_in
from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver
from django.utils import timezone

from core.models import Lead
from core.utils import criar_cliente, limpar_ramal_usuario


@receiver(user_logged_in)
def limpar_ramal_no_login(sender, request, user, **kwargs):
    limpar_ramal_usuario(user)


@receiver(user_logged_out)
def limpar_ramal_no_logout(sender, request, user, **kwargs):
    limpar_ramal_usuario(user)


@receiver(pre_save, sender=Lead)
def marcar_quando_virou_venda(sender, instance, **kwargs):
    instance._virou_venda = False

    if not instance.pk:
        return

    try:
        antigo = Lead.objects.get(pk=instance.pk)
    except Lead.DoesNotExist:
        return

    if antigo.status != "venda" and instance.status == "venda":
        instance._virou_venda = True


@receiver(post_save, sender=Lead)
def criar_cliente_apos_converter(sender, instance, created, **kwargs):
    if getattr(instance, "_virou_venda", False):
        criar_cliente(instance)
