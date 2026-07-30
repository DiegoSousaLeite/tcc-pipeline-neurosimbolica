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

VERSAO_TABELA = "2026-07-29"
DATA_CONSULTA = "2026-07-29"
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
}


def preco_do_modelo(modelo: str) -> Preco | None:
    """Preço exato, ou None se o modelo não estiver tabelado.

    Sem chute por prefixo: um modelo fora da tabela precisa aparecer como custo
    zero e ser notado, e não ser silenciosamente cobrado ao preço de um vizinho
    de nome parecido.
    """
    return TABELA.get(modelo)


def custo_usd(modelo: str, tokens_entrada: int, tokens_saida: int) -> float:
    """Custo estimado de uma chamada, em USD."""
    preco = preco_do_modelo(modelo)
    if preco is None:
        return 0.0
    return (tokens_entrada / 1_000_000 * preco.entrada_por_1m
            + tokens_saida / 1_000_000 * preco.saida_por_1m)


def tabela_para_manifesto(modelos) -> dict:
    """Recorte da tabela para os modelos de uma rodada, pronto para o manifesto."""
    return {
        "versao_tabela": VERSAO_TABELA,
        "data_consulta": DATA_CONSULTA,
        "fontes": FONTES,
        "precos": {
            m: {"entrada_por_1m_usd": TABELA[m].entrada_por_1m,
                "saida_por_1m_usd": TABELA[m].saida_por_1m}
            for m in modelos if m in TABELA
        },
        "modelos_sem_preco": [m for m in modelos if m not in TABELA],
    }
