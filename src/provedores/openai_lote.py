"""
openai_lote.py — entrega em lote da OpenAI (Batch API sobre `/v1/chat/completions`).

O segundo provedor de lote, que D6 de `envio-em-lote-comercial` previa: usa o
mesmo protocolo `ProvedorLote`, e o `ProvedorOpenAI` síncrono por composição
para as três coisas que precisam ser idênticas entre os modos — o corpo da
requisição (`_payload`: temperatura 0, JSON, `reasoning_effort: "none"` nos
modelos de raciocínio que o aceitam), a extração de texto e tokens (`_extrair`)
e o custo (`_custo`). O veredito sai de `validar_resposta`.

Formato do fornecedor — `developers.openai.com/api/docs/guides/batch`,
consultado em 2026-09-30:

1. Sobe um JSONL pela Files API (``POST /v1/files``, multipart, ``purpose=batch``),
   uma requisição por linha::

       {"custom_id": "<ID_Caso>|<Modelo_LLM>|<Tipo_Prompt>", "method": "POST",
        "url": "/v1/chat/completions", "body": {<o mesmo payload do síncrono>}}

2. Cria o lote (``POST /v1/batches``)::

       {"input_file_id": "file-...", "endpoint": "/v1/chat/completions",
        "completion_window": "24h", "metadata": {"rotulo": "<rótulo do cliente>"}}
       -> {"id": "batch_...", "status": "validating", ...}

3. Consulta (``GET /v1/batches/{id}``): `status` em validating, in_progress,
   finalizing, completed, failed, expired, cancelling, cancelled.

4. Recupera ``GET /v1/files/{output_file_id}/content`` e o de
   ``error_file_id``, JSONL, uma linha por requisição::

       {"id": "batch_req_...", "custom_id": "<chave>",
        "response": {"status_code": 200, "request_id": "...",
                     "body": {<ChatCompletion, igual à do síncrono>}},
        "error": null}

   Requisição expirada vem com ``"error": {"code": "batch_expired", ...}``.

`custom_id`: único por lote; sem limite de tamanho ou alfabeto documentado.
Ordem: "The output line order may not match the input line order" — a
correlação é pela chave, sempre. Expiração: janela de 24 h; as requisições não
concluídas são canceladas, e só as concluídas são cobradas. Retenção: o arquivo
de saída é apagado 30 dias depois de o lote terminar. Limites: 50.000
requisições e 200 MB por lote.
"""
import json
import logging
import os
from dataclasses import dataclass, field
from typing import Optional

import requests

from .base import ERROR, MAX_TENTATIVAS, RespostaLLM, validar_resposta
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
    resposta_expirada,
)
from .openai import BASE_URL, ProvedorOpenAI
from .precos import modelo_base

log = logging.getLogger(__name__)

ENDPOINT = "/v1/chat/completions"

# Tokens de entrada enfileiráveis por modelo, Tier 1 (coluna "Batch Queue" da
# página de cada modelo em developers.openai.com, consultada em 2026-09-30).
# Como no Gemini, o teto vale para a fila do modelo, e as partições são
# submetidas uma de cada vez.
TOKENS_ENFILEIRADOS_TIER1 = {
    "gpt-6-luna": 5_000_000,
}
# Modelo não verificado cai num teto baixo: uma partição a mais custa só um
# lote a mais; um teto alto demais custa um lote recusado.
TOKENS_ENFILEIRADOS_PADRAO = 2_000_000
REQUISICOES_POR_LOTE = 50_000
BYTES_POR_LOTE = 200_000_000

_ESTADOS = {
    "validating": PENDENTE,
    "in_progress": PENDENTE,
    "finalizing": PENDENTE,
    "cancelling": PENDENTE,
    "completed": CONCLUIDO,
    "expired": LOTE_EXPIRADO,
    "failed": FALHOU,
    "cancelled": CANCELADO,
}


def limites_do_modelo(modelo: str) -> LimitesLote:
    """Limites do lote, com o teto de fila sobrescrevível por ambiente.

    `OPENAI_LOTE_TOKENS_ENFILEIRADOS` existe porque o tier é da conta, não do
    código (o Tier 2 do `gpt-6-luna` enfileira 20.000.000).
    """
    bruto = os.environ.get("OPENAI_LOTE_TOKENS_ENFILEIRADOS")
    tokens = (int(bruto) if bruto else
              TOKENS_ENFILEIRADOS_TIER1.get(modelo_base(modelo),
                                            TOKENS_ENFILEIRADOS_PADRAO))
    return LimitesLote(tokens_enfileirados=tokens, bytes_por_lote=BYTES_POR_LOTE,
                       requisicoes_por_lote=REQUISICOES_POR_LOTE)


