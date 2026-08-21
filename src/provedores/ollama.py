"""
ollama.py — provedor de modelo local, via a API HTTP do Ollama (`/api/chat`).

Sem a biblioteca `ollama`: o servidor expõe HTTP e `requests` já é dependência
do projeto — o mesmo argumento que dispensou o SDK da OpenAI. Não há chave de
API: o serviço é local e não autentica.

O braço é nomeado `ollama:<tag>` (ex.: `ollama:qwen2.5-coder:7b`). O namespace é
explícito de propósito: `gemma2` é um modelo aberto do Google e `gemini` é a API
do mesmo Google, então o espaço de nomes de modelo não é particionável por
prefixo de forma estável.

O cuidado central aqui é a janela de contexto. O padrão do servidor é 4096 e o
excedente é descartado **em silêncio** — um veredito emitido sobre um arquivo Go
visto pela metade entraria no CSV indistinguível de um veredito legítimo. Por
isso `num_ctx` é sempre explícito e o estouro vira `ERROR` em duas camadas
(estimativa antes da chamada, `prompt_eval_count` depois dela), nunca veredito.

Hardware conferido nesta máquina (tarefa 1.3): Ollama 0.32.5, Radeon RX 7600 de
8 GB, `qwen2.5-coder:7b` (Q4_K_M, 7,6B, digest dae161e27b0e...) roda com
`100% GPU` em `ollama ps`. A estimativa de tempo do design vale nesse regime; se
o modelo cair para CPU, ela muda de ordem de grandeza.
"""
import os
from dataclasses import dataclass, field
from typing import ClassVar, Optional

import requests

from .base import ERROR, ProvedorHTTP, RespostaLLM

BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")

# 600 s cobre o carregamento inicial dos pesos na VRAM e uma resposta longa de
# modelo com camadas na CPU. Os 60 s das APIs comerciais transformariam essa
# lentidão numa fila de erros de rede indistinguíveis de falha real.
TIMEOUT_PADRAO_S = int(os.environ.get("OLLAMA_TIMEOUT", "600"))

# Janela de contexto pedida em toda requisição. Calibrada contra a distribuição
# real de tamanho de prompt da população (ver tarefa 5.3/5.4 e o design).
NUM_CTX_PADRAO = int(os.environ.get("OLLAMA_NUM_CTX", "8192"))

# Teto da saída: o JSON de veredito é curto, e o limite existe para que um
# modelo que entre em laço não segure a rodada por dez minutos.
NUM_PREDICT = 512

# Semente fixa: temperatura zero não basta para reprodutibilidade no Ollama.
# Vai para o manifesto — o determinismo afirmado é "dentro da configuração
# registrada", não bit a bit entre versões do servidor.
SEMENTE = 42

# Mantém o modelo residente entre casos. Sem isso o servidor o descarrega após
# 5 min ociosos e a chamada seguinte paga de novo os ~15 s de carregamento.
KEEP_ALIVE = "30m"

# Razão caractere/token usada na estimativa pré-chamada. Folgada de propósito:
# em código a razão é menor que em prosa, então dividir por 3.5 SUPERESTIMA o
# número de tokens e erra para o lado seguro (recusar um prompt que talvez
# coubesse, em vez de aceitar um que será truncado em silêncio).
CHARS_POR_TOKEN = 3.5

PREFIXO = "ollama:"


class OllamaIndisponivel(RuntimeError):
    """Servidor fora do ar ou modelo não instalado — a rodada não pode começar."""


