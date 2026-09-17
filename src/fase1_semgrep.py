import json
import logging
import os
import re
import subprocess
from typing import NamedTuple

log = logging.getLogger(__name__)

# Diretório do binário proprietário, instalado por `semgrep install-semgrep-pro`.
# Consultado só para registrar presença — nunca para decidir invocação.
_BIN_PRO = "semgrep-core-proprietary"

SEMGREP = os.environ.get(
    "SEMGREP_BIN",
    r"C:\Users\Soous\AppData\Local\Programs\Python\Python314\Scripts\semgrep.exe",
)
# --- conjunto de rulesets ------------------------------------------------
#
# p/default (registry amplo) reproduz as CWEs do dataset; o p/golang enxuto
# perdia ~97 alertas (NAO_DETECTADO) por não ter regras para CWE-665/79/470/400/etc.
#
# A configuração aceita MAIS DE UM ruleset porque acrescentar cobertura não pode
# custar a cobertura existente: trocar de ruleset já foi avaliado e recusado, e
# a união é a única forma de somar sem subtrair. O padrão permanece unitário —
# ligar um segundo ruleset muda o conjunto de alertas e, portanto, o objeto que
# o braço neural tria; as Rodadas 1–3 mediram `p/default` sozinho, e a
# comparabilidade só pode se perder por decisão explícita.

# Separador da lista. Vírgula, e não espaço nem `os.pathsep`: identificador do
# registry (`p/default`) e caminho local (`regras/go`) contêm barra, e no
# Windows `os.pathsep` é `;`, que o shell come antes de a variável chegar aqui.
_SEPARADOR_CONFIG = ","


def _configs_de(texto):
    """Rulesets declarados numa string de configuração, na ordem em que aparecem.

    Entradas vazias são descartadas em silêncio (`"p/default,"` é um typo, não
    um ruleset anônimo), mas a lista INTEIRA vazia não vira `p/default` por
    omissão: quem apagou a variável pediu algo, e `montar_comando` recusa em vez
    de invocar o motor sem regras.
    """
    return tuple(p.strip() for p in str(texto).split(_SEPARADOR_CONFIG)
                 if p.strip())


SEMGREP_CONFIGS = _configs_de(os.environ.get("SEMGREP_CONFIG", "p/default"))
# Primeiro ruleset configurado. Mantido porque consumidores de um ruleset só
# (snapshot do catálogo, URL do registry) continuam existindo; NÃO é a
# identidade da configuração — para isso existe `identidade_conjunto`.
SEMGREP_CONFIG = SEMGREP_CONFIGS[0] if SEMGREP_CONFIGS else ""
SEMGREP_TIMEOUT = int(os.environ.get("SEMGREP_TIMEOUT", "240"))

# Procedência de um ruleset. A distinção é metodológica, não organizacional: um
# ruleset publicado no registry não foi escrito olhando para a nossa população, e
# medir com ele não levanta a objeção de ajuste ao conjunto de teste. Um ruleset
# que sai de arquivo local pode ter sido, e o texto da monografia precisa tratar
# os dois casos de forma diferente.
PROCEDENCIA_TERCEIROS = "terceiros"
PROCEDENCIA_PROPRIA = "propria"

# `p/`, `r/` e `s/` são os prefixos do registry do Semgrep; URL é registry
# remoto por outro caminho.
_RE_REGISTRY = re.compile(r"^(?:[prs]/|https?://)", re.IGNORECASE)


class ConfiguracaoVaziaError(Exception):
    """Nenhum ruleset configurado.

    É erro, e não invocação sem `--config`: uma execução sem regras produz zero
    alertas e faria a população INTEIRA parecer não detectada — o mesmo modo de
    falha silenciosa do `settings.yml` corrompido, que já custou 200
    não-detecções falsas a este projeto.
    """


def procedencia(config) -> str:
    """Este ruleset é publicado por terceiros ou sai de arquivo nosso?

    Tudo que não é identificador do registry conta como próprio, inclusive
    caminho fora deste repositório. É o lado conservador: classificar como de
    terceiros um arquivo que ninguém publicou dispensaria a ressalva
    metodológica justamente onde ela pode ser necessária.
    """
    return (PROCEDENCIA_TERCEIROS if _RE_REGISTRY.match(str(config))
            else PROCEDENCIA_PROPRIA)


