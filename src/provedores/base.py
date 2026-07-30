"""
base.py — contrato comum dos provedores de LLM, backoff e validação de schema.

O que está aqui é o que precisa ser idêntico entre os braços da matriz: a forma
da resposta, o critério de aceitação de um veredito e a política de repetição.
O que muda por provedor (URL, header de autenticação, formato do payload, onde
ficam os tokens na resposta) fica nas subclasses.
"""
import json
import logging
import random
import re
import time
from dataclasses import dataclass, field
from typing import Optional, Protocol

import requests

log = logging.getLogger(__name__)

VP = "VP"
FP = "FP"
ERROR = "ERROR"
VEREDITOS_VALIDOS = frozenset({VP, FP})

# Códigos que valem nova tentativa. 500/502/503 são falha transitória do lado
# do servidor; 429 é cota. Um 400/401/403 é erro de configuração e repetir só
# gasta tempo.
CODIGOS_TRANSITORIOS = frozenset({429, 500, 502, 503, 504})

# Backoff exponencial com jitter, substituindo os delays fixos [10, 30, 60] da
# Parte 1. O jitter evita que várias execuções paralelas repitam em sincronia;
# o teto impede que a terceira tentativa de um 429 pare a rodada por minutos.
BACKOFF_BASE_S = 5.0
BACKOFF_TETO_S = 120.0
MAX_TENTATIVAS = 4


@dataclass
class RespostaLLM:
    """Resultado normalizado de uma chamada, igual para qualquer provedor.

    `veredito` só assume VP ou FP quando a resposta passou pela validação de
    schema. Qualquer outra coisa é ERROR — nunca FP, porque contar uma falha de
    esteira como "o modelo achou seguro" inventaria um verdadeiro negativo.
    """

    veredito: str
    justificativa: str
    modelo: str
    tokens_entrada: int = 0
    tokens_saida: int = 0
    custo_usd: float = 0.0
    tentativas: int = 1

    @property
    def ok(self) -> bool:
        return self.veredito in VEREDITOS_VALIDOS

    def como_dict(self) -> dict:
        """Formato aceito por `src/fase5_auditoria.registrar_resultado`."""
        return {"verdict": self.veredito, "reasoning": self.justificativa}


class ProvedorLLM(Protocol):
    """Interface mínima que a pipeline conhece."""

    modelo: str

    def avaliar(self, prompt: str) -> RespostaLLM:
        ...


# ---------------------------------------------------------------------------
# Validação de schema
# ---------------------------------------------------------------------------

_JSON_EM_TEXTO = re.compile(r"\{.*\}", re.S)


def _extrair_json(texto: str) -> Optional[dict]:
    """Tenta ler o JSON da resposta, tolerando cerca de ```json ... ```.

    Não é permissividade gratuita: os dois braços de prompt exigem o mesmo
    contrato de saída, então um modelo que embrulha o JSON correto numa cerca
    de markdown acertou o conteúdo. O que NÃO se tolera é veredito fora do
    domínio — isso é decisão do modelo, não formatação.
    """
    try:
        return json.loads(texto)
    except (json.JSONDecodeError, TypeError):
        pass
    m = _JSON_EM_TEXTO.search(texto or "")
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return None


