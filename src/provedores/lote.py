"""
lote.py — contrato da entrega EM LOTE, ao lado da síncrona (`base.py`).

A forma síncrona devolve o veredito na mesma chamada; a em lote devolve um
identificador e exige consulta depois. Os ciclos de vida não cabem na mesma
assinatura (D2 de `envio-em-lote-comercial`), e por isso `ProvedorLote` é um
protocolo à parte: `ProvedorLLM.avaliar` e `ProvedorHTTP.avaliar` não mudam.

O que precisa ser idêntico entre os dois modos NÃO mora aqui: o veredito sai de
`validar_resposta` e o custo de `precos.custo_usd`, os mesmos do síncrono. Aqui
fica só o que é próprio do lote — a chave de correlação, o desfecho de
expiração, os limites do fornecedor e a partição que os respeita.
"""
import logging
import time
from dataclasses import dataclass
from typing import Callable, Iterable, Optional, Protocol

import requests

from .base import (
    CODIGOS_TRANSITORIOS,
    ERROR,
    MAX_TENTATIVAS,
    RespostaLLM,
    espera_backoff,
    ler_retry_after,
)

log = logging.getLogger(__name__)

# Requisição que o fornecedor não processou dentro da janela do lote. NÃO é
# ERROR: ERROR é "o modelo respondeu e a resposta não passou na validação" (ou a
# esteira falhou ao falar com ele); EXPIRADO é "o modelo nunca viu isso". Somar
# os dois inflaria a taxa de erro do modelo com uma falha de esteira (D4).
EXPIRADO = "EXPIRADO"

# Separador da chave composta. Nenhum `ID_Caso` da população o contém (medido
# sobre os 2.328 casos em 2026-09-28), e `chave_lote` recusa o que contiver, para
# que a leitura de volta nunca seja ambígua.
SEPARADOR_CHAVE = "|"


def chave_lote(caso_id: str, modelo: str, tipo_prompt: str) -> str:
    """`custom_id` da requisição: a tripla do checkpoint, e nada além dela (D1).

    Com a chave de checkpoint como identificador, gravar veredito no caso
    errado deixa de ser representável: uma resposta sem chave válida não tem
    linha onde ser escrita. A ordem em que o fornecedor devolve as respostas
    passa a não importar.
    """
    partes = (caso_id, modelo, tipo_prompt)
    for p in partes:
        if not p or SEPARADOR_CHAVE in p:
            raise ValueError(f"Componente de chave inválido para o lote: {p!r}")
    return SEPARADOR_CHAVE.join(partes)


def ler_chave(chave: str) -> tuple[str, str, str]:
    """Inverso de `chave_lote`: `(ID_Caso, Modelo_LLM, Tipo_Prompt)`."""
    partes = chave.split(SEPARADOR_CHAVE)
    if len(partes) != 3 or not all(partes):
        raise ValueError(f"Chave de lote malformada: {chave!r}")
    return partes[0], partes[1], partes[2]


# ---------------------------------------------------------------------------
# Estados de um lote, normalizados entre fornecedores
# ---------------------------------------------------------------------------

PENDENTE = "PENDENTE"            # enfileirado ou em processamento
CONCLUIDO = "CONCLUIDO"
LOTE_EXPIRADO = "EXPIRADO"       # estourou a janela do fornecedor
FALHOU = "FALHOU"
CANCELADO = "CANCELADO"
NAO_ENCONTRADO = "NAO_ENCONTRADO"

ESTADOS_FINAIS = frozenset({CONCLUIDO, LOTE_EXPIRADO, FALHOU, CANCELADO})


class ErroLote(Exception):
    """Falha de operação do lote (submissão recusada, formato inesperado).

    Diferente de um veredito ERROR: aqui não há veredito a gravar, e a execução
    para para que o operador decida — reenviar custa, e o custo tem de ser
    escolhido, não automático.
    """


