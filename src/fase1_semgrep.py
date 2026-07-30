import json
import logging
import os
import subprocess

log = logging.getLogger(__name__)

SEMGREP = os.environ.get(
    "SEMGREP_BIN",
    r"C:\Users\Soous\AppData\Local\Programs\Python\Python314\Scripts\semgrep.exe",
)
# p/default (registry amplo) reproduz as CWEs do dataset; o p/golang enxuto
# perdia ~97 alertas (NAO_DETECTADO) por não ter regras para CWE-665/79/470/400/etc.
SEMGREP_CONFIG = os.environ.get("SEMGREP_CONFIG", "p/default")
SEMGREP_TIMEOUT = int(os.environ.get("SEMGREP_TIMEOUT", "240"))


class SemgrepFileNotFoundError(Exception):
    """O arquivo alvo não existe no commit especificado."""


class SemgrepTimeoutError(Exception):
    """O Semgrep excedeu o tempo máximo."""


class SemgrepError(Exception):
    """Erro de execução do Semgrep (rc inesperado)."""


def _cwe_nas_tags(tags, cwe_id):
    """Verifica se as tags da regra (SARIF) mencionam a CWE especificada.

    No SARIF do Semgrep, a CWE aparece nas tags da regra como uma string do
    tipo 'CWE-89: Improper Neutralization...'.
    """
    cwe_upper = cwe_id.upper()
    return any(cwe_upper in str(t).upper() for t in tags)


def _normalizar(result: dict) -> dict:
    """Converte um 'result' do SARIF no formato consumido pela Fase 2.

    Mantém o mesmo shape que a Fase 2 espera (start.line / check_id /
    extra.message), independentemente do motor ser SARIF ou JSON.
    """
    loc = (result.get("locations") or [{}])[0]
    region = loc.get("physicalLocation", {}).get("region", {})
    return {
        "start": {"line": region.get("startLine", 1)},
        "check_id": result.get("ruleId", "regra desconhecida"),
        "extra": {"message": (result.get("message") or {}).get("text", "")},
    }


def executar_semgrep(caminho_arquivo: str, cwe: str) -> dict | None:
    """Roda o Semgrep no arquivo-alvo e devolve o alerta cuja CWE casa com a
    do dataset.

    O arquivo já vem resolvido por src/fonte.py (cache, clone local ou rede) —
    esta fase não clona nem faz checkout. O Semgrep é invocado sobre o arquivo
    isolado, que no engine OSS é exatamente o escopo de análise disponível.

    Retorna None se o Semgrep não emitiu alerta para esta CWE (NAO_DETECTADO).
    Levanta exceções categorizadas para falhas de esteira.
    """
    if not os.path.exists(caminho_arquivo):
        raise SemgrepFileNotFoundError(
            f"Arquivo não encontrado: {caminho_arquivo}")

    # Marca de invocação real do motor simbólico: é por este registro que se
    # verifica que o cache simbólico está evitando reexecuções (ver
    # src/cache_simbolico.py).
    log.debug("semgrep invocado em %s (%s)", caminho_arquivo, cwe)

    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    try:
        res = subprocess.run(
            [SEMGREP, "--config", SEMGREP_CONFIG, "--sarif", "--quiet",
             caminho_arquivo],
            capture_output=True, timeout=SEMGREP_TIMEOUT, env=env,
        )
    except subprocess.TimeoutExpired:
        raise SemgrepTimeoutError(
            f"Semgrep excedeu {SEMGREP_TIMEOUT}s em {os.path.basename(caminho_arquivo)}.")

    data = json.loads(res.stdout.decode("utf-8", "ignore") or "{}")
    runs = data.get("runs", [])
    run = runs[0] if runs else {}
    results = run.get("results", [])

    if not results and res.returncode not in (0, 1):
        raise SemgrepError(
            f"Semgrep rc={res.returncode}: "
            f"{res.stderr.decode('utf-8', 'ignore')[:200]}")

    # Mapa ruleId -> tags da regra (onde a CWE aparece no SARIF do Semgrep)
    regras = {
        regra.get("id"): regra.get("properties", {}).get("tags", [])
        for regra in run.get("tool", {}).get("driver", {}).get("rules", [])
    }

    # Prioridade: alerta cuja regra menciona a CWE do dataset
    for r in results:
        if _cwe_nas_tags(regras.get(r.get("ruleId"), []), cwe):
            return _normalizar(r)

    # Fallback: se só há um alerta no arquivo, assume que é o mesmo
    # (regra sem tag de CWE explícita)
    if len(results) == 1:
        return _normalizar(results[0])

    return None  # Semgrep não detectou esta CWE → NAO_DETECTADO