def validar_resposta(texto_bruto: str, modelo: str, tokens_entrada: int = 0,
                     tokens_saida: int = 0, custo_usd: float = 0.0,
                     tentativas: int = 1) -> RespostaLLM:
    """Converte o texto do modelo em `RespostaLLM`, ou em ERROR.

    Regras (spec `provedores-llm`):
      - JSON inválido            -> ERROR, com o texto bruto truncado.
      - veredito fora de {VP,FP} -> ERROR, jamais FP.
      - justificativa ausente    -> ERROR.
    """
    def _erro(motivo: str) -> RespostaLLM:
        bruto = (texto_bruto or "")[:400]
        return RespostaLLM(
            veredito=ERROR,
            justificativa=f"{motivo} | resposta bruta: {bruto}",
            modelo=modelo, tokens_entrada=tokens_entrada,
            tokens_saida=tokens_saida, custo_usd=custo_usd,
            tentativas=tentativas,
        )

    dados = _extrair_json(texto_bruto)
    if not isinstance(dados, dict):
        return _erro("Resposta não é JSON parseável")

    # `verdict`/`reasoning` são os nomes usados pelos templates de prompt; os
    # equivalentes em português são aceitos porque o modelo às vezes traduz a
    # chave junto com o conteúdo.
    veredito = dados.get("verdict", dados.get("veredito"))
    justificativa = dados.get("reasoning", dados.get("justificativa"))

    if not isinstance(veredito, str) or veredito.strip().upper() not in VEREDITOS_VALIDOS:
        return _erro(f"Veredito fora do domínio {{VP, FP}}: {veredito!r}")
    if not isinstance(justificativa, str) or not justificativa.strip():
        return _erro("Justificativa ausente ou vazia")

    return RespostaLLM(
        veredito=veredito.strip().upper(),
        justificativa=justificativa.strip(),
        modelo=modelo, tokens_entrada=tokens_entrada,
        tokens_saida=tokens_saida, custo_usd=custo_usd, tentativas=tentativas,
    )


# ---------------------------------------------------------------------------
# Backoff
# ---------------------------------------------------------------------------

def ler_retry_after(headers) -> Optional[float]:
    """Segundos pedidos pelo servidor no header `Retry-After`, se houver.

    Só a forma numérica é tratada: a forma em data HTTP exigiria comparar
    relógios com o servidor, e nenhuma das duas APIs em uso a emite.
    """
    if not headers:
        return None
    bruto = headers.get("Retry-After") or headers.get("retry-after")
    if bruto is None:
        return None
    try:
        return max(0.0, float(str(bruto).strip()))
    except ValueError:
        return None


def espera_backoff(tentativa: int, retry_after: Optional[float] = None,
                   aleatorio=random.uniform) -> float:
    """Espera antes da próxima tentativa (`tentativa` é 1-based).

    `Retry-After` vence o cálculo local — o servidor sabe melhor que nós quando
    a cota volta —, mas continua sujeito ao teto, para que um valor absurdo não
    trave a rodada.
    """
    if retry_after is not None:
        return min(retry_after, BACKOFF_TETO_S)
    bruto = BACKOFF_BASE_S * (2 ** (tentativa - 1)) * aleatorio(0.5, 1.5)
    return min(bruto, BACKOFF_TETO_S)


# ---------------------------------------------------------------------------
# Base concreta
# ---------------------------------------------------------------------------

