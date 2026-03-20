from django.contrib.auth.signals import user_logged_out
from django.dispatch import receiver
from django.utils import timezone


@receiver(user_logged_out)
def limpar_ramal_no_logout(sender, request, user, **kwargs):
    vendedor = getattr(user, "perfil_vendedor", None)

    if vendedor:
        vendedor.ramal = None
        vendedor.ultimo_acesso = timezone.now()
        vendedor.save(update_fields=["ramal", "ultimo_acesso"])