@dataclass(frozen=True)
class LimitesLote:
    """O que o fornecedor aceita por lote. Declarado pelo provedor (D7).

    `tokens_enfileirados` é o teto de tokens de ENTRADA na fila do modelo. No
    Gemini ele vale para a soma de todos os lotes ativos daquele modelo, e não
    por lote — por isso as partições são submetidas uma de cada vez
    (`src/envio_lote.py`), e não todas juntas.

    `caracteres_por_token` estima os tokens antes da submissão, quando o
    fornecedor ainda não contou nada. É deliberadamente pessimista (conta mais
    tokens do que haverá): errar para mais gera uma partição a mais; errar para
    menos gera um lote recusado.
    """

    tokens_enfileirados: int
    bytes_por_lote: int
    requisicoes_por_lote: Optional[int] = None
    caracteres_por_token: float = 3.0
    # Folga sobre os tetos: cobre o erro da estimativa de tokens e o envelope
    # JSON da submissão, que o medidor por requisição não vê.
    margem: float = 0.9


def estimar_tokens(prompt: str, limites: LimitesLote) -> int:
    return int(len(prompt) / limites.caracteres_por_token) + 1


class ProvedorLote(Protocol):
    """Interface mínima da entrega em lote que a pipeline conhece.

    `submeter` devolve um identificador sem bloquear à espera dos vereditos;
    `recuperar` devolve os vereditos associados à chave com que foram
    submetidos — nunca à posição. `localizar` acha pelo rótulo do cliente um
    lote cuja submissão pode ter acontecido sem que o identificador chegasse ao
    disco (D3).
    """

    modelo: str
    nome: str
    limites: LimitesLote
    # Fração descontada do preço de tabela no modo lote (0,5 nos três
    # fornecedores levantados). Vai para o manifesto, não para o CSV.
    desconto: float
    # Se o fornecedor cobra a requisição expirada. Quando não cobra, o custo
    # dela é zero por construção, e não por acaso de não haver tokens.
    cobra_expirada: bool

    def medir(self, chave: str, prompt: str) -> tuple[int, int]:
        """(tokens estimados, bytes) de uma requisição no formato do fornecedor."""
        ...

    def submeter(self, prompts: dict[str, str], rotulo: str) -> str:
        ...

    def estado(self, id_lote: str) -> str:
        ...

    def localizar(self, rotulo: str) -> Optional[str]:
        ...

    def recuperar(self, id_lote: str) -> dict[str, RespostaLLM]:
        ...


def get_com_repeticao(http, url: str, headers: dict, params=None,
                      timeout: int = 120, max_tentativas: int = MAX_TENTATIVAS,
                      dormir=time.sleep):
    """GET com repetição em falha transitória, para CONSULTAS de lote.

    Consultar não custa, então repetir é seguro — ao contrário de submeter,
    que nenhum provedor de lote repete sozinho. Devolve a resposta (inclusive
    4xx, que quem chama interpreta) ou levanta `ErroLote` esgotadas as
    tentativas.
    """
    ultimo = "erro desconhecido"
    for tentativa in range(1, max_tentativas + 1):
        retry_after = None
        try:
            resp = http.get(url, headers=headers, params=params, timeout=timeout)
        except requests.RequestException as e:
            ultimo = f"falha de rede: {type(e).__name__}"
        else:
            if resp.status_code not in CODIGOS_TRANSITORIOS:
                return resp
            ultimo = f"HTTP {resp.status_code}"
            retry_after = ler_retry_after(resp.headers)
        if tentativa < max_tentativas:
            dormir(espera_backoff(tentativa, retry_after))
    raise ErroLote(f"Consulta ao lote falhou após {max_tentativas} tentativas: "
                   f"{ultimo}")


# ---------------------------------------------------------------------------
# Partição por orçamento
# ---------------------------------------------------------------------------