def normalizar_estado(lote: dict) -> str:
    return _ESTADOS.get(str(lote.get("status") or ""), PENDENTE)


@dataclass
class ProvedorOpenAILote:
    modelo: str = "gpt-6-luna"
    api_key: Optional[str] = None
    sessao: Optional[requests.Session] = None
    timeout_s: int = 120
    max_tentativas: int = MAX_TENTATIVAS
    limites: Optional[LimitesLote] = None
    nome: str = "openai"
    desconto: float = 0.5
    # "You will be charged for tokens consumed from any completed requests": a
    # requisição expirada não foi executada, não consumiu token, não é cobrada.
    cobra_expirada: bool = False
    _sinc: ProvedorOpenAI = field(init=False, repr=False)

    def __post_init__(self):
        if self.api_key is None:
            self.api_key = os.environ.get("OPENAI_API_KEY")
        if self.limites is None:
            self.limites = limites_do_modelo(self.modelo)
        self._sinc = ProvedorOpenAI(modelo=self.modelo, api_key=self.api_key,
                                    intervalo_minimo_s=0)

    # -- formato -------------------------------------------------------------

    def linha(self, chave: str, prompt: str) -> str:
        return json.dumps({"custom_id": chave, "method": "POST", "url": ENDPOINT,
                           "body": self._sinc._payload(prompt)},
                          ensure_ascii=False)

    def jsonl(self, prompts: dict[str, str]) -> bytes:
        return "".join(self.linha(k, p) + "\n"
                       for k, p in prompts.items()).encode("utf-8")

    def medir(self, chave: str, prompt: str) -> tuple[int, int]:
        return (estimar_tokens(prompt, self.limites),
                len(self.linha(chave, prompt).encode("utf-8")) + 1)

    def converter(self, item: dict) -> RespostaLLM:
        """Uma linha do JSONL de saída em `RespostaLLM`, pelo caminho do síncrono."""
        erro = item.get("error")
        if erro:
            if erro.get("code") == "batch_expired":
                return resposta_expirada(self.modelo, str(erro.get("message", "")))
            return RespostaLLM(
                veredito=ERROR,
                justificativa=(f"Erro do provedor {self.nome} na requisição do "
                               f"lote: {erro.get('code', '?')} "
                               f"{str(erro.get('message', ''))[:300]}"),
                modelo=self.modelo)
        resposta = item.get("response") or {}
        corpo = resposta.get("body") or {}
        if resposta.get("status_code") != 200:
            mensagem = (corpo.get("error") or {}).get("message", "") \
                if isinstance(corpo, dict) else ""
            return RespostaLLM(
                veredito=ERROR,
                justificativa=(f"HTTP {resposta.get('status_code')} do provedor "
                               f"{self.nome} no lote: {str(mensagem)[:300]}"),
                modelo=self.modelo)
        try:
            texto, t_in, t_out = self._sinc._extrair(corpo)
        except (ValueError, KeyError, IndexError, TypeError) as e:
            return RespostaLLM(
                veredito=ERROR,
                justificativa=(f"Resposta do provedor {self.nome} em formato "
                               f"inesperado ({type(e).__name__}): "
                               f"{json.dumps(corpo)[:300]}"),
                modelo=self.modelo)
        return validar_resposta(texto, self.modelo, t_in, t_out,
                                self._sinc._custo(t_in, t_out), 1)

    # -- rede ----------------------------------------------------------------

    def _auth(self) -> dict:
        # Sem Content-Type: o upload é multipart, e `requests` monta o dele.
        return {"Authorization": f"Bearer {self.api_key}"}

    def _exigir_chave(self):
        if not self.api_key:
            raise ErroLote(f"Chave de API ausente para o provedor {self.nome} "
                           "(OPENAI_API_KEY).")

    def _get(self, url: str, params=None):
        self._exigir_chave()
        return get_com_repeticao(self.sessao or requests, url, self._auth(),
                                 params, self.timeout_s, self.max_tentativas)

    def _post(self, url: str, **kwargs):
        http = self.sessao or requests
        resp = http.post(url, headers=self._auth(), timeout=self.timeout_s,
                         **kwargs)
        if resp.status_code >= 400:
            raise ErroLote(f"Requisição recusada pelo provedor {self.nome} "
                           f"({url.rsplit('/', 1)[-1]}): HTTP "
                           f"{resp.status_code}: {resp.text[:300]}")
        return resp.json()

    def submeter(self, prompts: dict[str, str], rotulo: str) -> str:
        """Sobe o JSONL, cria o lote e devolve `batch_...`, sem esperar.

        Sem repetição automática: uma criação cujo retorno se perdeu pode ter
        criado o lote. Um upload órfão (arquivo sem lote) não custa nada; a
        retomada procura o lote pelo rótulo antes de submeter de novo.
        """
        self._exigir_chave()
        arquivo = self._post(
            f"{BASE_URL}/files", data={"purpose": "batch"},
            files={"file": (f"{rotulo}.jsonl", self.jsonl(prompts),
                            "application/jsonl")})
        lote = self._post(f"{BASE_URL}/batches", json={
            "input_file_id": arquivo["id"],
            "endpoint": ENDPOINT,
            "completion_window": "24h",
            "metadata": {"rotulo": rotulo},
        })
        try:
            return lote["id"]
        except (KeyError, TypeError) as e:
            raise ErroLote(f"Lote criado sem identificador: {lote!r:.300}") from e

    def _lote(self, id_lote: str) -> Optional[dict]:
        resp = self._get(f"{BASE_URL}/batches/{id_lote}")
        if resp.status_code == 404:
            return None
        if resp.status_code >= 400:
            raise ErroLote(f"Consulta a {id_lote} recusada: HTTP "
                           f"{resp.status_code}: {resp.text[:300]}")
        return resp.json()

    def estado(self, id_lote: str) -> str:
        lote = self._lote(id_lote)
        if lote is None:
            return NAO_ENCONTRADO
        estado = normalizar_estado(lote)
        if estado == FALHOU:
            # Lote que falha na validação não tem arquivo de erro por linha: o
            # motivo só existe aqui, e sem o log a rodada sairia toda ERROR sem
            # explicação.
            log.error("    [LOTE] %s falhou no fornecedor: %s", id_lote,
                      json.dumps(lote.get("errors"))[:500])
        return estado

    def localizar(self, rotulo: str) -> Optional[str]:
        """Identificador do lote cujo `metadata.rotulo` é `rotulo`, se existir."""
        depois = None
        while True:
            params = {"limit": 100}
            if depois:
                params["after"] = depois
            resp = self._get(f"{BASE_URL}/batches", params=params)
            if resp.status_code >= 400:
                raise ErroLote(f"Listagem de lotes recusada: HTTP "
                               f"{resp.status_code}: {resp.text[:300]}")
            dados = resp.json()
            lotes = dados.get("data") or []
            for lote in lotes:
                if (lote.get("metadata") or {}).get("rotulo") == rotulo:
                    return lote.get("id")
            if not dados.get("has_more") or not lotes:
                return None
            depois = dados.get("last_id") or lotes[-1].get("id")

    def _linhas_do_arquivo(self, id_arquivo: str) -> list:
        resp = self._get(f"{BASE_URL}/files/{id_arquivo}/content")
        if resp.status_code >= 400:
            raise ErroLote(f"Arquivo de resultado {id_arquivo} indisponível: "
                           f"HTTP {resp.status_code}: {resp.text[:300]}")
        linhas = []
        for bruta in resp.text.splitlines():
            if not bruta.strip():
                continue
            try:
                linhas.append(json.loads(bruta))
            except json.JSONDecodeError:
                log.warning("    [ANOMALIA] linha ilegível no resultado do "
                            "lote, descartada: %s", bruta[:200])
        return linhas

    def recuperar(self, id_lote: str) -> dict[str, RespostaLLM]:
        """Vereditos por chave, lidos do arquivo de saída e do de erros."""
        lote = self._lote(id_lote)
        if lote is None:
            raise ErroLote(f"Lote {id_lote} não encontrado no provedor "
                           f"{self.nome} (retenção de 30 dias).")
        saida = {}
        for id_arquivo in (lote.get("output_file_id"), lote.get("error_file_id")):
            if not id_arquivo:
                continue
            for item in self._linhas_do_arquivo(id_arquivo):
                chave = item.get("custom_id")
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
