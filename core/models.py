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
    ramal = models.CharField(max_length=10, blank=True, null=True)
    ultimo_acesso = models.DateTimeField(blank=True, null=True)

    class Meta:
        verbose_name_plural = "Vendedores"

    @property
    def badge_status(self):
        mapa = {
            "ativo": "bg-ativo",
            "bloqueado": "bg-bloqueado",
            "inativo": "bg-inativo"
        }

        return mapa.get(self.status)

    def __str__(self):
        return self.usuario.get_full_name()


class Cliente(models.Model):
    lead = models.OneToOneField("Lead", on_delete=models.SET_NULL, blank=True, null=True)
    vendedor = models.ForeignKey("Vendedor", on_delete=models.SET_NULL, blank=True, null=True)
    nome = models.CharField(max_length=250)
    documento = models.CharField(max_length=20)
    registro = models.CharField(max_length=2)
    cep = models.CharField(max_length=8)
    logradouro = models.CharField(max_length=250)
    bairro = models.CharField(max_length=250)
    cidade = models.CharField(max_length=250)
    uf = models.CharField(max_length=2)
    celular1 = models.CharField(max_length=15)
    celular2 = models.CharField(max_length=15)
    telefone1 = models.CharField(max_length=15)
    telefone2 = models.CharField(max_length=15)
    
    def __str__(self):
        return f"Cliente: {self.nome}"


class Lead(models.Model):
    STATUS_CONTATO = [
        ("desligou", "Cliente desligou"),
        ("nao_atendeu", "Cliente não atendeu"),
        ("ligar_mais_tarde", "Ligar mais tarde"),
        ("caro", "Cliente achou caro"),
        ("sem_interesse", "Cliente não tem interesse"),
        ("nao_virou_venda", "Cliente não virou venda"),
        ("numero_invalido", "Número inválido"),
        ("outros", "Outros"),
    ]

    STATUS_LEAD = [
        ("novo", "Novo"),
        ("em_contato", "Em Contato"),
        ("em_negociacao", "Em Negociação"),
        ("perdido", "Perdido"),
        ("venda", "Venda Realizada")
    ]

    vendedor = models.ForeignKey("Vendedor", on_delete=models.CASCADE, related_name="leads")
    contrato_id = models.IntegerField(db_index=True)
    data_atribuicao = models.DateTimeField(auto_now_add=True)
    resolvido = models.BooleanField(default=False)
    resolvido_em = models.DateTimeField(blank=True, null=True)
    contato_realizado = models.BooleanField(default=False)
    status = models.CharField(
        max_length=20,
        choices=STATUS_LEAD,
        default="novo",
        db_index=True
    )
    status_contato = models.CharField(
        max_length=30,
        choices=STATUS_CONTATO,
        blank=True,
        null=True
    )
    observacao = models.TextField(blank=True, null=True)
    proximo_contato = models.DateTimeField(blank=True, null=True)

    def get_status_display_formatado(self):
        if not self.status_contato:
            return "-"

        return self.status_contato.replace("_", " ").title()
    
    @property
    def status_lead(self):

        if not self.contato_realizado:
            return "novo"

        if self.contato_realizado and not self.status_contato:
            return "em_atendimento"

        return "respondido"

    @property
    def resolvido_badge_class(self):
        mapa = {
            True: "bg-resolvido",
            False: "bg-pendente",
        }

        return mapa.get(self.resolvido)
    
    @property
    def status_lead_label(self):

        mapa = {
            "novo": "Novo",
            "em_atendimento": "Em atendimento",
            "respondido": "Respondido",
        }

        return mapa[self.status_lead]
    
    @property
    def status_lead_badge(self):

        mapa = {
            "novo": "bg-novo",
            "em_atendimento": "bg-atendimento",
            "respondido": "bg-respondido",
        }

        return mapa[self.status_lead]
    

    def get_contrato(self):
        from contratos.models import Contrato
        return Contrato.objects.filter(contrato=self.contrato_id).first()

    def __str__(self):
        return f"{self.vendedor.usuario.username} - {self.contrato_id}"


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
        verbose_name_plural = "Score dos Leads"
        ordering = ["-score_total", "-atualizado_em"]

    def __str__(self):
        return f"Contrato {self.contrato_id} - Score {self.score_total}"