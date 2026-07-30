"""Camada de provedores de LLM.

A matriz 2x2 da Parte 2 cruza dois modelos (Gemini e GPT) com dois tipos de
prompt. Para que o eixo do modelo seja de fato uma variável independente, o
resto da pipeline não pode saber qual provedor está em uso: `avaliar(prompt)`
devolve sempre uma `RespostaLLM`, com veredito já validado e custo já derivado.
"""
from .base import ERROR, FP, VP, ProvedorLLM, RespostaLLM
from .gemini import ProvedorGemini
from .openai import ProvedorOpenAI

# Modelos padrão de cada braço da matriz. Ficam aqui, e não no config, porque
# são identidade do experimento e vão para o manifesto da rodada.
MODELO_GEMINI_PADRAO = "gemini-2.5-flash-lite"
MODELO_OPENAI_PADRAO = "gpt-4o-mini"

_FABRICAS = {
    "gemini": ProvedorGemini,
    "openai": ProvedorOpenAI,
}


def familia_do_modelo(modelo: str) -> str:
    """'gemini-2.5-flash-lite' -> 'gemini'; 'gpt-4o-mini' -> 'openai'."""
    nome = modelo.lower()
    if nome.startswith("gemini"):
        return "gemini"
    if nome.startswith(("gpt", "o1", "o3", "o4")):
        return "openai"
    raise ValueError(f"Modelo sem provedor conhecido: {modelo}")


def criar_provedor(modelo: str, **kwargs) -> ProvedorLLM:
    return _FABRICAS[familia_do_modelo(modelo)](modelo=modelo, **kwargs)


__all__ = [
    "ERROR",
    "FP",
    "VP",
    "MODELO_GEMINI_PADRAO",
    "MODELO_OPENAI_PADRAO",
    "ProvedorGemini",
    "ProvedorLLM",
    "ProvedorOpenAI",
    "RespostaLLM",
    "criar_provedor",
    "familia_do_modelo",
]