def identidade_conjunto(configs=None) -> str:
    """Identidade do CONJUNTO de rulesets configurado.

    Insensível à ordem (os nomes são ordenados) porque a ordem não altera a
    união dos achados, e fazê-la alterar a identidade invalidaria cache por um
    detalhe sem significado. Distinta para conjuntos distintos, inclusive quando
    um contém o outro: `p/default` e `p/default+regras/go` não colidem.

    É nome legível, e não hash, por dois motivos. O conjunto unitário fica
    IDÊNTICO ao nome do ruleset — então as ~1.700 entradas de cache gravadas
    quando a configuração era um ruleset só continuam válidas, sem migração. E
    quem abrir um manifesto meses depois lê a configuração em vez de um digest
    que só o código sabe traduzir.
    """
    alvo = SEMGREP_CONFIGS if configs is None else tuple(configs)
    if not alvo:
        raise ConfiguracaoVaziaError(
            "nenhum ruleset configurado: SEMGREP_CONFIG está vazia. Uma "
            "execução sem regras produziria zero alertas e faria toda a "
            "população parecer não detectada.")
    return "+".join(sorted(set(alvo)))


def rulesets_configurados(configs=None) -> list:
    """`[{'config': ..., 'procedencia': ...}]`, para o manifesto da rodada."""
    alvo = SEMGREP_CONFIGS if configs is None else tuple(configs)
    return [{"config": c, "procedencia": procedencia(c)} for c in alvo]


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

# --- identidade do motor simbólico ---------------------------------------
#
# Enquanto houve um motor só, pressupor qual era foi inofensivo. A partir do
# momento em que dois motores produzem SARIF diferente sobre o MESMO arquivo, um
# resultado sem identidade não sabe dizer o que o gerou — e a auditoria não tem
# como recuperar a informação depois.

EDICAO_CE = "ce"
EDICAO_PRO = "pro"

# Registro gravado pelo portão (`scripts/verificar_pro.py`). A ativação do modo
# entre-arquivos exige um destes com classificação `viavel`: sem ele, pedir o
# modo aborta em vez de cair no CE em silêncio.
VIABILIDADE_GLOB = "viabilidade_pro_*.json"
CLASSIFICACAO_VIAVEL = "viavel"


class ModoIndisponivelError(Exception):
    """O modo entre-arquivos foi pedido sem viabilidade verificada.

    É erro, e não degradação para o CE: o modo de falha a evitar é o silencioso.
    Se o Pro for pedido e o Semgrep cair de volta no CE sem avisar, a rodada
    produz números CE rotulados como Pro e nada no CSV denuncia isso.
    """


class MotorSimbolico(NamedTuple):
    """Quem produziu um resultado simbólico.

    `binario_pro_disponivel` não estava previsto no desenho e entrou por
    medição: instalar o binário proprietário mudou o comportamento do CE nesta
    máquina (com `--dataflow-traces`, de 0 para 1 trilha, e de ~6 s para ~16 s
    no mesmo alvo), mesmo sem `--pro` e mesmo com `--oss-only`. A Fase 1 não
    passa `--dataflow-traces` e reexecutar 25 casos do cache devolveu 25
    resultados idênticos — mas "ce" deixou de ser um estado único na máquina, e
    uma identidade que não registra isso volta a ser a suposição que este tipo
    já existe para eliminar.
    """

    edicao: str
    versao: str
    entre_arquivos: bool
    binario_pro_disponivel: bool = False

    def como_dict(self) -> dict:
        """Forma serializável, para o cache e para o manifesto da rodada."""
        return {
            "edicao": self.edicao,
            "versao": self.versao,
            "entre_arquivos": self.entre_arquivos,
            "binario_pro_disponivel": self.binario_pro_disponivel,
        }


# A identidade é obtida uma vez por processo: descobri-la custa uma invocação do
# Semgrep (~1 s), e a Fase 1 percorre centenas de casos por rodada.
_MOTOR_CACHE = {}


