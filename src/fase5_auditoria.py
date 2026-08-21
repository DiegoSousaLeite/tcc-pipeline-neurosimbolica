import csv
import logging
from typing import Dict, Optional

from .config import MODELO_LLM, PROMPT_TYPE

log = logging.getLogger(__name__)

# ID_Caso permanece na coluna 0 para o checkpoint de recuperação do run_pipeline.py.
#
# A partir da Parte 2 o checkpoint é pela TRIPLA (ID_Caso, Modelo_LLM,
# Tipo_Prompt): a mesma população roda em quatro braços, e indexar só pelo
# ID_Caso faria o segundo braço sair vazio.
CABECALHO = [
    "ID_Caso", "Repositorio", "CWE",
    "Origem",                  # FP | TP_ouro | TP_prata | TP_dataset
    "Modelo_LLM", "Tipo_Prompt",
    "Gabarito",                # vulneravel | seguro
    "Status_Semgrep",          # DETECTADO | NAO_DETECTADO | <categoria de erro>
    "Classificacao_Semgrep",   # Matriz de COBERTURA do Semgrep
    "Veredito_LLM",            # VP | FP | ERROR | N/A
    "Classificacao_LLM",       # Matriz de ACERTO do LLM
    "Tempo_Execucao_s",
    "Justificativa",
    # --- Parte 2 ---
    "Num_Locations",           # locations da entrada de origem, ANTES dos filtros
    "Ficha_CWE",               # especifica | fallback | N/A
    "Versao_Prompt",           # hash curto do template usado
    "Hash_Catalogo",           # SHA-256 do catálogo vigente na execução
    "Tokens_Entrada", "Tokens_Saida", "Custo_USD",
    # Motivo da não-detecção, em coluna própria e não em valor novo de
    # `Status_Semgrep`: o checkpoint por tripla, o cache e as métricas comparam
    # a string `NAO_DETECTADO` diretamente, e um terceiro valor de status
    # quebraria cada um deles de um jeito diferente, nenhum ruidosamente.
    # No FIM do cabeçalho porque `registrar_resultado` escreve a linha
    # posicionalmente e `COLUNAS_PARTE2` é definido por fatia.
    "Motivo_Nao_Deteccao",     # SEM_ALERTA | ALERTA_OUTRA_CWE | N/A
    "Regras_Nao_Casadas",      # check_id separados por ';', ordem alfabética
]

# Colunas que os CSVs da Parte 1 não têm — e às quais as duas de pareamento se
# somaram depois. Quem lê um CSV antigo trata a ausência delas como
# "indisponível", nunca como erro.
COLUNAS_PARTE2 = CABECALHO[13:]

CATEGORIAS_ERRO = {
    "FETCH_FAIL",                    # falha ao obter o arquivo-alvo (rede/git)
    "CLONE_FAIL", "CHECKOUT_FAIL",   # legado: CSVs gerados antes do cache
    "SEMGREP_TIMEOUT", "SEMGREP_ERROR", "SEMGREP_FILE_NOT_FOUND",
    "API_ERROR", "ERRO_DESCONHECIDO",
}


