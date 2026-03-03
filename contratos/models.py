from django.db import models


class Contrato(models.Model):
    contrato = models.IntegerField(db_column='Contrato', primary_key=True)  # Field name made lowercase.
    cid = models.CharField(db_column='CID', max_length=255, blank=True, null=True)  # Field name made lowercase.
    status = models.CharField(db_column='Status', max_length=255, blank=True, null=True)  # Field name made lowercase.
    valor = models.DecimalField(db_column='Valor', max_digits=20, decimal_places=2, blank=True, null=True)  # Field name made lowercase.
    devedor = models.DecimalField(db_column='Devedor', max_digits=20, decimal_places=2, blank=True, null=True)  # Field name made lowercase.
    produto = models.CharField(db_column='Produto', max_length=255, blank=True, null=True)  # Field name made lowercase.
    velocidade = models.CharField(db_column='Velocidade', max_length=255, blank=True, null=True)  # Field name made lowercase.
    ativacao = models.DateField(db_column='Ativacao', blank=True, null=True)  # Field name made lowercase.
    registro = models.CharField(db_column='Registro', max_length=255, blank=True, null=True)  # Field name made lowercase.
    doc = models.CharField(db_column='DOC', max_length=255, blank=True, null=True)  # Field name made lowercase.
    nome = models.CharField(db_column='NOME', max_length=255, blank=True, null=True)  # Field name made lowercase.
    unidade = models.CharField(db_column='Unidade', max_length=255, blank=True, null=True)  # Field name made lowercase.
    cancelamento = models.DateField(db_column='Cancelamento', blank=True, null=True)  # Field name made lowercase.
    motivo_cancelamento = models.CharField(db_column='MotivoCancelamento', max_length=800, blank=True, null=True)  # Field name made lowercase.
    endereco = models.CharField(db_column='Endereco', max_length=255, blank=True, null=True)  # Field name made lowercase.
    numero = models.CharField(db_column='Numero', max_length=255, blank=True, null=True)  # Field name made lowercase.
    complemento = models.CharField(db_column='Complemento', max_length=255, blank=True, null=True)  # Field name made lowercase.
    bairro = models.CharField(db_column='Bairro', max_length=255, blank=True, null=True)  # Field name made lowercase.
    cidade = models.CharField(db_column='Cidade', max_length=255, blank=True, null=True)  # Field name made lowercase.
    uf = models.CharField(db_column='UF', max_length=255, blank=True, null=True)  # Field name made lowercase.
    cep = models.CharField(db_column='CEP', max_length=255, blank=True, null=True)  # Field name made lowercase.
    cadastro = models.DateField(db_column='Cadastro', blank=True, null=True)  # Field name made lowercase.
    canal = models.CharField(db_column='CANAL', max_length=255, blank=True, null=True)  # Field name made lowercase.
    origem = models.CharField(db_column='ORIGEM', max_length=255, blank=True, null=True)  # Field name made lowercase.
    telefone1 = models.CharField(max_length=50, blank=True, null=True)
    telefone2 = models.CharField(max_length=50, blank=True, null=True)
    celular1 = models.CharField(max_length=50, blank=True, null=True)
    celular2 = models.CharField(max_length=50, blank=True, null=True)
    ultima_atualizacao = models.DateTimeField(blank=True, null=True)

    @property
    def status_badge_class(self):
        devedor = self.devedor or 0
        valor = self.valor or 0
        if self.status == "CANCELADO" and devedor > valor:
            return "bg-problema"
        
        mapa = {
            "ATIVO": "bg-ativo",
            "PORTADO": "bg-portado",
            "CANCELADO": "bg-cancelado",
            "SUSPENSÃO PARCIAL": "bg-suspenso",
            "BLOQUEADO": 'bg-bloqueado',
        }

        return mapa.get(self.status)

    class Meta:
        managed = False
        db_table = 'contratos'


class ClaroEndereco(models.Model):
    cidade = models.CharField(max_length=100, blank=True, null=True)
    bairro = models.CharField(max_length=100, blank=True, null=True)
    num_cep = models.CharField(max_length=8, blank=True, null=True)
    logradouro = models.CharField(max_length=200, blank=True, null=True)
    total = models.IntegerField(blank=True, null=True)
    livres = models.IntegerField(blank=True, null=True)
    penetracao = models.IntegerField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'claro_enderecos'