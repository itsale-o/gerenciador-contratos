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
    ramal = models.CharField(max_length=10, blank=True, null=True, default="000")

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


class SessaoLigacao(models.Model):
    STATUS_CHAMADA = [
        ("em_andamento", "Em Andamento"),
        ("completed", "Atendida"),
        ("failed", "Sem contato")
    ]

    contrato_id = models.IntegerField(db_index=True)
    vendedor = models.ForeignKey("Vendedor", on_delete=models.PROTECT)
    status = models.CharField(max_length=50, choices=STATUS_CHAMADA, default="em_andamento")
    criado_em = models.DateTimeField(auto_now_add=True)


class TentativaLigacao(models.Model):
    sessao = models.ForeignKey("SessaoLigacao", on_delete=models.PROTECT, related_name="tentativas")
    numero_discado = models.CharField(max_length=50)
    id_ligacao = models.CharField(
        max_length=50,
        null=True,
        blank=True
    )

    status = models.CharField(
        max_length=20,
        choices=[
            ("calling", "Chamando"),
            ("completed", "Atendida"),
            ("no_answer", "Sem resposta"),
            ("failed", "Falhou"),
        ],
        default="calling"
    )

    criado_em = models.DateTimeField(auto_now_add=True)


class ScoreLead(models.Model):
    contrato_id = models.IntegerField(unique=True, db_index=True)
    score_total = models.IntegerField(default=0)
    score_status = models.IntegerField(default=0)
    score_valor = models.IntegerField(default=0)
    score_divida = models.IntegerField(default=0)
    score_cancelamento = models.IntegerField(default=0)

    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Score de Lead"
        verbose_name_plural = "Scores de Leads"
        ordering = ["-score_total", "-atualizado_em"]

    def __str__(self):
        return f"Contrato {self.contrato_id} - Score {self.score_total}"