@dataclass
class ProvedorHTTP:
    """Esqueleto compartilhado: throttle, retry e contabilidade.

    A subclasse fornece `_url()`, `_headers()`, `_payload(prompt)` e
    `_extrair(resposta_json)`; o laço de rede é o mesmo para todos.
    """

    modelo: str
    api_key: Optional[str] = None
    # None = "não informado", e cada subclasse aplica o padrão do seu provedor.
    # 0 é valor legítimo (desativa o throttle) e por isso não pode ser o
    # sentinela: `if not intervalo` trataria 0 como ausente.
    intervalo_minimo_s: Optional[float] = None
    timeout_s: int = 60
    max_tentativas: int = MAX_TENTATIVAS
    sessao: Optional[requests.Session] = None
    # None = nenhuma chamada feita ainda; a primeira não espera.
    _ultima_chamada: Optional[float] = field(default=None, init=False, repr=False)

    nome: str = "http"

    # -- a implementar pelas subclasses ------------------------------------

    def _url(self) -> str:
        raise NotImplementedError

    def _headers(self) -> dict:
        raise NotImplementedError

    def _payload(self, prompt: str) -> dict:
        raise NotImplementedError

    def _extrair(self, dados: dict) -> tuple[str, int, int]:
        """(texto da resposta, tokens de entrada, tokens de saída)."""
        raise NotImplementedError

    def _custo(self, tokens_entrada: int, tokens_saida: int) -> float:
        from .precos import custo_usd
        return custo_usd(self.modelo, tokens_entrada, tokens_saida)

    # -- throttle ----------------------------------------------------------

    def _aguardar_throttle(self, dormir=time.sleep, relogio=time.monotonic):
        """Intervalo mínimo entre chamadas consecutivas ao mesmo provedor.

        Preserva o comportamento do `GEMINI_MIN_INTERVALO` da Parte 1, agora
        por provedor: no tier grátis do Gemini o limite é de requisições por
        minuto, e estourá-lo transforma a rodada inteira numa fila de 429.
        """
        if self.intervalo_minimo_s and self._ultima_chamada is not None:
            espera = self.intervalo_minimo_s - (relogio() - self._ultima_chamada)
            if espera > 0:
                dormir(espera)
        self._ultima_chamada = relogio()

    # -- laço principal ----------------------------------------------------

    def avaliar(self, prompt: str, dormir=time.sleep,
                relogio=time.monotonic) -> RespostaLLM:
        """Uma avaliação completa: throttle, POST, retry e validação."""
        if not self.api_key:
            return RespostaLLM(
                veredito=ERROR,
                justificativa=f"Chave de API ausente para o provedor {self.nome}.",
                modelo=self.modelo,
            )

        http = self.sessao or requests
        ultimo_erro = "erro desconhecido"

        for tentativa in range(1, self.max_tentativas + 1):
            self._aguardar_throttle(dormir=dormir, relogio=relogio)
            try:
                resp = http.post(self._url(), headers=self._headers(),
                                 json=self._payload(prompt),
                                 timeout=self.timeout_s)
            except requests.RequestException as e:
                # Timeout e falha de conexão são transitórios por natureza.
                ultimo_erro = f"falha de rede: {type(e).__name__}"
                if tentativa < self.max_tentativas:
                    self._dormir_backoff(tentativa, None, dormir)
                    continue
                break

            if resp.status_code in CODIGOS_TRANSITORIOS:
                ultimo_erro = f"HTTP {resp.status_code}"
                if tentativa < self.max_tentativas:
                    self._dormir_backoff(tentativa,
                                         ler_retry_after(resp.headers), dormir)
                    continue
                break

            if resp.status_code >= 400:
                # A URL não entra na mensagem: ela não carrega a chave (a
                # autenticação é por header), mas repeti-la em log não ajuda.
                return RespostaLLM(
                    veredito=ERROR,
                    justificativa=(f"HTTP {resp.status_code} do provedor "
                                   f"{self.nome}: {resp.text[:300]}"),
                    modelo=self.modelo, tentativas=tentativa,
                )

            try:
                texto, t_in, t_out = self._extrair(resp.json())
            except (ValueError, KeyError, IndexError, TypeError) as e:
                return RespostaLLM(
                    veredito=ERROR,
                    justificativa=(f"Resposta do provedor {self.nome} em formato "
                                   f"inesperado ({type(e).__name__}): "
                                   f"{resp.text[:300]}"),
                    modelo=self.modelo, tentativas=tentativa,
                )

            return validar_resposta(texto, self.modelo, t_in, t_out,
                                    self._custo(t_in, t_out), tentativa)

        return RespostaLLM(
            veredito=ERROR,
            justificativa=(f"Tentativas esgotadas ({self.max_tentativas}) no "
                           f"provedor {self.nome}: {ultimo_erro}"),
            modelo=self.modelo, tentativas=self.max_tentativas,
        )

    def _dormir_backoff(self, tentativa, retry_after, dormir):
        espera = espera_backoff(tentativa, retry_after)
        log.info("    [retry] %s: aguardando %.1fs antes da tentativa %d...",
                 self.nome, espera, tentativa + 1)
        dormir(espera)
