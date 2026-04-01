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
    nome = models.CharField(max_length=250)
    documento = models.CharField(max_length=20, unique=True)
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
        ("ligar_mais_tarde", "Cliente solicitou contato em outro momento"),
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
        ("venda", "Venda Realizada"),
        # pode até manter no banco por compatibilidade,
        # mas essa regra nova não depende mais dele
        ("lista_negra", "Lista Negra"),
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
    ciclos_resetados = models.PositiveIntegerField(default=0)

    def get_status_display_formatado(self):
        if not self.status_contato:
            return "-"
        return self.status_contato.replace("_", " ").title()

    @property
    def total_tentativas(self):
        from contratos.models import AuditoriaCdr

        return (
            AuditoriaCdr.objects.filter(
                vendedor_id=self.vendedor.usuario_id,
                contrato_numero=str(self.contrato_id)
            )
            .values("uuid")
            .distinct()
            .count()
        )

    @property
    def tentativas_no_ciclo(self):
        if self.total_tentativas == 0:
            return 0

        resto = self.total_tentativas % 3
        return 3 if resto == 0 else resto

    @property
    def ciclos_tentativas(self):
        return self.total_tentativas // 3

    @property
    def tem_novo_ciclo_para_resetar(self):
        return self.ciclos_tentativas > self.ciclos_resetados

    @property
    def prioridade_fila(self):
        """
        Vai para o fim da fila quando fechou um novo ciclo de 3 tentativas
        e esse ciclo ainda não foi processado.
        """
        if self.tem_novo_ciclo_para_resetar:
            return 1
        return 0

    @property
    def pode_ligar(self):
        return not self.resolvido

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
            "em_contato": "Em Contato",
            "em_negociacao": "Em Negociação",
            "perdido": "Lead perdido",
            "venda": "Lead Convertido"
        }
        return mapa[self.status]

    @property
    def status_lead_badge(self):
        mapa = {
            "novo": "badge-novo",
            "em_contato": "badge-contato",
            "em_negociacao": "badge-negociacao",
            "perdido": "badge-perdido",
            "venda": "badge-venda"
        }
        return mapa[self.status]

    def aplicar_reset_por_novo_ciclo_tentativas(self):
        """
        A cada novo bloco de 3 tentativas:
        - volta para status 'novo'
        - contato_realizado = False
        - status_contato = None
        - marca esse ciclo como já processado
        """
        ciclos_atuais = self.ciclos_tentativas
        campos = []

        if ciclos_atuais > self.ciclos_resetados:
            self.status = "novo"
            self.contato_realizado = False
            self.status_contato = None
            self.ciclos_resetados = ciclos_atuais

            campos.extend([
                "status",
                "contato_realizado",
                "status_contato",
                "ciclos_resetados",
            ])

        if campos:
            self.save(update_fields=campos)

        return bool(campos)

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