"""
gemini.py — provedor Gemini via API REST (`generateContent`).

A chave vai no header `x-goog-api-key`. Na Parte 1 ela ia na query string da
URL montada em `src/config.py`, onde vazava em qualquer log de URL, traceback
de `requests` ou proxy no caminho. É correção de segurança, não refactor.
"""
import os
from dataclasses import dataclass

from .base import ProvedorHTTP

BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"

# O tier grátis do gemini-2.5-flash é ~10 RPM; 7 s deixa folga (~8,5 RPM).
# Em tier pago use 0. Mantém o nome da variável da Parte 1 para não quebrar os
# ambientes já configurados.
INTERVALO_PADRAO_S = float(os.environ.get("GEMINI_MIN_INTERVALO", "7"))


@dataclass
class ProvedorGemini(ProvedorHTTP):
    modelo: str = "gemini-2.5-flash-lite"
    nome: str = "gemini"

    def __post_init__(self):
        super().__post_init__()
        if self.api_key is None:
            self.api_key = os.environ.get("GEMINI_API_KEY")
        if self.intervalo_minimo_s is None:
            self.intervalo_minimo_s = INTERVALO_PADRAO_S

    def _url(self) -> str:
        return f"{BASE_URL}/{self.modelo}:generateContent"

    def _headers(self) -> dict:
        return {"x-goog-api-key": self.api_key,
                "Content-Type": "application/json"}

    def _payload(self, prompt: str) -> dict:
        return {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                # Temperatura 0: o experimento compara prompts e modelos, não
                # amostragens do mesmo modelo.
                "temperature": 0.0,
                "responseMimeType": "application/json",
            },
        }

    def _extrair(self, dados: dict) -> tuple[str, int, int]:
        texto = dados["candidates"][0]["content"]["parts"][0]["text"]
        uso = dados.get("usageMetadata", {})
        return (texto,
                int(uso.get("promptTokenCount", 0)),
                int(uso.get("candidatesTokenCount", 0)))
