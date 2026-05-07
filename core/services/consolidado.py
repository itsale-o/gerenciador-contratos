from django.db.models import Sum
from django.utils import timezone

from core.models import Vendedor, ProducaoDiaria, MetaReceita
from core.services.service_vendas import *
from core.utils import dias_uteis_no_mes

def gerar_consolidado_mensal(mes=None, ano=None):
    hoje = timezone.localdate()
    mes = mes or hoje.month
    ano = ano or hoje.year
    resumo_datas = dias_uteis_no_mes(ano, mes, hoje.day)
    dias_restantes = resumo_datas["restantes"]

    vendedores = Vendedor.objects.all().order_by("usuario__first_name")
    producoes = (
        ProducaoDiaria.objects.filter(
            registro__data__year=ano,
            registro__data__month=mes
        )
        .values(
            "registro__vendedor_id",
            "tipo"
        )
        .annotate(
            total_volume=Sum("volume"),
            total_receita=Sum("receita")
        )
    )
    metas_mensais = (
        MetaReceita.objects.filter(
            ano=ano,
            mes=mes
        )
        .values(
            "vendedor_id",
            "meta_receita_mensal"
        )
    )

    mapa_metas_mensais = {
        m["vendedor_id"]: m["meta_receita_mensal"]
        for m in metas_mensais
    }

    mapa = montar_mapa_producoes(producoes)
    TIPOS = ["BL", "TV", "MOVEL", "LINHA"]
    dados = []
    totais = {tipo: {"volume": 0, "receita": 0} for tipo in TIPOS}
    totais.update({
        "somatorio_receita_real": 0,
        "somatorio_meta": 0,
    })

    for vendedor in vendedores:
        linha = criar_linha_base(vendedor)
        linha = aplicar_mapa_na_linha(linha, mapa)
        receita_real_total = calcular_receita_total(linha)
        meta_mensal = mapa_metas_mensais.get(vendedor.id, 0)
        gap = calcular_gap(meta_mensal, receita_real_total)
        porc_ating = calcular_percentual_atingimento(receita_real_total, meta_mensal)
        meta_diaria = calcular_meta_diaria(gap, dias_restantes)
        porc_ating_diario = calcular_percentual_atingimento(receita_real_total, meta_diaria)
        classe = definir_classe_atingimento(porc_ating)
        classe_perc_diario = definir_classe_atingimento(porc_ating_diario)

        if gap <= 0:
            classe_gap = "meta-batida"
        else:
            classe_gap = "atencao"

        linha["receita_real_total"] = receita_real_total
        linha["meta_mensal"] = meta_mensal
        linha["meta_diaria"] = round(meta_diaria, 2)
        linha["gap"] = gap
        linha["percentual_atingimento"] = round(porc_ating, 2)
        linha["percentual_atingimento_diario"] = round(porc_ating_diario, 2)
        linha["classe"] = classe
        linha["classe_perc_diario"] = classe_perc_diario
        linha["classe_gap"] = classe_gap

        for tipo in TIPOS:
            totais[tipo]["volume"] += (linha[tipo]["volume"])
            totais[tipo]["receita"] += (linha[tipo]["receita"])

        totais["somatorio_receita_real"] += (receita_real_total)

        totais["somatorio_meta"] += (
            meta_mensal
        )

        dados.append(linha)

    somatorio_gap = calcular_gap(
        totais["somatorio_meta"],
        totais["somatorio_receita_real"]
    )

    totais["somatorio_gap"] = somatorio_gap

    totais["somatorio_perc_ating"] = round(
        calcular_percentual_atingimento(
            totais["somatorio_receita_real"],
            totais["somatorio_meta"]
        ),
        2
    )

    totais["meta_diaria_total"] = round(
        calcular_meta_diaria(
            somatorio_gap,
            dias_restantes
        ),
        2
    )

    totais["somatorio_perc_ating_diario"] = round(
        calcular_percentual_atingimento(
            totais["somatorio_receita_real"],
            totais["meta_diaria_total"]
        ),
        2
    )

    return {
        "totais": totais,
        "dados": dados,
        "hoje": hoje,
        "dias_uteis_totais": resumo_datas["total"],
        "dias_uteis_passados": resumo_datas["passados"],
        "dias_uteis_restantes": dias_restantes,
    }

