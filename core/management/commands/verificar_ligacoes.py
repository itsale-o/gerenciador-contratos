from django.core.management.base import BaseCommand

from core.models import TentativaLigacao
from core.utils import consultar_status, ligar_proximo_numero

class Command(BaseCommand):
    def handle(self, *args, **kwargs):

        tentativas = TentativaLigacao.objects.filter(status="calling")

        for tentativa in tentativas:

            status = consultar_status(tentativa.id_ligacao_pabx)

            if status == "completed":

                tentativa.status = "completed"
                tentativa.save()

                tentativa.sessao.status = "completed"
                tentativa.sessao.save()

            elif status in ["noanswer", "busy", "failed"]:

                tentativa.status = status
                tentativa.save()

                ligar_proximo_numero(tentativa)