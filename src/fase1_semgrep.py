import json
import logging
import os
import re
import subprocess
from typing import NamedTuple

log = logging.getLogger(__name__)

SEMGREP = os.environ.get(
    "SEMGREP_BIN",
    r"C:\Users\Soous\AppData\Local\Programs\Python\Python314\Scripts\semgrep.exe",
)
# p/default (registry amplo) reproduz as CWEs do dataset; o p/golang enxuto
# perdia ~97 alertas (NAO_DETECTADO) por não ter regras para CWE-665/79/470/400/etc.
SEMGREP_CONFIG = os.environ.get("SEMGREP_CONFIG", "p/default")
SEMGREP_TIMEOUT = int(os.environ.get("SEMGREP_TIMEOUT", "240"))

# Versão da REGRA DE PAREAMENTO — a decisão de qual alerta do Semgrep pertence
# ao caso. Subir isto invalida todo o cache simbólico (ver src/cache_simbolico.py):
# uma entrada gravada sob regra anterior pode guardar um alerta que a regra
# corrente recusaria, e servi-la do disco reintroduziria o emparelhamento errado.
# É um eixo separado da versão do ruleset: o ruleset muda quando o Semgrep passa
# a enxergar coisas diferentes, esta muda quando a pipeline passa a aceitar como
# do caso um conjunto diferente de alertas.
#   1 — casamento de CWE por substring, com fallback de alerta único
#   2 — casamento por identificador completo de CWE, sem fallback
VERSAO_PAREAMENTO = 2

# Motivos de não-detecção. Os dois continuam em `Status_Semgrep = NAO_DETECTADO`
# — a CWE rotulada de fato não foi detectada nos dois casos —, mas dizem coisas
# diferentes sobre o motor simbólico: "não alcança esta fraqueza" e "viu outra
# fraqueza neste arquivo".
SEM_ALERTA = "SEM_ALERTA"
ALERTA_OUTRA_CWE = "ALERTA_OUTRA_CWE"
MOTIVO_NA = "N/A"          # houve emparelhamento: não há não-detecção a explicar


class ResultadoFase1(NamedTuple):
    """Decisão da Fase 1 sobre um caso.

    `alerta` é `None` quando nenhum alerta foi emparelhado; `motivo` diz por quê
    e `regras_nao_casadas` lista os `check_id` que dispararam sobre o arquivo sem
    casar com a CWE do gabarito — é a evidência de que o Semgrep leu o arquivo e
    enxergou outra fraqueza, afirmação diferente de "não viu nada".
    """

    alerta: dict | None
    motivo: str
    regras_nao_casadas: list


class SemgrepFileNotFoundError(Exception):
    """O arquivo alvo não existe no commit especificado."""


class SemgrepTimeoutError(Exception):
    """O Semgrep excedeu o tempo máximo."""


class SemgrepError(Exception):
    """Erro de execução do Semgrep (rc inesperado)."""


# `CWE-<dígitos>` no início do identificador. O `\b` impede que `CWE-77` seja
# extraído de `CWE-770`.
_RE_CWE = re.compile(r"^\s*CWE-(\d+)\b", re.IGNORECASE)


def _numero_cwe(texto):
    """Número da CWE em `'CWE-89: Improper Neutralization...'`, ou None."""
    m = _RE_CWE.match(str(texto))
    return int(m.group(1)) if m else None


def _cwe_nas_tags(tags, cwe_id):
    """Verifica se alguma tag da regra (SARIF) declara EXATAMENTE esta CWE.

    No SARIF do Semgrep, a CWE aparece nas tags da regra como uma string do
    tipo 'CWE-89: Improper Neutralization...'.

    A comparação é pelo identificador inteiro, e não por substring: `CWE-77` e
    `CWE-770` são fraquezas distintas, e um casamento textual emparelharia o
    caso à regra errada sem que nada no CSV denunciasse. Os pares em risco
    existem na população — CWE-20 contra CWE-200/209, CWE-77 contra CWE-770,
    CWE-79 contra CWE-798.
    """
    alvo = _numero_cwe(cwe_id)
    if alvo is None:
        return False
    return any(_numero_cwe(t) == alvo for t in tags)


def _linha_inicial(result: dict) -> int:
    loc = (result.get("locations") or [{}])[0]
    return loc.get("physicalLocation", {}).get("region", {}).get("startLine", 1)


def _check_id(result: dict) -> str:
    return str(result.get("ruleId") or "regra desconhecida")


