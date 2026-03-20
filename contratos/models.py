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


# Status final da ligação
class Cdr(models.Model):
    calldate = models.DateTimeField() # Quando a chamada começou
    clid = models.CharField(max_length=80)     
    src = models.CharField(max_length=80) # Origem
    dst = models.CharField(max_length=80) # Destino
    dcontext = models.CharField(max_length=80)
    channel = models.CharField(max_length=80) # Canal de origem
    dstchannel = models.CharField(max_length=80) # Canal de destino
    lastapp = models.CharField(max_length=80)
    lastdata = models.CharField(max_length=80)
    duration = models.IntegerField() # Duração total da chamada
    billsec = models.IntegerField() # Segundos efetivamente "em conversa" após o atendimento
    disposition = models.CharField(max_length=45) # Desfecho 
    amaflags = models.IntegerField()
    accountcode = models.CharField(max_length=20)
    uniqueid = models.CharField(max_length=32) # Identificador único do canal
    userfield = models.CharField(max_length=255)
    did = models.CharField(max_length=50)
    recordingfile = models.CharField(max_length=255)
    cnum = models.CharField(max_length=80)
    cnam = models.CharField(max_length=80)
    outbound_cnum = models.CharField(max_length=80)
    outbound_cnam = models.CharField(max_length=80)
    dst_cnam = models.CharField(max_length=80)
    linkedid = models.CharField(max_length=32) # Identificador que agrupa registros da mesma chamada lógica
    peeraccount = models.CharField(max_length=80)
    sequence = models.IntegerField()

    class Meta:
        managed = False
        db_table = 'cdr'
        verbose_name_plural = "Status Finais das Ligações"


# Linha do tempo dos eventos da chamada
class Cel(models.Model):
    eventtype = models.CharField(max_length=30) # Tipo do evento
    eventtime = models.DateTimeField() # Momento do evento
    cid_name = models.CharField(max_length=80)
    cid_num = models.CharField(max_length=80)
    cid_ani = models.CharField(max_length=80)
    cid_rdnis = models.CharField(max_length=80)
    cid_dnid = models.CharField(max_length=80)
    exten = models.CharField(max_length=80)
    context = models.CharField(max_length=80)
    channame = models.CharField(max_length=80) # Canal
    appname = models.CharField(max_length=80) # Aplicação usada
    appdata = models.CharField(max_length=240) # Dados usados
    amaflags = models.IntegerField()
    accountcode = models.CharField(max_length=20)
    uniqueid = models.CharField(max_length=32) 
    linkedid = models.CharField(max_length=32)
    peer = models.CharField(max_length=80)
    userdeftype = models.CharField(max_length=255)
    eventextra = models.CharField(max_length=255) # Informações adicionais (às vezes em JSON)
    userfield = models.CharField(max_length=255)

    class Meta:
        managed = False
        db_table = 'cel'