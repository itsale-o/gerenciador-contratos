from django.conf import settings
from django.db import models


class Vendedor(models.Model):
    STATUS_VENDEDOR = [
        ("ativo", "Ativo"),
        ("bloqueado", "Bloqueado"),
        ("inativo", "Inativo"),
    ]

    usuario = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="perfil_vendedor")
    status = models.CharField(max_length=20, choices=STATUS_VENDEDOR, default="ativo")
    data_contratacao = models.DateField(blank=True, null=True)

    @property
    def badge_status(self):
        mapa = {
            "ativo": "bg-ativo",
            "bloqueado": "bg-bloqueado",
            "inativo": "bg-inativo"
        }

        return mapa.get(self.status)

    def __str__(self):
        return self.usuario.username


class Lead(models.Model):
    vendedor = models.ForeignKey("Vendedor", on_delete=models.CASCADE, related_name="leads")
    contrato_id = models.IntegerField(db_index=True)
    data_atribuicao = models.DateTimeField(auto_now_add=True)
    resolvido = models.BooleanField(default=False)
    resolvido_em = models.DateTimeField(blank=True, null=True)

    @property
    def resolvido_badge_class(self):
        mapa = {
            True: "bg-resolvido",
            False: "bg-pendente",
        }

        return mapa.get(self.resolvido)
    
    @property
    def resolvido_label(self):
        if self.resolvido:
            return "Concluído"
        return "Pendente"

    def get_contrato(self):
        from contratos.models import Contrato
        return Contrato.objects.filter(contrato=self.contrato_id).first()

    def __str__(self):
        return f"{self.vendedor.usuario.username} - {self.contrato_id}"
