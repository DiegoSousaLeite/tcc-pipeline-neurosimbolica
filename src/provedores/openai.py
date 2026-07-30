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


@dataclass
class ProvedorOpenAI(ProvedorHTTP):
    modelo: str = "gpt-4o-mini"
    nome: str = "openai"

    def __post_init__(self):
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
        return {
            "model": self.modelo,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.0,
            # Equivale ao responseMimeType do Gemini: os dois braços de modelo
            # precisam receber a mesma exigência de formato, senão a diferença
            # entre eles inclui a dificuldade de acertar o JSON.
            "response_format": {"type": "json_object"},
        }

    def _extrair(self, dados: dict) -> tuple[str, int, int]:
        texto = dados["choices"][0]["message"]["content"]
        uso = dados.get("usage", {})
        return (texto,
                int(uso.get("prompt_tokens", 0)),
                int(uso.get("completion_tokens", 0)))
