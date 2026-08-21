"""
fases3_4_llm.py — Fases 3 e 4: montagem do prompt e coleta do veredito.

Este módulo NÃO fala com a rede. Ele decide o que perguntar; quem pergunta é a
camada de provedores (`src/provedores/`). A separação é o que permite trocar o
modelo sem tocar em nada aqui — o eixo "modelo" da matriz 2x2 tem que ser
variável independente do eixo "prompt".
"""
import logging

from .prompts import montar_prompt
from .provedores import RespostaLLM, criar_provedor

log = logging.getLogger(__name__)

# Provedor reaproveitado entre chamadas quando nenhum é informado: preserva o
# throttle entre casos (uma instância nova zeraria o intervalo mínimo a cada
# caso e estouraria a cota).
_provedor_padrao = None


def _obter_provedor_padrao():
    global _provedor_padrao
    if _provedor_padrao is None:
        from .config import MODELO_LLM
        _provedor_padrao = criar_provedor(MODELO_LLM)
    return _provedor_padrao


def avaliar_vulnerabilidade(contexto_hidratado: str, cwe_id: str,
                            cwe_name: str = "", description: str = "",
                            provedor=None, tipo_prompt: str = "especialista",
                            ficha=None) -> dict:
    """Monta o prompt do tipo pedido e devolve o veredito no formato do CSV.

    Devolve dict (`{"verdict", "reasoning"}`) por compatibilidade com
    `src/fase5_auditoria.registrar_resultado`; quem precisa de tokens e custo
    usa `avaliar` diretamente.
    """
    return avaliar(contexto_hidratado, cwe_id, cwe_name, description,
                   provedor=provedor, tipo_prompt=tipo_prompt,
                   ficha=ficha).como_dict()


def avaliar(contexto_hidratado: str, cwe_id: str, cwe_name: str = "",
            description: str = "", provedor=None,
            tipo_prompt: str = "especialista", ficha=None) -> RespostaLLM:
    """Mesma coisa, devolvendo a `RespostaLLM` completa (tokens, custo, modelo)."""
    prompt = montar_prompt(tipo_prompt, contexto=contexto_hidratado,
                           cwe_id=cwe_id, cwe_name=cwe_name,
                           description=description, ficha=ficha)
    provedor = provedor or _obter_provedor_padrao()
    return provedor.avaliar(prompt)
