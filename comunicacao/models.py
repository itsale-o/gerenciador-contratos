from django.db import models

# class SessaoLigacao(models.Model):
#     STATUS_CHAMADA = [
#         ("em_andamento", "Em Andamento"),
#         ("atendida", "Atendida"),
#         ("sem_resposta", "Sem Resposta"),
#         ("falha", "Falha"),
#         ("parcial", "Parcial")
#     ]

#     contrato_id = models.IntegerField(db_index=True)
#     vendedor = models.ForeignKey("core.Vendedor", on_delete=models.PROTECT)
#     status = models.CharField(max_length=50, choices=STATUS_CHAMADA, default="em_andamento")
#     numero_atendido = models.CharField(max_length=20, blank=True, null=True)
#     tentativa_atendida = models.PositiveSmallIntegerField(blank=True, null=True)
#     criado_em = models.DateTimeField(auto_now_add=True)
#     finalizad_em = models.DateTimeField(blank=True, null=True)

#     class Meta:
#         verbose_name_plural = "Sessões de Ligação"


class TentativaContato(models.Model):
    STATUS_CHOICES = [
        ("pendente", "Pendente"),
        ("atendida", "Atendida"),
        ("sem_resposta", "Sem resposta"),
        ("ocupado", "Ocupado"),
        ("falha", "Falha"),
        ("cancelada", "Cancelada"),
        ("desconhecido", "Desconhecido"),
    ]

    lead = models.ForeignKey("core.Lead", on_delete=models.CASCADE, related_name="tentativas")
    vendedor = models.ForeignKey("core.Vendedor", on_delete=models.SET_NULL, null=True, blank=True)

    uuid = models.CharField(max_length=64, unique=True)
    ramal = models.CharField(max_length=20, blank=True, null=True)
    numero_discado = models.CharField(max_length=20, blank=True, null=True)

    iniciada_em = models.DateTimeField(blank=True, null=True)
    atendida_em = models.DateTimeField(blank=True, null=True)
    finalizada_em = models.DateTimeField(blank=True, null=True)

    duracao = models.IntegerField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pendente")

    hangup_text = models.CharField(max_length=50, blank=True, null=True)
    hangup_code = models.IntegerField(blank=True, null=True)
#     gravacao = models.CharField(max_length=255, blank=True, null=True)

#     observacao = models.TextField(blank=True, null=True)
#     criada_em = models.DateTimeField(auto_now_add=True)
#     atualizada_em = models.DateTimeField(auto_now=True)

#     class Meta:
#         ordering = ["-criada_em"]