def particionar(requisicoes: Iterable[tuple[str, str]], limites: LimitesLote,
                medir: Callable[[str, str], tuple[int, int]]) -> list[list[tuple[str, str]]]:
    """Parte `(chave, prompt)` em lotes que caibam nos limites, na ordem dada.

    Guloso e estável: a ordem de entrada é preservada dentro e entre as
    partições, e cada requisição cai em exatamente uma — a união das partições
    é a entrada, sem repetição nem omissão. Chave repetida é erro, porque
    significaria a mesma tripla submetida duas vezes (e paga duas vezes).

    O critério é o orçamento e não o braço: um corte por braço caberia hoje por
    coincidência, e deixaria de caber na primeira rodada maior (D7).
    """
    teto_tokens = int(limites.tokens_enfileirados * limites.margem)
    teto_bytes = int(limites.bytes_por_lote * limites.margem)
    teto_req = limites.requisicoes_por_lote

    particoes, atual = [], []
    tokens = bytes_ = 0
    vistas = set()
    for chave, prompt in requisicoes:
        if chave in vistas:
            raise ValueError(f"Chave repetida na submissão: {chave}")
        vistas.add(chave)
        t, b = medir(chave, prompt)
        if t > teto_tokens or b > teto_bytes:
            raise ErroLote(
                f"Requisição {chave} sozinha excede o limite do lote "
                f"({t} tokens estimados / {b} bytes; tetos {teto_tokens} / "
                f"{teto_bytes}).")
        cheia = (atual and (tokens + t > teto_tokens or bytes_ + b > teto_bytes
                            or (teto_req is not None and len(atual) >= teto_req)))
        if cheia:
            particoes.append(atual)
            atual, tokens, bytes_ = [], 0, 0
        atual.append((chave, prompt))
        tokens += t
        bytes_ += b
    if atual:
        particoes.append(atual)
    return particoes


# ---------------------------------------------------------------------------
# Correlação
# ---------------------------------------------------------------------------

def resposta_expirada(modelo: str, motivo: str = "") -> RespostaLLM:
    """Desfecho de requisição que o modelo nunca viu. Custo zero, sem tokens."""
    return RespostaLLM(
        veredito=EXPIRADO,
        justificativa=("Requisição expirada na janela do lote, sem "
                       f"processamento pelo modelo. {motivo}").strip(),
        modelo=modelo)


def correlacionar(submetidas: Iterable[str], recebidas: dict[str, RespostaLLM],
                  estado_final: str, modelo: str, cobra_expirada: bool = False,
                  ) -> tuple[dict[str, RespostaLLM], list[str]]:
    """Casa as respostas com as chaves submetidas. Devolve `(respostas, órfãs)`.

    - chave recebida que não foi submetida é **órfã**: nada é gravado para ela,
      e ela vai para o log como anomalia;
    - chave submetida sem resposta vira `EXPIRADO` se o lote expirou, e `ERROR`
      nos demais casos — um lote concluído que "perdeu" uma requisição é falha
      de esteira, não uma expiração;
    - resposta expirada não soma custo quando o fornecedor não cobra.
    """
    submetidas = list(submetidas)
    conjunto = set(submetidas)
    orfas = sorted(k for k in recebidas if k not in conjunto)
    for k in orfas:
        log.warning("    [ANOMALIA] resposta de lote com chave não submetida, "
                    "descartada: %s", k)

    respostas = {}
    for chave in submetidas:
        r = recebidas.get(chave)
        if r is None:
            if estado_final == LOTE_EXPIRADO:
                r = resposta_expirada(modelo)
            else:
                r = RespostaLLM(
                    veredito=ERROR,
                    justificativa=(f"Requisição ausente do resultado do lote "
                                   f"(estado final: {estado_final})."),
                    modelo=modelo)
        if r.veredito == EXPIRADO and not cobra_expirada:
            r = RespostaLLM(veredito=EXPIRADO, justificativa=r.justificativa,
                            modelo=r.modelo, tokens_entrada=r.tokens_entrada,
                            tokens_saida=r.tokens_saida, custo_usd=0.0,
                            tentativas=r.tentativas)
        respostas[chave] = r
    return respostas, orfas
