"""
gemini_lote.py — entrega em lote do Gemini (`models/{modelo}:batchGenerateContent`).

É o primeiro provedor de lote por ser o que já existe no síncrono e onde o lote
de validação custa ~R$ 0,01 (D6). Não herda de `ProvedorHTTP`: usa um
`ProvedorGemini` por composição só para três coisas, que precisam ser as MESMAS
do síncrono para que os modos sejam comparáveis — o corpo da requisição
(`_payload`: temperatura 0, `responseMimeType` JSON), a extração de texto e
tokens da `GenerateContentResponse` (`_extrair`) e o custo (`_custo`). O
veredito sai de `validar_resposta`, também a mesma.

Formato do fornecedor — consultado em 2026-09-28 em
`ai.google.dev/api/batch-api` (referência REST, "Last updated 2026-09-23") e
`ai.google.dev/gemini-api/docs/batch-api` (guia):

Submissão (requisições inline; limite de 20 MB por submissão)::

    POST /v1beta/models/gemini-2.5-flash-lite:batchGenerateContent
    {"batch": {"display_name": "<rótulo do cliente>",
               "input_config": {"requests": {"requests": [
                   {"request": {"contents": [{"parts": [{"text": "..."}]}],
                                "generationConfig": {...}},
                    "metadata": {"key": "<ID_Caso>|<Modelo_LLM>|<Tipo_Prompt>"}}
               ]}}}}
    -> Operation {"name": "batches/abc123", "metadata": {...}, "done": false}

Consulta: ``GET /v1beta/batches/abc123`` devolve a mesma `Operation`; o estado
fica em ``metadata.state``. O guia usa `JOB_STATE_*` e a referência lista
`BATCH_STATE_*` — os dois prefixos são aceitos (`normalizar_estado`).

Recuperação (``done: true``)::

    {"name": "batches/abc123", "done": true,
     "metadata": {"state": "BATCH_STATE_SUCCEEDED", ...},
     "response": {"inlinedResponses": {"inlinedResponses": [
         {"metadata": {"key": "<chave>"},
          "response": {<GenerateContentResponse, igual à do síncrono>}},
         {"metadata": {"key": "<chave>"},
          "error": {"code": 400, "message": "..."}}
     ]}}}

A chave de correlação (tarefa 1.1): `InlinedRequest.metadata` é um `Struct`
arbitrário, sem limite de tamanho ou alfabeto documentado. O limite de 63
caracteres minúsculos que aparece na mesma página é o de `labels`, campo que
este provedor não usa. A maior chave real da população tem 119 caracteres ASCII
(`TPA:mx-chain-go:CWE-665:CreateBuiltInFuncContainerAndNFTStorageHandler:
1f624cfb:vuln|gemini-2.5-flash-lite|especialista`); a do exemplo da tarefa, 84.

Ordem: a referência afirma que as respostas inline vêm "in the same order as
the input requests". A correlação NÃO se apoia nisso — é pela chave, sempre —,
porque a garantia é de um fornecedor só e a OpenAI declara o contrário.

Expiração: é do LOTE, não da requisição — `JOB_STATE_EXPIRED` depois de 48 h
pendente ou rodando, e então "the job will not have any results to retrieve".
Retenção dos resultados: 6 semanas.
"""
import json
import logging
import os
from dataclasses import dataclass, field
from typing import Optional

import requests

from .base import ERROR, MAX_TENTATIVAS, RespostaLLM, validar_resposta
from .gemini import ProvedorGemini
from .lote import (
    CANCELADO,
    CONCLUIDO,
    FALHOU,
    LOTE_EXPIRADO,
    NAO_ENCONTRADO,
    PENDENTE,
    ErroLote,
    LimitesLote,
    estimar_tokens,
    get_com_repeticao,
)

log = logging.getLogger(__name__)

BASE_URL = "https://generativelanguage.googleapis.com/v1beta"

# Tokens de entrada enfileiráveis por modelo, somando TODOS os lotes ativos
# daquele modelo — Tier 1 (billing ativo), `ai.google.dev/gemini-api/docs/
# rate-limits`, tabela "Batch enqueued tokens", consultada em 2026-09-28.
#
# Correção ao levantamento de 2026-09-17: os 3.000.000 citados em
# `docs/ESCOLHA-MODELO-COMERCIAL.md` §8.5 são do Gemini 3.8 Flash (e do 2.5
# Flash). O 2.5 Flash-Lite enfileira 10.000.000 — a rodada de 3.199.085 tokens
# cabe nele inteira. Quem ainda não cabe é o 2.5 Flash.
#
# O tier grátis NÃO consta da tabela: sem billing, não há lote.
TOKENS_ENFILEIRADOS_TIER1 = {
    "gemini-2.5-flash-lite": 10_000_000,
    "gemini-2.5-flash": 3_000_000,
    "gemini-2.5-pro": 5_000_000,
}
# Modelo fora da tabela cai no menor teto publicado: partição a mais custa só
# um lote a mais; teto alto demais custa um lote recusado.
TOKENS_ENFILEIRADOS_PADRAO = 3_000_000
# Requisições inline: "under 20MB" por submissão (guia do Batch API). Acima
# disso o caminho é arquivo JSONL via Files API, que este provedor não usa —
# a partição por bytes mantém cada submissão abaixo do teto.
BYTES_INLINE = 20_000_000