def _versao_semgrep() -> str:
    try:
        r = subprocess.run([SEMGREP, "--version"], capture_output=True,
                           text=True, timeout=60)
        return (r.stdout.strip().splitlines() or ["desconhecida"])[-1]
    except (OSError, subprocess.SubprocessError):
        return "desconhecida"


def _binario_pro_presente() -> bool:
    """O binário proprietário está instalado ao lado do Semgrep?"""
    try:
        import semgrep
        raiz = os.path.dirname(os.path.abspath(semgrep.__file__))
    except Exception:
        return False
    binarios = os.path.join(raiz, "bin")
    if not os.path.isdir(binarios):
        return False
    return any(nome.startswith(_BIN_PRO) for nome in os.listdir(binarios))


def motor_corrente(entre_arquivos: bool = False) -> MotorSimbolico:
    """Identidade do motor desta execução, memoizada por processo."""
    if "base" not in _MOTOR_CACHE:
        _MOTOR_CACHE["base"] = (_versao_semgrep(), _binario_pro_presente())
    versao, tem_pro = _MOTOR_CACHE["base"]
    return MotorSimbolico(
        edicao=EDICAO_PRO if entre_arquivos else EDICAO_CE,
        versao=versao,
        entre_arquivos=bool(entre_arquivos),
        binario_pro_disponivel=tem_pro,
    )


def motor_de_payload(payload) -> MotorSimbolico:
    """Lê a identidade gravada numa entrada, tratando ausência como CE.

    Entrada sem identidade é anterior a esta mudança: é factualmente verdade
    que não havia outro motor quando ela foi gravada. Tratá-la como
    "desconhecida" invalidaria o cache inteiro e forçaria uma reexecução
    completa da Fase 1 sobre a população, sem nenhum ganho de correção.

    Deliberadamente o OPOSTO da regra de pareamento, onde entrada sem versão é
    recomputada: lá, a ausência significava que o CONTEÚDO podia estar errado
    sob a regra nova; aqui significa apenas que o campo não existia, e o
    conteúdo continua correto para o motor CE.
    """
    dados = (payload or {}).get("motor") or {}
    return MotorSimbolico(
        edicao=dados.get("edicao", EDICAO_CE),
        versao=dados.get("versao", ""),
        entre_arquivos=bool(dados.get("entre_arquivos", False)),
        binario_pro_disponivel=bool(dados.get("binario_pro_disponivel", False)),
    )


def registro_de_viabilidade(diretorio=None):
    """Portão MAIS RECENTE, se e somente se ele classificou `viavel`.

    Decide pelo mais recente legível e para ali — não procura um `viavel` mais
    fundo na pilha. A diferença importa: varrer até achar um aprovado faria uma
    verificação nova dizendo `indisponivel` ser pulada em favor de uma antiga
    dizendo `viavel`, e o modo seria autorizado por evidência que a própria
    máquina acabou de contradizer. Registro ilegível é tratado como ausente,
    porque não afirma nada — é o único caso em que seguir adiante é honesto.
    """
    import glob

    from .config import DATA_DIR

    alvo = diretorio or DATA_DIR
    for caminho in sorted(glob.glob(os.path.join(alvo, VIABILIDADE_GLOB)),
                          reverse=True):
        try:
            with open(caminho, encoding="utf-8") as f:
                dados = json.load(f)
        except (OSError, json.JSONDecodeError):
            continue
        if dados.get("classificacao") == CLASSIFICACAO_VIAVEL:
            return caminho, dados
        return None       # o mais recente reprovou: não há o que procurar atrás
    return None


def exigir_viabilidade(diretorio=None):
    """Aborta se o modo entre-arquivos for pedido sem verificação aprovada."""
    registro = registro_de_viabilidade(diretorio)
    if registro is None:
        raise ModoIndisponivelError(
            "modo entre-arquivos pedido sem registro de viabilidade aprovada. "
            f"Rode `python scripts/verificar_pro.py` até obter classificação "
            f"'{CLASSIFICACAO_VIAVEL}' — sem isso a rodada produziria números "
            "do motor CE rotulados como Pro.")
    return registro


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


