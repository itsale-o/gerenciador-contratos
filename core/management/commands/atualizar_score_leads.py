from django.conf import settings
from django.core.management.base import BaseCommand

from contratos.models import Contrato, ClaroEndereco
from core.models import ScoreLead
from core.services.score import calcular_score_contrato


class Command(BaseCommand):
    help = "Calcula e salva os scores dos contratos em lotes"

    def add_arguments(self, parser):
        parser.add_argument(
            "--lote",
            type=int,
            default=100,
            help="Quantidade de contratos processados por lote"
        )
        parser.add_argument(
            "--max-lotes",
            type=int,
            default=None,
            help="Número máximo de lotes a processar nesta execução"
        )
        parser.add_argument(
            "--cidade",
            type=str,
            help="Filtra os contratos por cidade"
        )
        parser.add_argument(
            "--bairro",
            type=str,
            help="Filtra os contratos por bairro"
        )
        parser.add_argument(
            "--todas-cidades",
            action="store_true",
            help="Processa automaticamente uma cidade por vez com base na tabela ClaroEndereco"
        )

    def get_scorelead_manager(self):
        if getattr(settings, "SCORELEAD_SAME_DATABASE", False):
            return ScoreLead.objects.using("contratos")
        return ScoreLead.objects

    def get_cidades_claroendereco(self):
        return (
            ClaroEndereco.objects.using("contratos")
            .exclude(cidade__isnull=True)
            .exclude(cidade__exact="")
            .values_list("cidade", flat=True)
            .distinct()
            .order_by("cidade")
        )

    def get_queryset_contratos(self, cidade=None, bairro=None):
        queryset = (
            Contrato.objects.using("contratos")
            .only(
                "contrato",
                "status",
                "valor",
                "devedor",
                "cancelamento",
                "cidade",
                "bairro",
            )
            .order_by("contrato")
        )

        if cidade:
            queryset = queryset.filter(cidade=cidade)

        if bairro:
            queryset = queryset.filter(bairro=bairro)

        return queryset

    def processar_lote(self, contratos, scorelead_manager):
        ids_contratos = [contrato.contrato for contrato in contratos]

        ids_existentes = set(
            scorelead_manager.filter(
                contrato_id__in=ids_contratos
            ).values_list("contrato_id", flat=True)
        )

        criados = 0
        pulados = 0
        erros = 0

        for contrato in contratos:
            if contrato.contrato in ids_existentes:
                pulados += 1
                continue

            try:
                dados_score = calcular_score_contrato(contrato)

                scorelead_manager.create(
                    contrato_id=contrato.contrato,
                    **dados_score
                )
                criados += 1

            except Exception as e:
                erros += 1
                self.stdout.write(
                    self.style.ERROR(
                        f"Erro ao processar contrato {contrato.contrato}: {e}"
                    )
                )

        return criados, pulados, erros

    def processar_queryset(self, queryset, scorelead_manager, lote, max_lotes, cidade_label=None, bairro_label=None):
        total_criados = 0
        total_pulados = 0
        total_erros = 0
        lotes_processados = 0
        buffer = []

        if cidade_label:
            self.stdout.write(self.style.NOTICE(f"Cidade: {cidade_label}"))

        if bairro_label:
            self.stdout.write(self.style.NOTICE(f"Bairro: {bairro_label}"))

        for contrato in queryset.iterator(chunk_size=lote):
            buffer.append(contrato)

            if len(buffer) >= lote:
                criados, pulados, erros = self.processar_lote(buffer, scorelead_manager)

                total_criados += criados
                total_pulados += pulados
                total_erros += erros
                lotes_processados += 1

                self.stdout.write(
                    self.style.SUCCESS(
                        f"Lote {lotes_processados} concluído | "
                        f"criados={criados} | pulados={pulados} | erros={erros}"
                    )
                )

                buffer = []

                if max_lotes is not None and lotes_processados >= max_lotes:
                    self.stdout.write(
                        self.style.WARNING("Limite máximo de lotes atingido. Encerrando este bloco.")
                    )
                    break

        else:
            if buffer and (max_lotes is None or lotes_processados < max_lotes):
                criados, pulados, erros = self.processar_lote(buffer, scorelead_manager)

                total_criados += criados
                total_pulados += pulados
                total_erros += erros
                lotes_processados += 1

                self.stdout.write(
                    self.style.SUCCESS(
                        f"Lote final {lotes_processados} concluído | "
                        f"criados={criados} | pulados={pulados} | erros={erros}"
                    )
                )

        return {
            "lotes_processados": lotes_processados,
            "criados": total_criados,
            "pulados": total_pulados,
            "erros": total_erros,
        }

    def handle(self, *args, **options):
        lote = options["lote"]
        max_lotes = options["max_lotes"]
        cidade = options.get("cidade")
        bairro = options.get("bairro")
        todas_cidades = options.get("todas_cidades")

        if lote <= 0:
            self.stdout.write(
                self.style.ERROR("O valor de --lote deve ser maior que 0.")
            )
            return

        if max_lotes is not None and max_lotes <= 0:
            self.stdout.write(
                self.style.ERROR("O valor de --max-lotes deve ser maior que 0.")
            )
            return

        if cidade and todas_cidades:
            self.stdout.write(
                self.style.ERROR("Use apenas --cidade ou --todas-cidades, não os dois juntos.")
            )
            return

        scorelead_manager = self.get_scorelead_manager()

        self.stdout.write(
            self.style.NOTICE(
                f"Iniciando processamento | lote={lote} | max_lotes={max_lotes}"
            )
        )

        total_geral_criados = 0
        total_geral_pulados = 0
        total_geral_erros = 0
        total_geral_lotes = 0

        if todas_cidades:
            cidades = self.get_cidades_claroendereco()

            for nome_cidade in cidades:
                self.stdout.write("")
                self.stdout.write(self.style.WARNING(f"Processando cidade: {nome_cidade}"))

                queryset = self.get_queryset_contratos(
                    cidade=nome_cidade,
                    bairro=bairro
                )

                resultado = self.processar_queryset(
                    queryset=queryset,
                    scorelead_manager=scorelead_manager,
                    lote=lote,
                    max_lotes=max_lotes,
                    cidade_label=nome_cidade,
                    bairro_label=bairro,
                )

                total_geral_criados += resultado["criados"]
                total_geral_pulados += resultado["pulados"]
                total_geral_erros += resultado["erros"]
                total_geral_lotes += resultado["lotes_processados"]

        else:
            queryset = self.get_queryset_contratos(cidade=cidade, bairro=bairro)

            resultado = self.processar_queryset(
                queryset=queryset,
                scorelead_manager=scorelead_manager,
                lote=lote,
                max_lotes=max_lotes,
                cidade_label=cidade,
                bairro_label=bairro,
            )

            total_geral_criados += resultado["criados"]
            total_geral_pulados += resultado["pulados"]
            total_geral_erros += resultado["erros"]
            total_geral_lotes += resultado["lotes_processados"]

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("Processamento finalizado."))
        self.stdout.write(f"Lotes processados: {total_geral_lotes}")
        self.stdout.write(f"Scores criados: {total_geral_criados}")
        self.stdout.write(f"Contratos pulados: {total_geral_pulados}")
        self.stdout.write(f"Erros: {total_geral_erros}")