@dataclass
class ProvedorOllama(ProvedorHTTP):
    modelo: str = "ollama:qwen2.5-coder:7b"
    nome: str = "ollama"
    # O serviço é local e não autentica; a guarda de chave da base não se aplica.
    exige_chave: bool = False
    num_ctx: int = NUM_CTX_PADRAO
    num_predict: int = NUM_PREDICT
    semente: int = SEMENTE
    base_url: str = BASE_URL
    # Última resposta crua do servidor: é dela que saem `prompt_eval_count` e
    # `done_reason`, que a interface de `_extrair` (texto + dois inteiros) não
    # tem como carregar.
    _ultima_resposta: dict = field(default_factory=dict, init=False, repr=False)

    timeout_padrao_s: ClassVar[int] = TIMEOUT_PADRAO_S

    def __post_init__(self):
        super().__post_init__()
        if self.intervalo_minimo_s is None:
            # Throttle é para cota, e não há cota local.
            self.intervalo_minimo_s = 0

    # -- identidade do modelo ----------------------------------------------

    @property
    def tag(self) -> str:
        """`ollama:qwen2.5-coder:7b` -> `qwen2.5-coder:7b`.

        A separação é no PRIMEIRO dois-pontos: a tag do modelo tem os seus, e
        um nome de registry (`hf.co/org/modelo:Q4`) tem barras que também
        precisam sobreviver inteiras.
        """
        if self.modelo.startswith(PREFIXO):
            return self.modelo[len(PREFIXO):]
        return self.modelo

    # -- contrato da base ---------------------------------------------------

    def _url(self) -> str:
        return f"{self.base_url}/api/chat"

    def _headers(self) -> dict:
        return {"Content-Type": "application/json"}

    def _payload(self, prompt: str) -> dict:
        return {
            "model": self.tag,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            # `format: "json"`, e NÃO um JSON Schema com o enum {VP, FP}: o
            # Gemini e o GPT recebem só a exigência de JSON válido, e impor o
            # enum apenas aqui eliminaria do braço local uma modalidade de falha
            # ("respondeu TALVEZ") que os comerciais continuam correndo. A taxa
            # de erro de esteira é um dos números comparados.
            "format": "json",
            "keep_alive": KEEP_ALIVE,
            "options": {
                "temperature": 0.0,
                "seed": self.semente,
                "num_ctx": self.num_ctx,
                "num_predict": self.num_predict,
            },
        }

    def _extrair(self, dados: dict) -> tuple[str, int, int]:
        self._ultima_resposta = dados if isinstance(dados, dict) else {}
        texto = dados["message"]["content"]
        return (texto,
                int(dados.get("prompt_eval_count", 0)),
                int(dados.get("eval_count", 0)))

    def _descrever_erro_de_rede(self, e: Exception) -> str:
        # Timeout vem antes: `ConnectTimeout` é subclasse das duas, e nesse caso
        # o diagnóstico útil é o de espera esgotada.
        if isinstance(e, requests.Timeout):
            return (f"tempo limite excedido ({self.timeout_s}s): a inferência "
                    "local não respondeu a tempo")
        if isinstance(e, requests.ConnectionError):
            return (f"conexão recusada em {self.base_url}: o servidor Ollama "
                    "não está no ar")
        return super()._descrever_erro_de_rede(e)

    # -- janela de contexto -------------------------------------------------

    @property
    def teto_do_prompt(self) -> int:
        """Tokens de entrada que cabem sobrando espaço para a resposta."""
        return self.num_ctx - self.num_predict

    def tokens_estimados(self, prompt: str) -> int:
        return int(len(prompt or "") / CHARS_POR_TOKEN)

    def _erro(self, motivo: str, tokens_entrada=0, tokens_saida=0,
              tentativas=1) -> RespostaLLM:
        return RespostaLLM(veredito=ERROR, justificativa=motivo,
                           modelo=self.modelo, tokens_entrada=tokens_entrada,
                           tokens_saida=tokens_saida, tentativas=tentativas)

    def _motivo_de_truncamento(self) -> Optional[str]:
        """Diagnóstico de contexto a partir da última resposta do servidor.

        O Ollama não sinaliza truncamento de entrada: ele descarta o excedente e
        responde normalmente. O que se pode observar é `prompt_eval_count`
        encostando no teto — sinal de que o prompt foi cortado para caber.
        """
        dados = self._ultima_resposta or {}
        # Duas formas do mesmo desfecho. `done_reason == "length"` é o relato
        # limpo; `done: false` é o que o servidor devolve quando aborta a
        # geração no meio (visto no Ollama 0.32.5 com o modelo em laço
        # degenerado): sem `done_reason` e sem as contagens de token. Aceitar
        # veredito de uma geração que o próprio servidor não declarou concluída
        # seria exatamente a contaminação que este provedor existe para impedir.
        if dados.get("done") is False or dados.get("done_reason") == "length":
            return (f"Geração interrompida antes de concluir (limite de saída "
                    f"num_predict={self.num_predict}, ou aborto do servidor): "
                    "a resposta não chegou a fechar o JSON.")
        entrada = int(dados.get("prompt_eval_count", 0) or 0)
        if entrada >= self.teto_do_prompt:
            return (f"Prompt truncado pela janela de contexto: o servidor "
                    f"avaliou {entrada} tokens de entrada, no teto de "
                    f"{self.teto_do_prompt} (num_ctx={self.num_ctx}). O veredito "
                    "seria sobre código visto pela metade.")
        return None

    def avaliar(self, prompt: str, **kwargs) -> RespostaLLM:
        """`ProvedorHTTP.avaliar` cercado pelas duas camadas de contexto.

        O laço de rede (throttle, retry, validação) continua sendo o da base,
        byte a byte o mesmo dos braços comerciais: o que se acrescenta aqui é
        só a recusa de prompt grande demais e a auditoria do que o servidor
        relatou ter avaliado.
        """
        estimados = self.tokens_estimados(prompt)
        if estimados > self.teto_do_prompt:
            return self._erro(
                f"Prompt maior que a janela de contexto: ~{estimados} tokens "
                f"estimados contra o teto de {self.teto_do_prompt} "
                f"(num_ctx={self.num_ctx}, num_predict={self.num_predict}). "
                "Chamada não feita.")

        self._ultima_resposta = {}
        resposta = super().avaliar(prompt, **kwargs)

        motivo = self._motivo_de_truncamento()
        if motivo:
            # Vale inclusive quando o JSON veio bem-formado: um veredito sobre
            # entrada truncada é contaminação silenciosa da amostra, não dado.
            return self._erro(motivo, resposta.tokens_entrada,
                              resposta.tokens_saida, resposta.tentativas)
        return resposta

    # -- verificação prévia -------------------------------------------------

    def _get(self, caminho: str):
        http = self.sessao or requests
        return http.get(f"{self.base_url}{caminho}", timeout=30)

    def _post(self, caminho: str, corpo: dict, timeout=None):
        http = self.sessao or requests
        return http.post(f"{self.base_url}{caminho}", json=corpo,
                         timeout=timeout or 30)

    def sondar(self) -> dict:
        """Verifica servidor e modelo, e devolve a identidade que vai ao manifesto.

        Chamada uma vez por rodada, antes do primeiro caso. Sem ela, um
        `ollama serve` esquecido produziria centenas de linhas `ERROR`, cada uma
        depois de quatro tentativas com backoff — dezenas de minutos para
        descobrir um erro de operação.

        Campo que o servidor não informar sai como `None`: ausente e visível, em
        vez de omitido ou preenchido por suposição.
        """
        try:
            versao = self._get("/api/version").json().get("version")
            instalados = self._get("/api/tags").json().get("models") or []
        except requests.RequestException as e:
            raise OllamaIndisponivel(
                f"Servidor Ollama inacessível em {self.base_url} "
                f"({type(e).__name__}). Suba o serviço com `ollama serve` (ou "
                "inicie o aplicativo do Ollama) e refaça a rodada; para apontar "
                "para outro endereço, defina OLLAMA_BASE_URL."
            ) from e

        nomes = [m.get("name") for m in instalados if m.get("name")]
        if self.tag not in nomes:
            disponiveis = ", ".join(sorted(nomes)) or "nenhum"
            raise OllamaIndisponivel(
                f"Modelo '{self.tag}' não está instalado em {self.base_url}. "
                f"Instalados: {disponiveis}. Baixe com `ollama pull {self.tag}`."
            )

        entrada = next((m for m in instalados if m.get("name") == self.tag), {})
        detalhes, info = {}, {}
        try:
            mostrado = self._post("/api/show", {"model": self.tag}).json()
            detalhes = mostrado.get("details") or {}
            info = mostrado.get("model_info") or {}
        except (requests.RequestException, ValueError):
            # A rodada pode seguir sem isso; o manifesto registra o que faltou.
            pass

        return {
            "modelo": self.modelo,
            "tag": self.tag,
            "servidor": self.base_url,
            "versao_ollama": versao,
            # O digest é o que identifica os PESOS: a tag é ponteiro mutável no
            # registry, igual a `latest`, e sozinha não reatribui um número do
            # capítulo de resultados ao modelo que o produziu.
            "digest": entrada.get("digest"),
            "quantizacao": detalhes.get("quantization_level"),
            "parametros": detalhes.get("parameter_size"),
            "janela_maxima_declarada": _janela_declarada(info),
            "num_ctx": self.num_ctx,
            "num_predict": self.num_predict,
            "semente": self.semente,
            "processador": self._carregar_e_medir_processador(),
        }

    def _carregar_e_medir_processador(self) -> Optional[str]:
        """Residencia o modelo e lê como o servidor o dividiu entre GPU e CPU.

        `/api/ps` só reporta o que está carregado, e a sondagem roda antes do
        primeiro caso — daí o carregamento explícito (prompt vazio é o pedido de
        load da API). Efeito colateral desejável: o primeiro caso da rodada não
        paga mais os ~15 s de leitura dos pesos.
        """
        try:
            self._post("/api/generate",
                       {"model": self.tag, "keep_alive": KEEP_ALIVE},
                       timeout=self.timeout_s)
        except requests.RequestException:
            return None
        return self._processador()

    def _processador(self) -> Optional[str]:
        """`100% GPU`, `100% CPU` ou a divisão entre as duas, como em `ollama ps`.

        Se o ROCm não engatar, o Ollama roda em CPU com os mesmos vereditos e
        throughput ~10x menor: é nota de viabilidade no manifesto, não resultado.
        Devolve `None` quando o modelo ainda não está residente — o servidor só
        reporta o que está carregado.
        """
        try:
            carregados = self._get("/api/ps").json().get("models") or []
        except (requests.RequestException, ValueError):
            return None
        for m in carregados:
            if m.get("name") != self.tag:
                continue
            total = int(m.get("size") or 0)
            vram = int(m.get("size_vram") or 0)
            if not total:
                return None
            if vram >= total:
                return "100% GPU"
            if vram <= 0:
                return "100% CPU"
            pct = round(vram / total * 100)
            return f"{pct}% GPU/{100 - pct}% CPU"
        return None


def _janela_declarada(model_info: dict) -> Optional[int]:
    """`<familia>.context_length` do GGUF, sem depender do nome da família."""
    for chave, valor in (model_info or {}).items():
        if chave.endswith(".context_length"):
            try:
                return int(valor)
            except (TypeError, ValueError):
                return None
    return None
