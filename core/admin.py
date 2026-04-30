from django.contrib import admin

from .models import *

admin.site.register(Lead)
admin.site.register(Vendedor)
admin.site.register(Cliente)
admin.site.register(ScoreLead)
admin.site.register(Fatura)
admin.site.register(RegistroVenda)
admin.site.register(ProducaoDiaria)
admin.site.register(MetaReceita)