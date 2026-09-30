"""
openai.py — provedor OpenAI via API REST (`/v1/chat/completions`).

Sem o SDK oficial: a chamada é um POST com um JSON, e `requests` já é
dependência do projeto. Trazer o SDK adicionaria uma árvore de dependências
inteira para economizar ~20 linhas, contra a decisão de manter o projeto enxuto.

A chave vai em `Authorization: Bearer`, nunca na URL.
"""
import os
from dataclasses import dataclass

from .base import ProvedorHTTP

BASE_URL = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")
INTERVALO_PADRAO_S = float(os.environ.get("OPENAI_MIN_INTERVALO", "0"))

# Modelos de RACIOCÍNIO que aceitam `reasoning_effort: "none"`. Neles, e só com
# esse valor, `temperature` continua permitido: "When reasoning effort is not
# `none`, remove `temperature`, `top_p`, and `top_logprobs`" — e o padrão do
# Luna é `medium` (developers.openai.com/api/docs/guides/latest-model e
# /models/gpt-6-luna, consultados em 2026-09-30).
#
# `none` não é só o que destrava a temperatura 0: é o que põe esses modelos nas
# condições dos outros braços da matriz — uma resposta direta, sem raciocínio
# escondido que o prompt não controla e que seria cobrado como saída.
#
# Lista explícita, e não prefixo: GPT-6 Astra e GPT-6.1 Sol NÃO aceitam `none`,
# e mandar o parâmetro a um modelo que não o conhece (o `gpt-4o-mini`) é erro.
MODELOS_RACIOCINIO_NONE = frozenset({"gpt-6-luna", "gpt-6-sol"})


@dataclass
class ProvedorOpenAI(ProvedorHTTP):
    modelo: str = "gpt-4o-mini"
    nome: str = "openai"

    def __post_init__(self):
        super().__post_init__()
        if self.api_key is None:
            self.api_key = os.environ.get("OPENAI_API_KEY")
        if self.intervalo_minimo_s is None:
            self.intervalo_minimo_s = INTERVALO_PADRAO_S

    def _url(self) -> str:
        return f"{BASE_URL}/chat/completions"

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"}

    def _payload(self, prompt: str) -> dict:
        payload = {
            "model": self.modelo,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.0,
            # Equivale ao responseMimeType do Gemini: os dois braços de modelo
            # precisam receber a mesma exigência de formato, senão a diferença
            # entre eles inclui a dificuldade de acertar o JSON.
            "response_format": {"type": "json_object"},
        }
        if self.modelo in MODELOS_RACIOCINIO_NONE:
            payload["reasoning_effort"] = "none"
        return payload

    def _extrair(self, dados: dict) -> tuple[str, int, int]:
        texto = dados["choices"][0]["message"]["content"]
        uso = dados.get("usage", {})
        return (texto,
                int(uso.get("prompt_tokens", 0)),
                int(uso.get("completion_tokens", 0)))
