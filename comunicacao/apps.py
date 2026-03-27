from django.apps import AppConfig


class ComunicacaoConfig(AppConfig):
    name = 'comunicacao'
    verbose_name = "Comunicação"

    def ready(self):
        import comunicacao.signals
