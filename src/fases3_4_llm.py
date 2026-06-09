import json
import requests
from .config import URL_API_GEMINI

def avaliar_vulnerabilidade(contexto_hidratado: str, cwe_id: str) -> dict:
    """Monta o prompt especialista e coleta o veredito do modelo de fronteira."""
    prompt = f"""
    Atue como Arquiteto de Segurança Sênior especialista em Go (Golang).
    Analise o alerta de Análise Estática abaixo e classifique como FALSO POSITIVO (FP) ou VERDADEIRO POSITIVO (TP).

    DIRETRIZES DE TRIAGEM ({cwe_id}):
    1. Verifique rigorosamente se a variável vulnerável atinge o 'Sink' (banco de dados, resposta HTTP, log) sem sanitização.
    2. Avalie funções de mitigação comuns em Go (ex: html/template, validações de interface, pacotes standard de sanitização).
    3. Se houver mitigação efetiva ou a rota for inalcançável, é FP. Caso contrário, é TP.

    DADOS DA TRILHA E CÓDIGO FONTE:
    {contexto_hidratado}

    RESPONDA ESTRITAMENTE EM JSON, contendo duas chaves exatas:
    {{"verdict": "TP" ou "FP", "reasoning": "Sua justificativa técnica e direta"}}
    """

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.0, 
            "responseMimeType": "application/json"
        }
    }

    try:
        response = requests.post(URL_API_GEMINI, json=payload)
        response.raise_for_status()
        resposta_json = response.json()
        texto_resposta = resposta_json['candidates'][0]['content']['parts'][0]['text']
        return json.loads(texto_resposta)
    except Exception as e:
        return {"verdict": "ERROR", "reasoning": f"Falha de comunicação com a API: {str(e)}"}