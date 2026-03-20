from django.db import models

class SessaoLigacao(models.Model):
    STATUS_CHAMADA = [
        ("em_andamento", "Em Andamento"),
        ("atendida", "Atendida"),
        ("sem_resposta", "Sem Resposta"),
        ("falha", "Falha"),
        ("parcial", "Parcial")
    ]

    contrato_id = models.IntegerField(db_index=True)
    vendedor = models.ForeignKey("core.Vendedor", on_delete=models.PROTECT)
    status = models.CharField(max_length=50, choices=STATUS_CHAMADA, default="em_andamento")
    numero_atendido = models.CharField(max_length=20, blank=True, null=True)
    tentativa_atendida = models.PositiveSmallIntegerField(blank=True, null=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    finalizad_em = models.DateTimeField(blank=True, null=True)

    class Meta:
        verbose_name_plural = "Sessões de Ligação"


class TentativaLigacao(models.Model):
    STATUS_TENTATIVA = [
        ("pendente", "Pendente"),
        ("em_andamento", "Em andamento"),
        ("atendida", "Atendida"),
        ("sem_resposta", "Sem resposta"),
        ("ocupado", "Ocupado"),
        ("falha", "Falha"),
        ("numero_invalido", "Número inválido"),
        ("desconhecido", "Desconhecido"),
    ]

    TIPO_NUMERO = [
        ("celular1", "Celular 1"),
        ("celular2", "Celular 2"),
        ("telefone1", "Telefone 1"),
        ("telefone2", "Telefone 2"),
    ]

    sessao = models.ForeignKey("SessaoLigacao", related_name="tentativas", on_delete=models.CASCADE)
    tipo_numero = models.CharField(max_length=20, choices=TIPO_NUMERO)
    numero = models.CharField(max_length=20)
    ordem = models.PositiveSmallIntegerField()
    ligacao_id = models.CharField(max_length=120, blank=True, null=True)   # id da API
    uniqueid = models.CharField(max_length=150, blank=True, null=True)     # se você conseguir obter
    linkedid = models.CharField(max_length=150, blank=True, null=True)     # se você conseguir obter
    status = models.CharField(max_length=20, choices=STATUS_TENTATIVA, default="pendente")
    status_api = models.CharField(max_length=50, blank=True, null=True)
    disposition_cdr = models.CharField(max_length=50, blank=True, null=True)
    billsec = models.PositiveIntegerField(blank=True, null=True)
    duration = models.PositiveIntegerField(blank=True, null=True)
    payload_api = models.JSONField(blank=True, null=True)
    detalhes_cel = models.JSONField(blank=True, null=True)
    iniciada_em = models.DateTimeField(blank=True, null=True)
    finalizada_em = models.DateTimeField(blank=True, null=True)

    class Meta:
        verbose_name_plural = "Tentativas de Ligação"