def limites_do_modelo(modelo: str) -> LimitesLote:
    """Limites do lote para o modelo, com sobrescrita por ambiente.

    `GEMINI_LOTE_TOKENS_ENFILEIRADOS` existe para um tier acima do 1 (o Tier 2
    enfileira 400.000.000): o tier é propriedade da conta, não do código.
    """
    bruto = os.environ.get("GEMINI_LOTE_TOKENS_ENFILEIRADOS")
    tokens = (int(bruto) if bruto else
              TOKENS_ENFILEIRADOS_TIER1.get(modelo, TOKENS_ENFILEIRADOS_PADRAO))
    return LimitesLote(tokens_enfileirados=tokens, bytes_por_lote=BYTES_INLINE)


_ESTADOS = {
    "PENDING": PENDENTE,
    "RUNNING": PENDENTE,
    "UNSPECIFIED": PENDENTE,
    "SUCCEEDED": CONCLUIDO,
    "EXPIRED": LOTE_EXPIRADO,
    "FAILED": FALHOU,
    "CANCELLED": CANCELADO,
}


def normalizar_estado(operacao: dict) -> str:
    """Estado de uma `Operation` de lote, no vocabulário de `lote.py`."""
    bruto = str((operacao.get("metadata") or {}).get("state") or "")
    for prefixo in ("JOB_STATE_", "BATCH_STATE_"):
        if bruto.startswith(prefixo):
            bruto = bruto[len(prefixo):]
            break
    if bruto in _ESTADOS:
        return _ESTADOS[bruto]
    if operacao.get("done"):
        # Sem estado legível: o desfecho sai do resultado da operação.
        if operacao.get("error"):
            # google.rpc.Code.CANCELLED == 1
            return CANCELADO if operacao["error"].get("code") == 1 else FALHOU
        return CONCLUIDO
    return PENDENTE


def respostas_inline(operacao: dict) -> list:
    """A lista de `InlinedResponse` da operação, onde quer que ela venha.

    A referência põe a saída em `GenerateContentBatch.output`; a `Operation`
    concluída a traz em `response`, e o guia a lê como `.response.
    inlinedResponses` — que por sua vez é um objeto `InlinedResponses` com a
    lista dentro. Aceitar as três formas custa pouco; errar custaria o lote.
    """
    for fonte in (operacao.get("response"),
                  (operacao.get("metadata") or {}).get("output")):
        if not isinstance(fonte, dict):
            continue
        if fonte.get("responsesFile"):
            raise ErroLote("O lote devolveu um arquivo de respostas "
                           f"({fonte['responsesFile']}); este provedor só lê "
                           "respostas inline.")
        itens = fonte.get("inlinedResponses")
        if isinstance(itens, dict):
            itens = itens.get("inlinedResponses")
        if isinstance(itens, list):
            return itens
    return []


def _nome_exibicao(operacao: dict) -> Optional[str]:
    meta = operacao.get("metadata") or {}
    return meta.get("displayName") or meta.get("display_name")


