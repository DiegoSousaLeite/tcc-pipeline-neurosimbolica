"""Camada de provedores de LLM.

A matriz 2x2 da Parte 2 cruza dois modelos (Gemini e GPT) com dois tipos de
prompt. Para que o eixo do modelo seja de fato uma variável independente, o
resto da pipeline não pode saber qual provedor está em uso: `avaliar(prompt)`
devolve sempre uma `RespostaLLM`, com veredito já validado e custo já derivado.
"""
from .base import ERROR, FP, VP, ProvedorLLM, RespostaLLM
from .gemini import ProvedorGemini
from .gemini_lote import ProvedorGeminiLote
from .lote import EXPIRADO, ProvedorLote
from .ollama import PREFIXO as PREFIXO_OLLAMA
from .ollama import ProvedorOllama
from .openai import ProvedorOpenAI
from .openai_lote import ProvedorOpenAILote

# Modelos padrão de cada braço da matriz. Ficam aqui, e não no config, porque
# são identidade do experimento e vão para o manifesto da rodada.
MODELO_GEMINI_PADRAO = "gemini-2.5-flash-lite"
MODELO_OPENAI_PADRAO = "gpt-4o-mini"
# Não entra na matriz padrão: o braço local só roda quando nomeado.
MODELO_OLLAMA_PADRAO = "ollama:qwen2.5-coder:7b"

_FABRICAS = {
    "gemini": ProvedorGemini,
    "openai": ProvedorOpenAI,
    "ollama": ProvedorOllama,
}


def familia_do_modelo(modelo: str) -> str:
    """'gemini-2.5-flash-lite' -> 'gemini'; 'ollama:qwen2.5-coder:7b' -> 'ollama'."""
    nome = modelo.lower()
    # O namespace explícito vem ANTES dos prefixos comerciais: os nomes de
    # modelo aberto não são particionáveis por prefixo de forma estável
    # (`gemma2` é modelo do Google servido localmente; `gemini` é a API dele).
    if nome.startswith(PREFIXO_OLLAMA):
        return "ollama"
    if nome.startswith("gemini"):
        return "gemini"
    if nome.startswith(("gpt", "o1", "o3", "o4")):
        return "openai"
    raise ValueError(f"Modelo sem provedor conhecido: {modelo}")


def criar_provedor(modelo: str, **kwargs) -> ProvedorLLM:
    return _FABRICAS[familia_do_modelo(modelo)](modelo=modelo, **kwargs)


# Só quem implementa a entrega em lote entra aqui. O local fica de fora por
# natureza: não existe API de lote para inferência local, e o gargalo dela é
# GPU, não vazão de rede.
_FABRICAS_LOTE = {
    "gemini": ProvedorGeminiLote,
    "openai": ProvedorOpenAILote,
}


class LoteNaoSuportado(ValueError):
    """Modo de envio em lote pedido para um provedor que não o implementa."""


def exigir_suporte_lote(modelo: str) -> str:
    """Família do modelo, ou erro que NOMEIA o provedor sem suporte a lote.

    Barato de propósito: roda antes de montar qualquer prompt e antes da Fase 1,
    para que uma rodada não gaste Semgrep até descobrir que não pode enviar.
    """
    familia = familia_do_modelo(modelo)
    if familia not in _FABRICAS_LOTE:
        raise LoteNaoSuportado(
            f"O provedor '{familia}' (modelo {modelo}) não implementa envio em "
            f"lote. Provedores com lote: {', '.join(sorted(_FABRICAS_LOTE))}. "
            f"Use --modo-envio sincrono para este modelo.")
    return familia


def criar_provedor_lote(modelo: str, **kwargs) -> ProvedorLote:
    return _FABRICAS_LOTE[exigir_suporte_lote(modelo)](modelo=modelo, **kwargs)


__all__ = [
    "ERROR",
    "EXPIRADO",
    "FP",
    "VP",
    "LoteNaoSuportado",
    "ProvedorGeminiLote",
    "ProvedorOpenAILote",
    "ProvedorLote",
    "criar_provedor_lote",
    "exigir_suporte_lote",
    "MODELO_GEMINI_PADRAO",
    "MODELO_OLLAMA_PADRAO",
    "MODELO_OPENAI_PADRAO",
    "ProvedorGemini",
    "ProvedorLLM",
    "ProvedorOllama",
    "ProvedorOpenAI",
    "RespostaLLM",
    "criar_provedor",
    "familia_do_modelo",
]