def montar_comando(caminho_arquivo: str, entre_arquivos: bool = False,
                   configs=None) -> list:
    """Linha de comando do Semgrep para um alvo.

    Com configuração unitária e `entre_arquivos=False` — o padrão — devolve
    EXATAMENTE a mesma lista de antes destas mudanças. É a garantia de que ligar
    as capacidades não mexeu na invocação de quem não as pediu: as Rodadas 1–3
    mediram esta linha, e qualquer argumento a mais aqui as tornaria
    irreproduzíveis.

    Mais de um ruleset vira `--config` repetido, na ORDEM CONFIGURADA. A ordem
    não altera a união dos achados — por isso não entra na identidade do
    conjunto —, mas a linha de comando reproduz o que foi pedido, e não uma
    reordenação nossa, para que copiá-la do log e rodá-la à mão dê o mesmo
    resultado.
    """
    alvo = SEMGREP_CONFIGS if configs is None else tuple(configs)
    if not alvo:
        raise ConfiguracaoVaziaError(
            "nenhum ruleset configurado: SEMGREP_CONFIG está vazia. Uma "
            "execução sem regras produziria zero alertas e faria toda a "
            "população parecer não detectada.")
    cmd = [SEMGREP]
    for config in alvo:
        cmd += ["--config", config]
    cmd += ["--sarif", "--quiet"]
    if entre_arquivos:
        cmd.append("--pro")
    cmd.append(caminho_arquivo)
    return cmd


def _cwes_da_regra(tags) -> tuple:
    """Números de CWE que a regra declara, ordenados — a chave semântica dela."""
    return tuple(sorted({n for n in (_numero_cwe(t) for t in tags)
                         if n is not None}))


def _posicao(result: dict) -> tuple:
    loc = ((result.get("locations") or [{}])[0]).get("physicalLocation", {})
    regiao = loc.get("region", {})
    arquivo = (loc.get("artifactLocation") or {}).get("uri", "")
    return (str(arquivo), regiao.get("startLine", 1), regiao.get("startColumn", 1))


def deduplicar(results, regras) -> list:
    """Achados equivalentes de rulesets diferentes contam como um só.

    Equivalente é `(arquivo, posição, CWE)` — dois rulesets podem cobrir a mesma
    fraqueza no mesmo ponto do código com regras de nomes diferentes. Sem
    política, o número de alertas por arquivo passaria a depender de quantos
    rulesets cobrem aquele padrão, e é esse número que alimenta o diagnóstico de
    cobertura simbólica (`regras_nao_casadas`).

    A CWE entra na chave: mesma posição com CWEs diferentes NÃO é duplicata,
    porque descreve fraquezas distintas. Regra sem CWE alguma tem chave própria
    (tupla vazia) e só deduplica contra outra igualmente sem CWE na mesma
    posição.

    Determinística: a ordem é `(arquivo, linha, coluna, check_id)` e o
    sobrevivente é sempre o primeiro dela — não o primeiro da saída do Semgrep,
    que é estável na prática mas é detalhe interno da ferramenta.

    Não rebaixa status: o sobrevivente de um grupo declara as mesmas CWEs que os
    descartados, então se algum do grupo casava com o gabarito, ele casa.
    """
    ordenados = sorted(results, key=lambda r: (*_posicao(r), _check_id(r)))
    preservados, vistos = [], set()
    for r in ordenados:
        chave = (*_posicao(r), _cwes_da_regra(regras.get(r.get("ruleId"), [])))
        if chave in vistos:
            continue
        vistos.add(chave)
        preservados.append(r)
    return preservados


def executar_semgrep(caminho_arquivo: str, cwe: str,
                     entre_arquivos: bool = False,
                     configs=None) -> ResultadoFase1:
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
            montar_comando(caminho_arquivo, entre_arquivos, configs),
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

    # A deduplicação só entra com configuração COMPOSTA. Com um ruleset só não
    # há de onde vir achado equivalente de outra procedência, e aplicá-la mesmo
    # assim poderia encolher `regras_nao_casadas` numa rodada unitária —
    # alterando, sem ganho algum, a série que as Rodadas 1–3 mediram.
    if len(SEMGREP_CONFIGS if configs is None else tuple(configs)) > 1:
        results = deduplicar(results, regras)

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
