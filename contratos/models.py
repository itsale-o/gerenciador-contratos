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

    def _formatar_telefone(self, numero):
        if not numero:
            return ""

        numeros = "".join(filter(str.isdigit, numero))

        if len(numeros) == 10:
            return f"({numeros[:2]}) {numeros[2:6]}-{numeros[6:]}"
        elif len(numeros) == 11:
            return f"({numeros[:2]}) {numeros[2:7]}-{numeros[7:]}"
        
        return numero

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
    
    @property
    def score_badge_class(self):
        score = getattr(self, "score_total", 0) or 0

        if score >= 90:
            return "badge-score-premium"
        elif score >= 70:
            return "badge-score-quente"
        elif score >= 50:
            return "badge-score-fraco"
        else:
            return "badge-score-ruim"

    @property
    def doc_formatado(self):
        if not self.doc:
            return ""
        
        numeros = "".join(filter(str.isdigit, self.doc))

        if len(numeros) == 11:
            return f"{numeros[:3]}.{numeros[3:6]}.{numeros[6:9]}-{numeros[9:]}"
        elif len(numeros) == 14:
            return f"{numeros[:2]}.{numeros[2:5]}.{numeros[5:8]}/{numeros[8:12]}-{numeros[12:]}"
        
        return self.doc

    @property
    def telefone1_formatado(self):
        return self._formatar_telefone(self.telefone1)

    @property
    def telefone2_formatado(self):
        return self._formatar_telefone(self.telefone2)

    @property
    def celular1_formatado(self):
        return self._formatar_telefone(self.celular1)

    @property
    def celular2_formatado(self):
        return self._formatar_telefone(self.celular2)

    class Meta:
        managed = False
        db_table = 'contratos'

    
    def __str__(self):
        return f"Contrato #{self.contrato}: {self.nome}"


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
        verbose_name_plural = "Endereços"
    
    def __str__(self):
        return f"CEP: {self.num_cep} | {self.cidade} | {self.bairro}"


class AuditoriaCdr(models.Model):
    uuid = models.CharField(primary_key=True, max_length=50)
    agente = models.CharField(max_length=20, blank=True, null=True) # ramal
    destino = models.CharField(max_length=20, blank=True, null=True) # número cliente
    inicio = models.DateTimeField(blank=True, null=True)
    atendimento = models.DateTimeField(blank=True, null=True)
    fim = models.DateTimeField(blank=True, null=True)
    duracao = models.IntegerField(blank=True, null=True)
    hangup_text = models.CharField(max_length=50, blank=True, null=True)
    hangup_code = models.IntegerField(blank=True, null=True)
    gravacao = models.CharField(max_length=255, blank=True, null=True)
    created_at = models.DateTimeField(blank=True, null=True)
    vendedor_id = models.IntegerField(blank=True, null=True)
    vendedor_nome = models.CharField(max_length=150, blank=True, null=True)
    contrato_numero = models.CharField(max_length=50, blank=True, null=True)
    contrato_doc = models.CharField(max_length=30, blank=True, null=True)
    contrato_nome = models.CharField(max_length=150, blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'auditoria_cdr'


# # Tabela de auditoria de ligações com dados mais legíveis
# class AuditoriaCdr(models.Model):
#     agente = models.CharField(max_length=255, blank=True, null=True)
#     destino = models.CharField(max_length=255, blank=True, null=True)
#     inicio = models.DateTimeField(blank=True, null=True)
#     atendimento = models.DateTimeField(blank=True, null=True)
#     fim = models.DateTimeField(blank=True, null=True)
#     duracao = models.IntegerField(blank=True, null=True)
#     hangup_text = models.CharField(max_length=255, blank=True, null=True)
#     hangup_cause = models.CharField(max_length=255, blank=True, null=True)
#     gravacao = models.CharField(max_length=500, blank=True, null=True)
#     created_at = models.DateTimeField(blank=True, null=True)
#     vendedor_id = models.IntegerField(blank=True, null=True)
#     vendedor_nome = models.CharField(max_length=255, blank=True, null=True)
#     contrato_numero = models.IntegerField(blank=True, null=True)
#     contrato_doc = models.CharField(max_length=255, blank=True, null=True)
#     contrato_nome = models.CharField(max_length=255, blank=True, null=True)

#     class Meta:
#         managed = False
#         db_table = 'auditoria_cdr'
#         verbose_name_plural = "Auditoria CDR"
    
#     def __str__(self):
#         return f"Ligação: {self.contrato_numero} - {self.contrato_nome}"


class AuditoriaChamadas(models.Model):
    uuid = models.CharField(max_length=64, blank=True, null=True)
    datahora = models.DateTimeField(blank=True, null=True)
    agente = models.CharField(max_length=20, blank=True, null=True)
    destino = models.CharField(max_length=20, blank=True, null=True)
    evento = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'auditoria_chamadas'