@dataclass
class ProvedorGeminiLote:
    modelo: str = "gemini-2.5-flash-lite"
    api_key: Optional[str] = None
    sessao: Optional[requests.Session] = None
    timeout_s: int = 120
    max_tentativas: int = MAX_TENTATIVAS
    limites: Optional[LimitesLote] = None
    nome: str = "gemini"
    desconto: float = 0.5
    # A expiração no Gemini é do lote inteiro e ele "não terá resultados": não
    # há tokens a cobrar. Declarado, e não inferido da ausência de tokens.
    cobra_expirada: bool = False
    _sinc: ProvedorGemini = field(init=False, repr=False)

    def __post_init__(self):
        if self.api_key is None:
            self.api_key = os.environ.get("GEMINI_API_KEY")
        if self.limites is None:
            self.limites = limites_do_modelo(self.modelo)
        self._sinc = ProvedorGemini(modelo=self.modelo, api_key=self.api_key,
                                    intervalo_minimo_s=0)

    # -- formato -------------------------------------------------------------

    def _item(self, chave: str, prompt: str) -> dict:
        return {"request": self._sinc._payload(prompt), "metadata": {"key": chave}}

    def corpo_submissao(self, prompts: dict[str, str], rotulo: str) -> dict:
        return {"batch": {
            "display_name": rotulo,
            "input_config": {"requests": {"requests": [
                self._item(k, p) for k, p in prompts.items()]}},
        }}

    def medir(self, chave: str, prompt: str) -> tuple[int, int]:
        corpo = json.dumps(self._item(chave, prompt), ensure_ascii=False)
        return estimar_tokens(prompt, self.limites), len(corpo.encode("utf-8"))

    def converter(self, item: dict) -> RespostaLLM:
        """Uma `InlinedResponse` em `RespostaLLM`, pelo MESMO caminho do síncrono."""
        if "response" in item:
            try:
                texto, t_in, t_out = self._sinc._extrair(item["response"])
            except (ValueError, KeyError, IndexError, TypeError) as e:
                return RespostaLLM(
                    veredito=ERROR,
                    justificativa=(f"Resposta do provedor {self.nome} em formato "
                                   f"inesperado ({type(e).__name__}): "
                                   f"{json.dumps(item['response'])[:300]}"),
                    modelo=self.modelo)
            return validar_resposta(texto, self.modelo, t_in, t_out,
                                    self._sinc._custo(t_in, t_out), 1)
        erro = item.get("error") or {}
        return RespostaLLM(
            veredito=ERROR,
            justificativa=(f"Erro do provedor {self.nome} na requisição do lote: "
                           f"{erro.get('code', '?')} {str(erro.get('message', ''))[:300]}"),
            modelo=self.modelo)

    # -- rede ----------------------------------------------------------------

    def _headers(self) -> dict:
        return self._sinc._headers()

    def _exigir_chave(self):
        if not self.api_key:
            raise ErroLote(f"Chave de API ausente para o provedor {self.nome} "
                           "(GEMINI_API_KEY).")

    def _get(self, url: str, params=None):
        self._exigir_chave()
        return get_com_repeticao(self.sessao or requests, url, self._headers(),
                                 params, self.timeout_s, self.max_tentativas)

    def submeter(self, prompts: dict[str, str], rotulo: str) -> str:
        """Submete e devolve `batches/<id>`, sem esperar os vereditos.

        SEM repetição automática, ao contrário das consultas: uma submissão cujo
        retorno se perdeu pode ter criado o lote, e repeti-la pagaria duas vezes.
        Quem chama resolve pelo rótulo (`localizar`) antes de tentar de novo.
        """
        self._exigir_chave()
        http = self.sessao or requests
        resp = http.post(f"{BASE_URL}/models/{self.modelo}:batchGenerateContent",
                         headers=self._headers(),
                         json=self.corpo_submissao(prompts, rotulo),
                         timeout=self.timeout_s)
        if resp.status_code >= 400:
            raise ErroLote(f"Submissão recusada pelo provedor {self.nome}: HTTP "
                           f"{resp.status_code}: {resp.text[:300]}")
        try:
            return resp.json()["name"]
        except (ValueError, KeyError, TypeError) as e:
            raise ErroLote(f"Submissão sem identificador de lote "
                           f"({type(e).__name__}): {resp.text[:300]}") from e

    def _operacao(self, id_lote: str) -> Optional[dict]:
        resp = self._get(f"{BASE_URL}/{id_lote}")
        if resp.status_code == 404:
            return None
        if resp.status_code >= 400:
            raise ErroLote(f"Consulta a {id_lote} recusada: HTTP "
                           f"{resp.status_code}: {resp.text[:300]}")
        return resp.json()

    def estado(self, id_lote: str) -> str:
        op = self._operacao(id_lote)
        return NAO_ENCONTRADO if op is None else normalizar_estado(op)

    def localizar(self, rotulo: str) -> Optional[str]:
        """Identificador do lote de nome de exibição `rotulo`, se existir."""
        token = None
        while True:
            params = {"pageSize": 100}
            if token:
                params["pageToken"] = token
            resp = self._get(f"{BASE_URL}/batches", params=params)
            if resp.status_code >= 400:
                raise ErroLote(f"Listagem de lotes recusada: HTTP "
                               f"{resp.status_code}: {resp.text[:300]}")
            dados = resp.json()
            for op in dados.get("operations", []) or dados.get("batches", []):
                if _nome_exibicao(op) == rotulo:
                    return op.get("name")
            token = dados.get("nextPageToken")
            if not token:
                return None

    def recuperar(self, id_lote: str) -> dict[str, RespostaLLM]:
        """Vereditos por chave. Lote sem resultados (expirado) devolve `{}`."""
        op = self._operacao(id_lote)
        if op is None:
            raise ErroLote(f"Lote {id_lote} não encontrado no provedor "
                           f"{self.nome} (retenção de 6 semanas).")
        saida = {}
        for item in respostas_inline(op):
            chave = (item.get("metadata") or {}).get("key")
            if not chave:
                log.warning("    [ANOMALIA] resposta de lote sem chave, "
                            "descartada: %s", json.dumps(item)[:200])
                continue
            if chave in saida:
                log.warning("    [ANOMALIA] chave repetida no resultado do "
                            "lote, mantida a primeira: %s", chave)
                continue
            saida[chave] = self.converter(item)
        return saida
