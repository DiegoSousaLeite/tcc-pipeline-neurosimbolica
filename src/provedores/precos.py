"""
precos.py — tabela de preços por 1M de tokens, versionada e datada.

O custo gravado no CSV é **derivado**, não medido: a API não devolve o valor
cobrado, só a contagem de tokens. Por isso a tabela precisa estar versionada no
repositório e citada no texto da monografia — sem a data de consulta, o número
de custo total não é auditável.

Atualizar preços aqui **muda resultados já gravados** se recalculados. Suba
`VERSAO_TABELA` ao mexer: o manifesto de cada rodada registra a versão usada.
"""
from dataclasses import dataclass

VERSAO_TABELA = "2026-09-30"
# Data da consulta da tabela ORIGINAL. Modelo acrescentado depois tem a sua em
# `CONSULTA_POR_MODELO`: dar a todos a data mais recente afirmaria que os preços
# antigos foram reconferidos, e não foram.
DATA_CONSULTA = "2026-07-29"
CONSULTA_POR_MODELO = {
    # developers.openai.com/api/docs/models/gpt-6-luna
    "gpt-6-luna": "2026-09-30",
}
FONTES = {
    "gemini": "https://ai.google.dev/gemini-api/docs/pricing",
    "openai": "https://platform.openai.com/docs/pricing",
}


@dataclass(frozen=True)
class Preco:
    """USD por 1 milhão de tokens."""

    entrada_por_1m: float
    saida_por_1m: float


# Tier pago. O tier grátis do Gemini não entra: ele tem custo zero e cota de 20
# req/dia, inviável para a matriz 2x2 (ver proposal, "Custo e cota de LLM").
TABELA: dict[str, Preco] = {
    "gemini-2.5-flash-lite": Preco(entrada_por_1m=0.10, saida_por_1m=0.40),
    "gemini-2.5-flash": Preco(entrada_por_1m=0.30, saida_por_1m=2.50),
    "gemini-2.5-pro": Preco(entrada_por_1m=1.25, saida_por_1m=10.00),
    "gpt-4o-mini": Preco(entrada_por_1m=0.15, saida_por_1m=0.60),
    "gpt-4o": Preco(entrada_por_1m=2.50, saida_por_1m=10.00),
    "gpt-4.1-mini": Preco(entrada_por_1m=0.40, saida_por_1m=1.60),
    # Preço padrão. O de lote é a metade, e fica no manifesto, não aqui: a
    # tabela é uma só para os dois modos de envio (spec `envio-em-lote`).
    "gpt-6-luna": Preco(entrada_por_1m=0.10, saida_por_1m=0.50),
}


# `modelo@variante` é o mesmo modelo com outra configuração de chamada (hoje,
# o esforço de raciocínio: `gpt-6-luna@low`). O fornecedor cobra pelo modelo
# base; os tokens de raciocínio já vêm somados aos de saída.
SEPARADOR_VARIANTE = "@"


def modelo_base(modelo: str) -> str:
    """'gpt-6-luna@low' -> 'gpt-6-luna'; nome sem variante volta igual."""
    return modelo.split(SEPARADOR_VARIANTE, 1)[0]


def preco_do_modelo(modelo: str) -> Preco | None:
    """Preço exato, ou None se o modelo não estiver tabelado.

    Sem chute por prefixo: um modelo fora da tabela precisa aparecer como custo
    zero e ser notado, e não ser silenciosamente cobrado ao preço de um vizinho
    de nome parecido. A única equivalência é a variante, que é o mesmo modelo.
    """
    return TABELA.get(modelo_base(modelo))


def custo_usd(modelo: str, tokens_entrada: int, tokens_saida: int) -> float:
    """Custo estimado de uma chamada, em USD."""
    preco = preco_do_modelo(modelo)
    if preco is None:
        return 0.0
    return (tokens_entrada / 1_000_000 * preco.entrada_por_1m
            + tokens_saida / 1_000_000 * preco.saida_por_1m)


def tabela_para_manifesto(modelos, modelos_locais=()) -> dict:
    """Recorte da tabela para os modelos de uma rodada, pronto para o manifesto.

    `modelos_locais` chega de fora (de `familia_do_modelo`, em `run_pipeline`) e
    não é inferido aqui por prefixo: a tabela de preços sabe de preços, não de
    namespaces de provedor.

    A distinção importa porque os dois casos custam zero por motivos opostos.
    Modelo comercial fora da tabela é anomalia a notar — alguém esqueceu de
    tabelar o preço. Modelo local é zero por construção, e listá-lo como "sem
    preço" daria a entender que faltou consultar algo.
    """
    locais = set(modelos_locais)
    return {
        "versao_tabela": VERSAO_TABELA,
        "data_consulta": DATA_CONSULTA,
        "data_consulta_por_modelo": {
            m: CONSULTA_POR_MODELO[modelo_base(m)] for m in modelos
            if modelo_base(m) in CONSULTA_POR_MODELO},
        "fontes": FONTES,
        "precos": {
            m: {"entrada_por_1m_usd": preco_do_modelo(m).entrada_por_1m,
                "saida_por_1m_usd": preco_do_modelo(m).saida_por_1m}
            for m in modelos if preco_do_modelo(m) is not None
        },
        "modelos_sem_preco": [m for m in modelos
                              if preco_do_modelo(m) is None and m not in locais],
        "modelos_locais_sem_custo": [m for m in modelos if m in locais],
    }