def inicializar_relatorio(caminho_csv: str):
    """Cria o cabeçalho do arquivo CSV se for uma nova execução."""
    with open(caminho_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(CABECALHO)


def classificar_cobertura_semgrep(gabarito: str, detectado: bool) -> str:
    """Matriz de COBERTURA: avalia o Semgrep vs o gabarito.

    Mede a cobertura do motor simbólico e expõe pontos cegos (FN). Não mede o LLM.
    """
    if detectado:
        if gabarito == "vulneravel":
            return "Semgrep VP (detectou vuln real)"
        return "Semgrep FP (ruído sobre código seguro)"
    else:
        if gabarito == "vulneravel":
            return "Semgrep FN (ponto cego simbólico)"
        return "Semgrep VN (silêncio correto)"


def classificar_acerto_llm(gabarito: str, verdict_llm: str) -> str:
    """Matriz de ACERTO do LLM. Avalia a decisão neural contra o gabarito."""
    previsao = (
        "vulneravel" if verdict_llm == "VP"
        else "seguro" if verdict_llm == "FP"
        else "ERROR"
    )
    if previsao == "ERROR":
        return "Erro de Inferência (API_ERROR)"
    if gabarito == "vulneravel" and previsao == "vulneravel":
        return "Verdadeiro Positivo (Acerto)"
    if gabarito == "seguro" and previsao == "seguro":
        return "Verdadeiro Negativo (Acerto)"
    if gabarito == "vulneravel" and previsao == "seguro":
        return "Falso Negativo (Falha Crítica)"
    return "Falso Positivo (Ruído Mantido)"


def registrar_resultado(
    caminho_csv: str,
    caso_id: str,
    repo_name: str,
    cwe: str,
    origem: str,
    gabarito: str,
    status_semgrep: str,
    tempo_exec: float,
    resposta_llm: Optional[Dict] = None,
    erro_msg: Optional[str] = None,
    modelo: str = MODELO_LLM,
    tipo_prompt: str = PROMPT_TYPE,
    num_locations: int = 1,
    ficha_cwe: str = "N/A",
    versao_prompt: str = "",
    hash_catalogo: str = "",
    tokens_entrada: int = 0,
    tokens_saida: int = 0,
    custo_usd: float = 0.0,
    motivo_nao_deteccao: str = "N/A",
    regras_nao_casadas=(),
):
    """Consolida um caso no relatório, mantendo as duas matrizes separadas.

    - status_semgrep == "DETECTADO":    preenche cobertura Semgrep E acerto LLM.
    - status_semgrep == "NAO_DETECTADO": preenche só a cobertura (LLM = N/A) e
      registra qual dos dois motivos produziu a não-detecção.
    - status_semgrep em CATEGORIAS_ERRO: falha de esteira, fora das duas matrizes.
    """
    tempo_fmt = f"{tempo_exec:.2f}"
    # Só a não-detecção tem motivo a explicar: nos demais estados as colunas
    # saem neutras, para que o campo vazio não seja lido como informação
    # perdida sobre um caso `ALERTA_OUTRA_CWE`.
    motivo = "N/A"
    regras = ""

    if status_semgrep in CATEGORIAS_ERRO:
        classificacao_semgrep = "N/A (Falha de Esteira)"
        veredito_llm = "N/A"
        classificacao_llm = "N/A (Falha de Esteira)"
        justificativa = erro_msg or ""

    elif status_semgrep == "NAO_DETECTADO":
        classificacao_semgrep = classificar_cobertura_semgrep(gabarito, detectado=False)
        veredito_llm = "N/A"
        classificacao_llm = "N/A (Semgrep nao detectou)"
        justificativa = "Semgrep nao emitiu alerta para esta CWE (cobertura simbolica)."
        motivo = motivo_nao_deteccao or "N/A"
        regras = (regras_nao_casadas if isinstance(regras_nao_casadas, str)
                  else ";".join(regras_nao_casadas))

    else:  # DETECTADO
        classificacao_semgrep = classificar_cobertura_semgrep(gabarito, detectado=True)
        resposta_llm = resposta_llm or {}
        veredito_llm = resposta_llm.get("verdict", "ERROR")
        classificacao_llm = classificar_acerto_llm(gabarito, veredito_llm)
        justificativa = resposta_llm.get("reasoning", "")

    with open(caminho_csv, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            caso_id, repo_name, cwe,
            origem,
            modelo, tipo_prompt,
            gabarito,
            status_semgrep,
            classificacao_semgrep,
            veredito_llm,
            classificacao_llm,
            tempo_fmt,
            justificativa,
            num_locations,
            ficha_cwe,
            versao_prompt,
            hash_catalogo,
            tokens_entrada,
            tokens_saida,
            f"{custo_usd:.8f}",
            motivo,
            regras,
        ])

    log.info("    [Cobertura Semgrep] %s", classificacao_semgrep)
    log.info("    [Acerto LLM]        %s | %ss", classificacao_llm, tempo_fmt)