def _normalizar(result: dict) -> dict:
    """Converte um 'result' do SARIF no formato consumido pela Fase 2.

    Mantém o mesmo shape que a Fase 2 espera (start.line / check_id /
    extra.message), independentemente do motor ser SARIF ou JSON.
    """
    return {
        "start": {"line": _linha_inicial(result)},
        "check_id": _check_id(result),
        "extra": {"message": (result.get("message") or {}).get("text", "")},
    }


def executar_semgrep(caminho_arquivo: str, cwe: str) -> ResultadoFase1:
    """Roda o Semgrep no arquivo-alvo e devolve o alerta cuja CWE casa com a
    do dataset.

    O arquivo já vem resolvido por src/fonte.py (cache, clone local ou rede) —
    esta fase não clona nem faz checkout. O Semgrep é invocado sobre o arquivo
    isolado, que no engine OSS é exatamente o escopo de análise disponível.

    Devolve `ResultadoFase1`. Com `alerta=None` o caso é NAO_DETECTADO, e o
    motivo distingue `SEM_ALERTA` de `ALERTA_OUTRA_CWE`.
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

    # Uma execução válida com --sarif SEMPRE emite um documento JSON com `runs`,
    # inclusive quando não há achado algum. Stdout vazio ou ilegível é falha de
    # ESTEIRA, não silêncio do motor, e a diferença é crítica: `SEM_ALERTA` é
    # gravado no cache e vira ponto cego permanente do Semgrep, enquanto a falha
    # de esteira não é cacheada e o caso é recomputado na rodada seguinte.
    # Sem esta checagem, um `settings.yml` corrompido por queda de energia
    # produziu 200 não-detecções falsas — o Semgrep saía com rc=1 e stdout
    # vazio, e o `or "{}"` transformava isso em "nenhum achado".
    saida = res.stdout.decode("utf-8", "ignore").strip()
    erro = res.stderr.decode("utf-8", "ignore").strip()
    if not saida:
        raise SemgrepError(
            f"Semgrep rc={res.returncode} não produziu SARIF em "
            f"{os.path.basename(caminho_arquivo)}: {erro[:200]}")
    try:
        data = json.loads(saida)
    except json.JSONDecodeError as e:
        raise SemgrepError(
            f"Semgrep rc={res.returncode} produziu SARIF ilegível em "
            f"{os.path.basename(caminho_arquivo)}: {e}") from e
    if "runs" not in data:
        raise SemgrepError(
            f"Semgrep rc={res.returncode} produziu JSON sem 'runs' em "
            f"{os.path.basename(caminho_arquivo)}: {saida[:200]}")

    runs = data.get("runs", [])
    run = runs[0] if runs else {}
    results = run.get("results", [])

    if not results and res.returncode not in (0, 1):
        raise SemgrepError(f"Semgrep rc={res.returncode}: {erro[:200]}")

    # Mapa ruleId -> tags da regra (onde a CWE aparece no SARIF do Semgrep)
    regras = {
        regra.get("id"): regra.get("properties", {}).get("tags", [])
        for regra in run.get("tool", {}).get("driver", {}).get("rules", [])
    }

    # Condição necessária E suficiente: a regra que emitiu o alerta declara a
    # CWE do gabarito. Havia aqui um fallback que aceitava o alerta quando ele
    # era o único do arquivo, para cobrir regra sem tag de CWE explícita; ele
    # saiu porque não distinguia "a regra não declara CWE" de "a regra declara
    # OUTRA CWE", e era o segundo grupo que dominava na prática — o alerta
    # enviado ao LLM não tinha relação com a fraqueza rotulada, e o veredito era
    # pontuado contra um gabarito que não lhe pertencia. Nada ocupa o lugar
    # dele: emparelhar por proximidade de CWE exigiria um mapeamento
    # CWE<->regra, que viraria variável nova do experimento.
    casados = [r for r in results
               if _cwe_nas_tags(regras.get(r.get("ruleId"), []), cwe)]
    if casados:
        # Ordem explícita, e não a de saída do Semgrep: ela é estável na
        # prática, mas é detalhe interno da ferramenta, não garantia.
        casados.sort(key=lambda r: (_linha_inicial(r), _check_id(r)))
        return ResultadoFase1(_normalizar(casados[0]), MOTIVO_NA, [])

    if not results:
        return ResultadoFase1(None, SEM_ALERTA, [])

    # O Semgrep leu o arquivo e enxergou outra fraqueza. Os `check_id` vão
    # deduplicados e em ordem alfabética — alfabética, e não de aparição, porque
    # o campo existe para comparar CSVs de rodadas diferentes entre si.
    return ResultadoFase1(None, ALERTA_OUTRA_CWE,
                          sorted({_check_id(r) for r in results}))
