import csv
from typing import Dict, Optional
from .config import MODELO_LLM, PROMPT_TYPE

# Ordem das colunas do relatório científico (formato CSV).
# ID_Alerta permanece na coluna 0 para o checkpoint de recuperação do main.py.
CABECALHO = [
    'ID_Alerta', 'Repositorio', 'CWE',
    'Modelo_LLM', 'Tipo_Prompt',
    'Gabarito_SastBench',
    'Status_CodeQL',          # DETECTADO | NAO_DETECTADO | <categoria de erro da esteira>
    'Classificacao_CodeQL',   # Matriz de COBERTURA do motor simbólico (cross-tool)
    'Veredito_LLM',           # TP | FP | ERROR | N/A
    'Classificacao_LLM',      # Matriz de ACERTO do LLM (apenas sobre alertas DETECTADOS)
    'Tempo_Execucao_s',
    'Justificativa',
]

# Categorias de falha da esteira que NÃO entram em nenhuma das duas matrizes,
# mas ficam registradas para auditoria (requisito C).
CATEGORIAS_ERRO = {
    "CLONE_FAIL", "CHECKOUT_FAIL", "CODEQL_DB_FAIL",
    "CODEQL_TIMEOUT", "SARIF_MISSING", "API_ERROR", "ERRO_DESCONHECIDO",
}


def inicializar_relatorio(caminho_csv: str):
    """Cria o cabeçalho do arquivo CSV se for uma nova execução."""
    with open(caminho_csv, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(CABECALHO)


def classificar_cobertura_codeql(ground_truth: str, detectado: bool) -> str:
    """Matriz de COBERTURA: avalia o motor simbólico (CodeQL) vs o gabarito.

    Mede a concordância entre ferramentas (cross-tool agreement) e expõe o
    'ponto cego simbólico' (Falsos Negativos nativos do SAST). NÃO mede o LLM.
    """
    if detectado:
        if ground_truth == "true_positive":
            return "CodeQL VP (detectou vuln real)"
        return "CodeQL FP (ruído sobre código seguro)"
    else:
        if ground_truth == "true_positive":
            return "CodeQL FN (ponto cego simbólico)"
        return "CodeQL VN (silêncio correto)"


def classificar_acerto_llm(ground_truth: str, verdict_llm: str) -> str:
    """Matriz de ACERTO do LLM. Só deve ser chamada quando o CodeQL DETECTOU
    o alerta, garantindo que a decisão avaliada é de fato do modelo neural.
    """
    previsao = (
        "true_positive" if verdict_llm == "TP"
        else "false_positive" if verdict_llm == "FP"
        else "ERROR"
    )

    if previsao == "ERROR":
        return "Erro de Inferência (API_ERROR)"
    if ground_truth == "true_positive" and previsao == "true_positive":
        return "True Positive (Acerto)"
    if ground_truth == "false_positive" and previsao == "false_positive":
        return "True Negative (Acerto)"
    if ground_truth == "true_positive" and previsao == "false_positive":
        return "False Negative (Falha Crítica)"
    return "False Positive (Ruído Mantido)"


def registrar_resultado(
    caminho_csv: str,
    finding_id: str,
    repo_name: str,
    cwe: str,
    ground_truth: str,
    status_codeql: str,
    tempo_exec: float,
    resposta_llm: Optional[Dict] = None,
    erro_msg: Optional[str] = None,
):
    """Consolida uma amostra no relatório, mantendo as duas matrizes separadas.

    - status_codeql == "DETECTADO":     preenche cobertura E acerto do LLM.
    - status_codeql == "NAO_DETECTADO": preenche só a cobertura (LLM = N/A).
    - status_codeql em CATEGORIAS_ERRO: falha de esteira, fora das duas matrizes.
    """
    tempo_fmt = f"{tempo_exec:.2f}"

    if status_codeql in CATEGORIAS_ERRO:
        classificacao_codeql = "N/A (Falha de Esteira)"
        veredito_llm = "N/A"
        classificacao_llm = "N/A (Falha de Esteira)"
        justificativa = erro_msg or ""

    elif status_codeql == "NAO_DETECTADO":
        # Ponto cego simbólico: conta SÓ para a cobertura do CodeQL.
        # O LLM nunca foi acionado, então fica explicitamente fora da matriz dele.
        classificacao_codeql = classificar_cobertura_codeql(ground_truth, detectado=False)
        veredito_llm = "N/A"
        classificacao_llm = "N/A (CodeQL nao detectou)"
        justificativa = "CodeQL nao emitiu alerta para este arquivo (cobertura simbolica)."

    else:  # DETECTADO
        classificacao_codeql = classificar_cobertura_codeql(ground_truth, detectado=True)
        resposta_llm = resposta_llm or {}
        veredito_llm = resposta_llm.get("verdict", "ERROR")
        classificacao_llm = classificar_acerto_llm(ground_truth, veredito_llm)
        justificativa = resposta_llm.get("reasoning", "")

    with open(caminho_csv, 'a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow([
            finding_id, repo_name, cwe,
            MODELO_LLM, PROMPT_TYPE,
            ground_truth,
            status_codeql,
            classificacao_codeql,
            veredito_llm,
            classificacao_llm,
            tempo_fmt,
            justificativa,
        ])

    print(f"    [Cobertura CodeQL] {classificacao_codeql}")
    print(f"    [Acerto LLM]       {classificacao_llm} | {tempo_fmt}s")
