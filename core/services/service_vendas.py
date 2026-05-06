# Função para montar o mapa de produções
def montar_mapa_producoes(producoes):
    mapa = {}

    for item in producoes:
        vendedor_id = item["registro__vendedor_id"]
        tipo = item["tipo"]

        if vendedor_id not in mapa:
            mapa[vendedor_id] = {}

        mapa[vendedor_id][tipo] = {
            "volume": item["total_volume"] or 0,
            "receita": item["total_receita"] or 0
        }
    
    return mapa


# Função para criar a linha base
def criar_linha_base(vendedor):
    return {
        "vendedor": vendedor,
        "vendedor_id": vendedor.id,
        "BL": {"volume": 0, "receita": 0},
        "TV": {"volume": 0, "receita": 0},
        "MOVEL": {"volume": 0, "receita": 0},
        "LINHA": {"volume": 0, "receita": 0},
    }


# Função para aplicardados do mapa na linha
def aplicar_mapa_na_linha(linha, mapa):
    vendedor_id = linha["vendedor_id"]

    if vendedor_id in mapa:
        for tipo, valores in mapa[vendedor_id].items():
            linha[tipo] = valores
    
    return linha


# Função para calcular a receita total
def calcular_receita_total(linha):
    return sum([
        linha["BL"]["receita"],
        linha["TV"]["receita"],
        linha["MOVEL"]["receita"],
        linha["LINHA"]["receita"],
    ])


# Função para calcular o gap
def calcular_gap(meta, realizado):
    gap = meta - realizado
    
    return max(gap, 0)


# Função para calcular o percentual de atingimento
def calcular_percentual_atingimento(realizado, meta):
    if meta > 0:
        return (realizado / meta) * 100
    
    return 0


# Função para calcular a meta diária
def calcular_meta_diaria(gap, dias_restantes):
    if dias_restantes > 0:
        return gap / dias_restantes
    
    return 0


# Função para definir a classe de atingimento
def definir_classe_atingimento(percentual):
    if percentual < 70:
        return "atencao"
    elif percentual < 100:
        return "no-caminho"
    return "meta-batida"