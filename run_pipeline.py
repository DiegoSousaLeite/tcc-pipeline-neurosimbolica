"""
run_pipeline.py — orquestrador da pipeline neuro-simbólica (Semgrep + LLM).

Trilhas de entrada (todas passam pelo MESMO fluxo — o LLM é filtro puro do
Semgrep)
  FP          (dataset, ground_truth=false_positive) → gabarito=seguro
  TP_ouro     (tp_pairs.json)      → par vuln/corrigido, gabarito vulneravel/seguro
  TP_prata    (tp_pairs_osv.json)  → idem, da OSV harvest
  TP_dataset  (dataset, ground_truth=true_positive)  → gabarito=vulneravel
  TP_alcancavel (tp_pairs_osv_alcancavel.json) → idem, da OSV harvest já
                filtrada pelas CWEs que o ruleset alcança. Trilha própria e não
                sobrescrita da TP_prata: os pares inalcançáveis dela são a
                evidência do achado dos 70,1%, e separar as duas é o que permite
                dizer, depois da rodada, se o ganho veio da colheita filtrada.

  Em todas, o LLM só é consultado se o Semgrep detectar (DETECTADO). As vulns
  reais que o Semgrep não reproduz viram Semgrep FN (ponto cego simbólico).

Fases
  1. Semgrep      — resolve o arquivo-alvo (src/fonte.py: cache → clone local →
                    rede) e localiza o alerta exato nele; não clona repositórios
  2. Middleware   — extrai a função ao redor do alerta (hidratação)
  3/4. LLM        — monta o prompt (prompts/) e coleta o veredito (src/provedores/)
  5. Auditoria    — grava CSV + matrizes de cobertura/acerto

Matriz experimental (Parte 2)
  A mesma população roda sob N braços `(modelo, tipo de prompt)`. As Fases 1 e 2
  rodam UMA vez por caso e o resultado vai para o cache simbólico, de modo que
  todos os braços vejam contexto byte-a-byte idêntico e só a chamada de LLM se
  repita. Cada braço grava seu próprio CSV em `results/<run_id>/`.

USO
  python run_pipeline.py --amostra 10            # subconjunto rápido
  python run_pipeline.py --tudo                  # 948 casos, braço padrão
  python run_pipeline.py --tudo --matriz         # matriz 2x2 completa
  python run_pipeline.py --tp-only --sem-llm     # só cobertura simbólica
  python run_pipeline.py --trilha TP_dataset --dry-run
"""
import argparse
import collections
import csv
import glob
import hashlib
import json
import logging
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import NamedTuple

from src import regras_locais
from src.cache_simbolico import CacheSimbolico
from src.catalogo import catalogo_padrao
from src.config import (
    CACHE_DIR,
    DATASET_PATH,
    MODELO_LLM,
    PROMPT_TYPE,
    RESULTS_DIR,
)
from src.fase1_semgrep import (
    MOTIVO_NA,
    PROCEDENCIA_PROPRIA,
    SEMGREP,
    ModoIndisponivelError,
    SemgrepError,
    SemgrepFileNotFoundError,
    SemgrepTimeoutError,
    executar_semgrep,
    exigir_viabilidade,
    identidade_conjunto,
    motor_corrente,
    rulesets_configurados,
)
from src.fase2_middleware import extrair_e_hidratar_contexto
from src.fase5_auditoria import CATEGORIAS_ERRO, inicializar_relatorio, registrar_resultado
from src.fases3_4_llm import avaliar
from src.fonte import (
    ArquivoInexistente,
    FetchError,
    caminho_cache,
    estatisticas_cache,
    obter_arquivo,
)
from src.prompts import BASELINE, ESPECIALISTA, TIPOS, versao_prompt
from src.provedores import (
    MODELO_GEMINI_PADRAO,
    MODELO_OLLAMA_PADRAO,
    MODELO_OPENAI_PADRAO,
    criar_provedor,
    familia_do_modelo,
)
from src.provedores.ollama import OllamaIndisponivel
from src.provedores.precos import tabela_para_manifesto

log = logging.getLogger("pipeline")

BASE = os.path.dirname(os.path.abspath(__file__))
TP_PAIRS_OURO = os.path.join(BASE, "tp_pairs.json")
TP_PAIRS_PRATA = os.path.join(BASE, "tp_pairs_osv.json")
# Pool da colheita filtrada por alcançabilidade: saída de
# `scripts/tp_reconstruct.py --input data/tp_fixes_osv_alcancavel.json`.
# Arquivo próprio, e não sobrescrita do pool da TP_prata: sobrescrever apagaria
# os pares inalcançáveis que sustentam o achado dos 70,1%, e impediria saber
# depois se o ganho de amostra veio da colheita nova ou do pool antigo.
TP_PAIRS_ALCANCAVEL = os.path.join(BASE, "tp_pairs_osv_alcancavel.json")
# CSVs da Parte 1, arquivados. Continuam sendo lidos pelo checkpoint — só não
# ficam mais soltos na raiz nem são misturados aos resultados da Parte 2.
LEGADO_PARTE1 = os.path.join(BASE, "legacy", "resultados_parte1")


def configurar_log(verboso: bool = False):
    """Console equivalente ao `print` de antes: só a mensagem, sem prefixo.

    O nível DEBUG expõe as invocações reais do Semgrep — é assim que se verifica
    que o cache simbólico está de fato evitando reexecuções.
    """
    logging.basicConfig(
        level=logging.DEBUG if verboso else logging.INFO,
        format="%(message)s",
        stream=sys.stdout,
        force=True,
    )


# ---------------------------------------------------------------------------
# Construção da lista de casos
# ---------------------------------------------------------------------------

@dataclass
class Caso:
    """Uma amostra de avaliação: um arquivo, num commit, sob uma CWE.

    Substitui o dict solto que circulava entre as fases. `num_locations` guarda
    quantas locations a entrada de origem tinha ANTES de qualquer filtro (.go,
    _test.go), para permitir análise de sensibilidade post-hoc sem reexecutar o
    experimento; vale 1 para casos que não vêm de entradas agregadas.
    """

    id: str
    origem: str                 # FP | TP_ouro | TP_prata | TP_dataset |
                                # TP_alcancavel
    repo_name: str
    repo_dir: str
    repo_url: str
    commit: str
    arquivo: str
    cwe: str
    gabarito: str               # vulneravel | seguro
    cwe_name: str = ""
    description: str = ""
    num_locations: int = 1

    # Compatibilidade com o acesso por chave usado antes da dataclass
    # (scripts/ e código de análise antigos indexam o caso como dict).
    def __getitem__(self, chave: str):
        return getattr(self, chave)


def _cwe_lookup(dataset):
    """Mapa cwe_id → {name, description} a partir do dataset."""
    lookup = {}
    for entry in dataset:
        cwe = entry["metadata"]["cwe_id"]
        if cwe not in lookup:
            lookup[cwe] = {
                "name": entry["metadata"].get("cwe_name", ""),
                "description": entry["to_analyzer"].get("description", ""),
            }
    return lookup


# O dataset é de alertas Go, mas as locations agregadas incluem arquivos de
# outras linguagens do mesmo commit (relatórios .html do Snyk, front-end .tsx/
# .js/.vue). O CWE do gabarito é sempre de um achado Go, então esses casos só
# produziriam NAO_DETECTADO em massa e sujariam a matriz de cobertura.
EXTENSAO_ALVO = ".go"

# Arquivos de teste entram nas locations das entradas true_positive porque o
# commit de fix costuma alterar o teste junto com o código. Eles não são a
# vulnerabilidade, e mantê-los inflaria artificialmente o denominador da
# cobertura simbólica. `scripts/tp_reconstruct.py` já aplica o mesmo corte na
# trilha ouro.
SUFIXO_TESTE = "_test.go"


def construir_casos_fp(dataset, todas_locations=True, so_go=True):
    """Expande cada alerta do dataset em casos.

    O dataset agrega por `cwe_per_commit`: cada entrada reúne TODOS os achados
    daquela CWE naquele commit, e `num_findings == len(locations)` em 259 dos
    261 alertas. Ou seja, cada location é um achado independente e legitimamente
    rotulado — não é uma vulnerabilidade atravessando arquivos. Usar só
    `locations[0]` descartava 610 amostras válidas (871 -> 261).

    O ID da primeira location continua sendo o `finding_id` puro, para que o
    checkpoint reaproveite os CSVs já gerados; as demais recebem sufixo `#N`.
    """
    casos = []
    for alerta in dataset:
        if alerta["ground_truth"] != "false_positive":
            continue
        # O índice do ID vem da posição ORIGINAL na lista de locations, antes de
        # qualquer filtro: assim um filtro (ex.: só .go) nunca renumera os casos
        # e os CSVs antigos continuam apontando para o mesmo arquivo.
        todas = alerta["to_analyzer"].get("locations", [])
        locais = list(enumerate(todas))
        if so_go:
            locais = [(i, loc) for i, loc in locais
                      if loc["file"].lower().endswith(EXTENSAO_ALVO)]
        if not locais:
            continue
        if not todas_locations:
            locais = locais[:1]
        for i, local in locais:
            casos.append(Caso(
                id=alerta["finding_id"] if i == 0
                   else f"{alerta['finding_id']}#{i}",
                origem="FP",
                repo_name=alerta["repo_name"],
                repo_dir=alerta["repo_name"].split("/")[-1],
                repo_url=alerta["repo_url"],
                commit=alerta["commit_hash"],
                arquivo=local["file"],
                cwe=alerta["metadata"]["cwe_id"],
                cwe_name=alerta["metadata"].get("cwe_name", ""),
                description=alerta["to_analyzer"].get("description", ""),
                gabarito="seguro",
                num_locations=len(todas),
            ))
    return casos


def construir_casos_tp_dataset(dataset, todas_locations=True, so_go=True):
    """Função espelho de `construir_casos_fp` para as entradas `true_positive`.

    Estas 36 entradas nunca foram carregadas pela pipeline: `construir_casos_fp`
    descarta tudo que não é `false_positive`. Elas não são redundantes com as
    trilhas ouro/prata — a trilha ouro analisa o `parent_commit` do fix com um
    arquivo por par, enquanto aqui vale o `commit_hash` em que o SastBench de
    fato escaneou, com todas as suas locations.

    Não é uma generalização de `construir_casos_fp` por decisão de projeto (D1
    do design): as duas divergem no filtro `_test.go`, no valor de `gabarito` e
    no prefixo do ID, e unificá-las produziria uma função com três flags cujo
    caminho FP gera números já publicados.

    ATENÇÃO ao rótulo (D2): `metadata.source` é `cvefixes` aqui, não `semgrep`.
    O rótulo afirma que o *commit* corrigiu uma CVE, não que *cada arquivo* é a
    vulnerabilidade. É limitação declarada da amostra, documentada no README.
    """
    casos = []
    vistos = set()
    for alerta in dataset:
        if alerta["ground_truth"] != "true_positive":
            continue
        todas = alerta["to_analyzer"].get("locations", [])
        locais = list(enumerate(todas))
        if so_go:
            # Filtro de extensão e filtro de teste no MESMO ponto: o índice do
            # ID continua vindo da posição original, então nenhum caso é
            # renumerado quando o critério muda.
            locais = [(i, loc) for i, loc in locais
                      if loc["file"].lower().endswith(EXTENSAO_ALVO)
                      and not loc["file"].lower().endswith(SUFIXO_TESTE)]
        if not locais:
            continue
        if not todas_locations:
            locais = locais[:1]
        for i, local in locais:
            # Aqui as locations são por FUNÇÃO alterada no commit de fix, então
            # o mesmo arquivo reaparece várias vezes na mesma entrada — 108
            # locations .go para 66 alvos distintos. A pipeline analisa o
            # ARQUIVO inteiro (o Semgrep roda sobre ele e a Fase 2 hidrata a
            # função do alerta), logo cada repetição produziria exatamente o
            # mesmo veredito: duplicaria a evidência na matriz de confusão e
            # gastaria uma chamada de LLM por braço à toa. Fica a primeira
            # ocorrência, com o índice original no ID.
            # A trilha FP não precisa disto: lá as 791 locations .go já são
            # alvos distintos (source=semgrep, um achado por arquivo).
            chave = (alerta["repo_name"], alerta["commit_hash"],
                     local["file"], alerta["metadata"]["cwe_id"])
            if chave in vistos:
                continue
            vistos.add(chave)
            casos.append(Caso(
                id=f"TPD:{alerta['finding_id']}" if i == 0
                   else f"TPD:{alerta['finding_id']}#{i}",
                origem="TP_dataset",
                repo_name=alerta["repo_name"],
                repo_dir=alerta["repo_name"].split("/")[-1],
                repo_url=alerta["repo_url"],
                commit=alerta["commit_hash"],
                arquivo=local["file"],
                cwe=alerta["metadata"]["cwe_id"],
                cwe_name=alerta["metadata"].get("cwe_name", ""),
                description=alerta["to_analyzer"].get("description", ""),
                gabarito="vulneravel",
                num_locations=len(todas),
            ))
    return casos


TRILHAS = ("FP", "TP_ouro", "TP_prata", "TP_dataset", "TP_alcancavel")


def contar_por_trilha(casos):
    """Contagem por trilha, na ordem canônica e sem omitir trilha vazia.

    Vai para o log inicial e para o manifesto da rodada: é o número que permite
    conferir depois qual população produziu cada resultado.
    """
    contagem = {t: 0 for t in TRILHAS}
    for c in casos:
        contagem[c.origem] = contagem.get(c.origem, 0) + 1
    return contagem


def priorizar_locais(casos):
    """Reordena pondo primeiro o que já está no cache (roda sem rede).

    Antes isto era um *filtro* por repos clonados: com `repos/` vazio, o
    `--amostra` devolvia zero casos. Priorizar em vez de filtrar mantém a
    amostra sempre utilizável.
    """
    def ja_local(c):
        return os.path.exists(caminho_cache(c["repo_name"], c["commit"],
                                            c["arquivo"]))
    return sorted(casos, key=lambda c: not ja_local(c))


def construir_casos_tp(tp_pairs_file, origem_label, cwe_meta, prefixo_id=""):
    """Constrói casos TP no MESMO formato dos casos FP: cada par vira duas
    amostras (o commit vulnerável e o commit corrigido), que passam pela
    Fase 1 (Semgrep) como qualquer outra amostra. Não há bypass — o LLM só
    roda se o Semgrep detectar (filtro puro). As amostras vulneráveis que o
    Semgrep não reproduz viram Semgrep FN (ponto cego) na matriz de cobertura.

    `prefixo_id` separa o espaço de identificadores de uma trilha das demais.
    Fica vazio para `TP_ouro` e `TP_prata`, cujos IDs já estão gravados nos CSVs
    e no checkpoint das rodadas anteriores; pools colhidos depois usam prefixo
    próprio, porque a colheita pode reencontrar um repo/CWE/função já presente
    num pool antigo e o ID colidido faria dois casos distintos serem tratados
    como o mesmo pela tripla de checkpoint.

    Nos pools com prefixo o ID leva ainda um discriminador do **arquivo**, sem o
    qual a separação entre trilhas não bastaria: dentro de um mesmo pool, o
    mesmo nome de método aparece em vários arquivos do pacote e um único fix os
    altera juntos — `Decode` em `commit.go`, `tag.go` e `tree.go` do `go-git`
    davam três casos com um ID só. O discriminador sai do caminho do arquivo, e
    não da posição no pool, para que acrescentar um par nunca mude o ID de um
    par já existente (`identificador-de-caso-unico`, D1 e D2).

    Os pools sem prefixo ficam de fora da mudança de propósito: alterar o ID
    deles invalidaria a retomada das rodadas que já os gravaram (D3).
    """
    casos = []
    if not os.path.exists(tp_pairs_file):
        return casos
    with open(tp_pairs_file, encoding="utf-8") as f:
        pairs = json.load(f)
    for par in pairs:
        repo = par["repo"]
        repo_dir = repo.split("/")[-1]
        cwe = par["cwe_id"]
        arquivo = par.get("arquivo")
        funcao = (par.get("funcao") or "func").replace(" ", "_")
        meta = cwe_meta.get(cwe, {"name": "", "description": ""})
        base_id = f"{prefixo_id}{repo_dir}:{cwe}:{funcao}"
        if prefixo_id:
            discriminador = hashlib.sha256(
                (arquivo or "").encode("utf-8")).hexdigest()[:8]
            base_id = f"{base_id}:{discriminador}"
        for versao, commit, gabarito in [
            ("vuln", par.get("parent_commit"), "vulneravel"),
            ("fix", par.get("fix_commit"), "seguro"),
        ]:
            if not commit or not arquivo:
                continue
            casos.append(Caso(
                id=f"{base_id}:{versao}",
                origem=origem_label,
                repo_name=repo,
                repo_dir=repo_dir,
                repo_url=f"https://github.com/{repo}",
                commit=commit,
                arquivo=arquivo,
                cwe=cwe,
                cwe_name=meta["name"],
                description=meta["description"],
                gabarito=gabarito,
                # Um par TP aponta um arquivo por commit: a entrada de origem
                # não é agregada, então num_locations vale 1 por construção.
                num_locations=1,
            ))
    return casos


class IdentificadorDuplicadoError(Exception):
    """Dois casos distintos receberam o mesmo `ID_Caso`.

    É erro, e não aviso, porque o dano é silencioso: o checkpoint por tripla
    `(ID_Caso, Modelo_LLM, Tipo_Prompt)` trata o segundo caso como já gravado e
    `src/metricas.py` deduplica pela primeira ocorrência, de modo que o caso
    perdido não deixa rastro no CSV. É o mesmo modo de falha do pareamento por
    fallback e do ruleset vazio — saída plausível e errada.
    """


def verificar_ids_unicos(casos):
    """Aborta se a população carrega `ID_Caso` repetido.

    Roda uma vez por execução, antes de qualquer varredura ou chamada de LLM: o
    custo é desprezível perto de uma rodada de horas que terminaria com casos a
    menos sem ninguém perceber. A mensagem nomeia os IDs repetidos e as trilhas
    envolvidas, porque a decisão de o que fazer depende de qual pool colidiu.
    """
    contagem = collections.Counter(c.id for c in casos)
    repetidos = sorted(i for i, n in contagem.items() if n > 1)
    if not repetidos:
        return None

    trilhas = collections.defaultdict(set)
    for c in casos:
        if c.id in contagem and contagem[c.id] > 1:
            trilhas[c.id].add(c.origem)
    amostra = ", ".join(f"{i} ({'/'.join(sorted(trilhas[i]))})"
                        for i in repetidos[:5])
    raise IdentificadorDuplicadoError(
        f"{len(repetidos)} ID_Caso repetido(s) na população, "
        f"{sum(contagem[i] for i in repetidos)} casos envolvidos: {amostra}"
        + (" ..." if len(repetidos) > 5 else ""))


# ---------------------------------------------------------------------------
# Checkpoint
# ---------------------------------------------------------------------------

# Braço ao qual pertencem as linhas dos CSVs da Parte 1, que não têm as colunas
# novas. Todas foram geradas com este par (conferido nos CSVs existentes); o
# valor só é usado quando as colunas estão ausentes ou vazias.
BRACO_PARTE1 = (MODELO_GEMINI_PADRAO, ESPECIALISTA)


def _csvs_conhecidos(dir_rodada=None, incluir_anteriores=False):
    """CSVs que o checkpoint deve considerar.

    Por padrão, SÓ a rodada corrente. É o que faz uma rodada nova começar do
    zero e uma rodada interrompida retomar de onde parou.

    `incluir_anteriores` acrescenta as rodadas passadas e os CSVs da Parte 1
    (`legacy/resultados_parte1/`; o padrão da raiz fica por compatibilidade com
    cópias antigas). Fica DESLIGADO por padrão de propósito: as linhas da Parte 1
    pertencem ao braço `(gemini-2.5-flash-lite, especialista)`, e deixá-las
    satisfazer o checkpoint faria esse braço vir com menos casos que os outros
    três — quebrando a premissa de que os quatro cobrem exatamente a mesma
    população, que é o que torna o McNemar pareado válido. Some-se a isso que a
    própria proposta declara os resultados da Parte 1 não comparáveis: a
    população e o cabeçalho do CSV mudaram.

    Nenhum arquivo antigo é modificado ou removido — só lido.
    """
    padroes = []
    if dir_rodada:
        padroes.append(os.path.join(dir_rodada, "*.csv"))
    if incluir_anteriores:
        padroes += [
            os.path.join(RESULTS_DIR, "*", "*.csv"),
            os.path.join(BASE, "resultados_tcc*.csv"),
            os.path.join(LEGADO_PARTE1, "**", "*.csv"),
        ]
    vistos, arquivos = set(), []
    for p in padroes:
        for a in glob.glob(p, recursive=True):
            real = os.path.normcase(os.path.abspath(a))
            if real not in vistos:
                vistos.add(real)
                arquivos.append(a)
    return arquivos


def carregar_processados(arquivos=None, *args_csvs):
    """Set de triplas `(ID_Caso, Modelo_LLM, Tipo_Prompt)` já concluídas.

    A chave é composta porque a mesma população roda em quatro braços: indexar
    só por `ID_Caso` faria o segundo braço achar tudo pronto e sair vazio —
    falha silenciosa, o pior modo de falha possível aqui.

    Só conta como processado quem terminou em estado VÁLIDO:

      - `NAO_DETECTADO`: o caso está resolvido, o LLM nem devia ser consultado;
      - `DETECTADO` **com veredito em {VP, FP}**: o braço de fato decidiu.

    A exigência do veredito não é redundante. Uma medição `--sem-llm` grava
    `DETECTADO` com veredito `N/A` — o Semgrep disparou, mas ninguém triou.
    Sem esta checagem, medir a cobertura simbólica de um conjunto impediria
    para sempre de rodar o LLM sobre ele. Casos em categoria de erro
    (API_ERROR, FETCH_FAIL, etc.) também não são checkpointados.
    """
    processados = set()
    for arq in (arquivos if arquivos is not None else _csvs_conhecidos(*args_csvs)):
        try:
            with open(arq, encoding="utf-8") as f:
                for row in csv.DictReader(f):
                    caso_id = row.get("ID_Caso")
                    if not caso_id:
                        continue
                    status = row.get("Status_Semgrep")
                    if status in CATEGORIAS_ERRO:
                        continue
                    if status == "DETECTADO" and row.get("Veredito_LLM") not in ("VP", "FP"):
                        continue
                    modelo = row.get("Modelo_LLM") or BRACO_PARTE1[0]
                    prompt = row.get("Tipo_Prompt") or BRACO_PARTE1[1]
                    processados.add((caso_id, modelo, prompt))
        except OSError:
            log.debug("CSV ilegível, ignorado no checkpoint: %s", arq)
    return processados


def definir_nome_relatorio_unico(caminho_padrao):
    if not os.path.exists(caminho_padrao):
        return caminho_padrao
    nome_base, ext = os.path.splitext(caminho_padrao)
    i = 1
    while True:
        c = f"{nome_base}_{i}{ext}"
        if not os.path.exists(c):
            return c
        i += 1


# ---------------------------------------------------------------------------
# Identidade da rodada
# ---------------------------------------------------------------------------

# Caracteres que o Windows recusa em nome de arquivo. As tags do Ollama trazem
# dois-pontos (`qwen2.5-coder:7b`), e o rótulo do braço vira nome de CSV: sem o
# saneamento a rodada morre ao abrir o arquivo, antes do primeiro caso.
CARACTERES_RESERVADOS = ':*?"<>|/\\'


def sanear_rotulo(texto: str) -> str:
    """Troca os caracteres reservados por `-`, deixando o resto intacto.

    Rótulo já válido sai IDÊNTICO: `gemini-2.5-flash-lite__especialista`
    continua com esse nome, o que preserva a retomada de rodadas em andamento e
    a leitura dos CSVs já gravados.
    """
    return "".join("-" if c in CARACTERES_RESERVADOS else c for c in texto)


@dataclass(frozen=True)
class Braco:
    """Um ponto da matriz experimental: um modelo com um tipo de prompt.

    `sufixo` só é preenchido quando dois modelos distintos saneariam para o
    mesmo nome de arquivo (ver `definir_bracos`); nome de modelo é identidade e
    continua inteiro na coluna `Modelo_LLM` e no manifesto — o rótulo é só nome
    de arquivo.
    """

    modelo: str
    prompt: str
    sufixo: str = ""

    @property
    def rotulo(self) -> str:
        base = sanear_rotulo(f"{self.modelo}__{self.prompt}")
        return f"{base}-{self.sufixo}" if self.sufixo else base

    def __str__(self) -> str:
        return f"({self.modelo}, {self.prompt})"


def commit_atual() -> str:
    """SHA curto do repositório, ou 'desconhecido' fora de um clone git."""
    try:
        r = subprocess.run(["git", "-C", BASE, "rev-parse", "--short", "HEAD"],
                           capture_output=True, text=True, timeout=10)
        return r.stdout.strip() or "desconhecido"
    except (OSError, subprocess.SubprocessError):
        return "desconhecido"


def versao_semgrep() -> str:
    try:
        r = subprocess.run([SEMGREP, "--version"], capture_output=True,
                           text=True, timeout=60)
        return r.stdout.strip() or "desconhecida"
    except (OSError, subprocess.SubprocessError):
        return "desconhecida"


def novo_run_id() -> str:
    """`<timestamp UTC>-<commit curto>`: ordenável e rastreável ao código."""
    agora = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{agora}-{commit_atual()}"


def regras_locais_do_manifesto():
    """As regras de `regras/go/`, se e somente se o ruleset local está em uso.

    Condicionado à configuração de propósito: registrar regras que não entraram
    na invocação faria o manifesto afirmar que elas produziram os alertas da
    rodada, e é justamente esse tipo de afirmação que ele existe para sustentar.
    """
    if not any(p["procedencia"] == PROCEDENCIA_PROPRIA
               for p in rulesets_configurados()):
        return {}
    return regras_locais.para_manifesto(commit=commit_atual())


def gravar_manifesto(dir_rodada, run_id, bracos, por_trilha, total_casos,
                     inicio, fim, catalogo, sem_llm, cache_ativo, argv,
                     sondagens=None, entre_arquivos=False):
    """Registra a configuração completa da rodada.

    É o que permite, meses depois, dizer de qual código, ruleset, catálogo e
    tabela de preços saiu cada número do capítulo de resultados.
    """
    manifesto = {
        "run_id": run_id,
        "commit": commit_atual(),
        "comando": argv,
        "inicio_utc": inicio.isoformat(),
        "fim_utc": fim.isoformat(),
        "duracao_s": round((fim - inicio).total_seconds(), 2),
        # A identidade do MOTOR entra ao lado da do modelo local, e pelo mesmo
        # motivo: permitir dizer, meses depois, qual motor produziu cada número.
        # `versao` e `ruleset` continuam onde estavam para não quebrar quem lê
        # manifestos das rodadas anteriores (`scripts/analise_rodada.py`);
        # `ruleset` passa a ser a identidade do CONJUNTO, que para a
        # configuração unitária é o nome do ruleset — exatamente o valor de
        # antes.
        #
        # `rulesets` acrescenta a procedência de cada um. A distinção é
        # metodológica: ruleset publicado no registry não foi escrito olhando
        # para a nossa população; ruleset que sai de arquivo nosso pode ter
        # sido, e o texto da monografia trata os dois casos de forma diferente.
        "semgrep": {
            "versao": versao_semgrep(),
            "ruleset": identidade_conjunto(),
            "rulesets": rulesets_configurados(),
            "motor": motor_corrente(entre_arquivos).como_dict(),
            # Regra nossa não basta constar do conjunto: ela muda por commit, e
            # o texto precisa poder dizer quais regras, sob qual protocolo,
            # produziram cada número. Vazio quando `regras/go/` não está
            # configurado — que é o padrão.
            "regras_locais": regras_locais_do_manifesto(),
        },
        "catalogo_cwe": {
            "caminho": os.path.relpath(catalogo.caminho, BASE),
            "sha256": catalogo.sha256,
            "cwes_especificas": catalogo.cwes_especificas,
        },
        "prompts": {tipo: versao_prompt(tipo) for tipo in TIPOS},
        "bracos": [{"modelo": b.modelo, "prompt": b.prompt,
                    "csv": f"{b.rotulo}.csv"} for b in bracos],
        "precos": tabela_para_manifesto(sorted({b.modelo for b in bracos}),
                                        modelos_locais=modelos_locais(bracos)),
        # Identidade dos pesos que produziram os vereditos do braço local:
        # versão do servidor, digest, quantização, janela efetiva, semente e se
        # a inferência coube na GPU. A tag sozinha não identifica nada — é
        # ponteiro mutável no registry.
        "modelos_locais": sondagens or {},
        "populacao": {
            "total": total_casos,
            "por_trilha": por_trilha,
        },
        "modo": {
            "sem_llm": sem_llm,
            "cache_simbolico_ativo": cache_ativo,
        },
    }
    destino = os.path.join(dir_rodada, "manifesto.json")
    with open(destino, "w", encoding="utf-8", newline="\n") as f:
        json.dump(manifesto, f, ensure_ascii=False, indent=2)
        f.write("\n")
    return destino


# ---------------------------------------------------------------------------
# Pipeline principal
# ---------------------------------------------------------------------------

class ResultadoSimbolico(NamedTuple):
    """Resultado das Fases 1 e 2 de um caso.

    Os três primeiros campos são a tripla histórica `(status, alerta, contexto)`;
    o motivo e as regras foram acrescentados NO FIM de propósito, para que quem
    já lê a tupla por posição continue lendo a mesma coisa.
    """

    status: str
    alerta: dict | None
    contexto: str
    motivo: str = MOTIVO_NA
    regras_nao_casadas: list = ()


def resolver_simbolico(caso, cache_simbolico=None):
    """Fases 1 e 2 de um caso, servidas do cache simbólico quando possível.

    Devolve `ResultadoSimbolico` com status em
    `DETECTADO | NAO_DETECTADO | HIDRATACAO_FALHOU`. Exceções de esteira sobem
    para quem chamou categorizá-las — nada de resultado parcial vai para o
    cache, para que uma falha de rede não vire um `NAO_DETECTADO` permanente.
    """
    if cache_simbolico is not None:
        payload = cache_simbolico.ler(caso["repo_name"], caso["commit"],
                                      caso["arquivo"], caso["cwe"])
        if payload is not None:
            log.info("    -> Fases 1-2: reaproveitadas do cache simbólico.")
            # O diagnóstico de cobertura vem do cache junto com o status: sem
            # ele, uma rodada servida do disco só o recuperaria reexecutando o
            # Semgrep sobre a população inteira.
            return ResultadoSimbolico(
                payload["status_semgrep"], payload["alerta"],
                payload["contexto_hidratado"],
                payload.get("motivo", MOTIVO_NA),
                payload.get("regras_nao_casadas") or [])

    # FASE 1 — resolve o arquivo-alvo (cache / clone local / rede) e roda o
    # Semgrep sobre ele. Nenhum clone é feito aqui: ver src/fonte.py.
    caminho_arquivo = obter_arquivo(caso["repo_name"], caso["commit"],
                                    caso["arquivo"])
    log.info("    -> Fase 1: executando Semgrep...")
    # O modo vem do cache, e não de um parâmetro próprio: é o mesmo objeto que
    # decide qual entrada serve este caso, então as duas decisões não podem
    # divergir. Ler o motor de uma fonte e a invocação de outra reintroduziria,
    # por outro caminho, o descasamento que o terceiro eixo da chave elimina.
    entre_arquivos = bool(cache_simbolico is not None
                          and cache_simbolico.motor.entre_arquivos)
    alerta, motivo, regras = executar_semgrep(caminho_arquivo, caso["cwe"],
                                              entre_arquivos)

    if alerta is None:
        status, contexto = "NAO_DETECTADO", ""
    else:
        # FASE 2 — Hidratação (mesmo arquivo já resolvido na Fase 1)
        contexto = extrair_e_hidratar_contexto(alerta, caminho_arquivo)
        status = "DETECTADO" if contexto else "HIDRATACAO_FALHOU"

    if cache_simbolico is not None:
        # NAO_DETECTADO também é gravado: é a maioria dos casos e é onde o
        # Semgrep gasta tempo sem produzir chamada de LLM.
        cache_simbolico.gravar(caso["repo_name"], caso["commit"],
                               caso["arquivo"], caso["cwe"], status,
                               alerta=alerta, contexto_hidratado=contexto,
                               motivo=motivo, regras_nao_casadas=regras)
    return ResultadoSimbolico(status, alerta, contexto, motivo, regras)


ERRO_POR_EXCECAO = [
    (ArquivoInexistente, "SEMGREP_FILE_NOT_FOUND"),
    (FetchError, "FETCH_FAIL"),
    (SemgrepTimeoutError, "SEMGREP_TIMEOUT"),
    (SemgrepFileNotFoundError, "SEMGREP_FILE_NOT_FOUND"),
    (SemgrepError, "SEMGREP_ERROR"),
]


def _categoria_de_erro(exc) -> str:
    for tipo, categoria in ERRO_POR_EXCECAO:
        if isinstance(exc, tipo):
            return categoria
    return "ERRO_DESCONHECIDO"


def processar_caso(caso, csvs_por_braco, bracos, idx, total, processados,
                   sem_llm=False, cache_simbolico=None, provedores=None,
                   catalogo=None):
    """Processa um caso em TODOS os braços da matriz.

    As Fases 1 e 2 rodam uma vez só, por fora do laço de braços: é isso que
    garante contexto byte-a-byte idêntico entre eles (validade interna da
    comparação pareada) e que corta o custo de parede, já que o Semgrep é o
    gasto dominante e roda inclusive nos `NAO_DETECTADO`.

    O LLM continua sendo filtro puro do Semgrep: `NAO_DETECTADO` não dispara
    chamada em braço nenhum. Com `sem_llm`, nem os `DETECTADO` disparam.
    """
    caso_id = caso["id"]
    ficha = (catalogo or catalogo_padrao()).ficha(caso["cwe"], caso["cwe_name"])
    hash_catalogo = (catalogo or catalogo_padrao()).sha256

    log.info("\n[%d/%d] %s | %s | %s | %s", idx, total, caso["origem"],
             caso["repo_dir"], caso["cwe"], caso["gabarito"])

    pendentes = [b for b in bracos
                 if (caso_id, b.modelo, b.prompt) not in processados]
    if not pendentes:
        log.info("    [PULADO] Já processado em todos os braços selecionados.")
        return 0

    def _registrar(braco, status, tempo, resposta=None, erro=None, resp_llm=None,
                   motivo=MOTIVO_NA, regras=()):
        registrar_resultado(
            csvs_por_braco[braco], caso_id, caso["repo_name"], caso["cwe"],
            caso["origem"], caso["gabarito"],
            status_semgrep=status, tempo_exec=tempo,
            resposta_llm=resposta, erro_msg=erro,
            modelo=braco.modelo, tipo_prompt=braco.prompt,
            num_locations=caso["num_locations"],
            ficha_cwe=ficha.origem,
            versao_prompt=versao_prompt(braco.prompt),
            hash_catalogo=hash_catalogo,
            tokens_entrada=resp_llm.tokens_entrada if resp_llm else 0,
            tokens_saida=resp_llm.tokens_saida if resp_llm else 0,
            custo_usd=resp_llm.custo_usd if resp_llm else 0.0,
            motivo_nao_deteccao=motivo,
            regras_nao_casadas=regras,
        )

    t0 = time.time()
    try:
        simbolico = resolver_simbolico(caso, cache_simbolico)
    except Exception as e:                       # falha de esteira
        categoria = _categoria_de_erro(e)
        log.info("    [FALHA] %s: %s", categoria, str(e)[:120])
        for braco in pendentes:
            _registrar(braco, categoria, time.time() - t0, erro=str(e))
        return 0

    status_simbolico, contexto = simbolico.status, simbolico.contexto
    tempo_simbolico = time.time() - t0

    if status_simbolico == "NAO_DETECTADO":
        # O status continua um só nos dois motivos: quem compara a string
        # `NAO_DETECTADO` — checkpoint, cache e métricas — segue enxergando o
        # caso como resolvido, e o motivo viaja em coluna própria.
        log.info("    [!] Semgrep não detectou esta CWE (NAO_DETECTADO, %s).",
                 simbolico.motivo)
        for braco in pendentes:
            _registrar(braco, "NAO_DETECTADO", tempo_simbolico,
                       motivo=simbolico.motivo,
                       regras=simbolico.regras_nao_casadas)
        return 0

    if status_simbolico == "HIDRATACAO_FALHOU":
        for braco in pendentes:
            _registrar(braco, "DETECTADO", tempo_simbolico,
                       resposta={"verdict": "ERROR",
                                 "reasoning": "Hidratação falhou (arquivo ilegível)."})
        return 0

    if sem_llm:
        log.info("    [DETECTADO] (medição simbólica; LLM não consultado)")
        for braco in pendentes:
            _registrar(braco, "DETECTADO", tempo_simbolico,
                       resposta={"verdict": "N/A",
                                 "reasoning": "Medição de cobertura simbólica "
                                              "(--sem-llm): LLM não consultado."})
        return 0

    chamadas = 0
    for braco in pendentes:
        t_braco = time.time()
        log.info("    -> Fase 3/4: %s ...", braco)
        try:
            resposta = avaliar(contexto, caso["cwe"], caso["cwe_name"],
                               caso["description"],
                               provedor=(provedores or {}).get(braco.modelo),
                               tipo_prompt=braco.prompt, ficha=ficha)
        except Exception as e:                   # provedor não deve estourar
            log.info("    [ERRO INESPERADO] %s", str(e)[:120])
            _registrar(braco, "ERRO_DESCONHECIDO",
                       tempo_simbolico + time.time() - t_braco, erro=str(e))
            continue
        chamadas += 1
        status = "API_ERROR" if resposta.veredito == "ERROR" else "DETECTADO"
        _registrar(braco, status, tempo_simbolico + time.time() - t_braco,
                   resposta=resposta.como_dict(),
                   erro=resposta.justificativa if status == "API_ERROR" else None,
                   resp_llm=resposta)
    return chamadas


def executar_matriz(casos, bracos, dir_rodada, sem_llm=False,
                    cache_simbolico=None, catalogo=None,
                    incluir_anteriores=False):
    """Roda a população inteira em cada braço, gravando um CSV por braço."""
    catalogo = catalogo or catalogo_padrao()
    processados = carregar_processados(
        None, dir_rodada, incluir_anteriores)
    if processados:
        log.info("[+] RECUPERAÇÃO ATIVA: %d resultados (caso, modelo, prompt) "
                 "já gravados serão pulados.", len(processados))

    csvs_por_braco = {}
    for braco in bracos:
        caminho = os.path.join(dir_rodada, f"{braco.rotulo}.csv")
        # Só cria o cabeçalho se o arquivo ainda não existe: `--run-id` de uma
        # rodada em andamento tem que APENDAR. `inicializar_relatorio` abre em
        # modo "w", então chamá-la aqui sempre apagaria o que já foi gravado.
        if not os.path.exists(caminho):
            inicializar_relatorio(caminho)
        csvs_por_braco[braco] = caminho

    # Um provedor por MODELO, compartilhado entre os braços de prompt daquele
    # modelo: o intervalo mínimo entre chamadas é por provedor, e instanciar de
    # novo a cada braço zeraria o throttle e estouraria a cota.
    provedores = {}
    if not sem_llm:
        for modelo in sorted({b.modelo for b in bracos}):
            provedores[modelo] = criar_provedor(modelo)

    total = len(casos)
    inicio = time.time()
    chamadas = 0

    for idx, caso in enumerate(casos, 1):
        chamadas += processar_caso(
            caso, csvs_por_braco, bracos, idx, total, processados,
            sem_llm=sem_llm, cache_simbolico=cache_simbolico,
            provedores=provedores, catalogo=catalogo)

        decorrido = time.time() - inicio
        medio = decorrido / idx
        log.info("    Sessão: %s | Previsão: %s",
                 timedelta(seconds=int(decorrido)),
                 timedelta(seconds=int((total - idx) * medio)))

    log.info("\n[+] Concluído. Rodada: %s", dir_rodada)
    log.info("[+] Chamadas de LLM efetuadas: %d", chamadas)
    log.info("[+] Tempo total: %s", timedelta(seconds=int(time.time() - inicio)))
    if cache_simbolico is not None:
        log.info("[+] %s", cache_simbolico.resumo())
    return chamadas


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def _desambiguar_rotulos(bracos: list) -> list:
    """Dá sufixo de hash aos braços cujos modelos colidem depois do saneamento.

    Improvável na prática, mas um braço sobrescrever silenciosamente o CSV de
    outro seria falha de integridade dos dados — do mesmo tipo do checkpoint
    indexado só por `ID_Caso`.
    """
    crus_por_saneado = {}
    for b in bracos:
        crus_por_saneado.setdefault(sanear_rotulo(b.modelo), set()).add(b.modelo)
    colididos = {s for s, crus in crus_por_saneado.items() if len(crus) > 1}
    if not colididos:
        return bracos
    return [
        Braco(b.modelo, b.prompt,
              hashlib.sha256(b.modelo.encode("utf-8")).hexdigest()[:8]
              if sanear_rotulo(b.modelo) in colididos else "")
        for b in bracos
    ]


def definir_bracos(args) -> list:
    """Braços selecionados na linha de comando.

    `--matriz` é a matriz de referência do experimento, e continua sendo só o
    par comercial: um braço local roda quando nomeado, nunca por promoção
    automática. Sem `--matriz`, o produto cartesiano de `--modelo` por
    `--prompt`, cada um caindo no padrão da Parte 1 quando omitido — assim
    `run_pipeline.py --amostra 10` continua fazendo o que fazia.
    """
    if args.matriz:
        modelos = [MODELO_GEMINI_PADRAO, MODELO_OPENAI_PADRAO]
        prompts = [BASELINE, ESPECIALISTA]
    else:
        modelos = args.modelo or [MODELO_LLM]
        prompts = args.prompt or [PROMPT_TYPE]
    return _desambiguar_rotulos([Braco(m, p) for m in modelos for p in prompts])


def _e_local(modelo: str) -> bool:
    try:
        return familia_do_modelo(modelo) == "ollama"
    except ValueError:
        # Modelo sem provedor conhecido não é problema da sondagem local:
        # `criar_provedor` o rejeita mais adiante, com a mensagem certa.
        return False


def modelos_locais(bracos) -> list:
    return sorted({b.modelo for b in bracos if _e_local(b.modelo)})


def sondar_modelos_locais(bracos) -> dict:
    """Verifica servidor e modelo de cada braço local, antes do primeiro caso.

    Devolve `{modelo: identidade}`, que é o que o manifesto registra. Rodada só
    com modelos comerciais não faz sondagem nenhuma — a pipeline continua
    funcionando em máquina sem Ollama instalado.
    """
    return {m: criar_provedor(m).sondar() for m in modelos_locais(bracos)}


def main():
    ap = argparse.ArgumentParser(description="Pipeline neuro-simbólica (Semgrep + LLM).")
    modo = ap.add_mutually_exclusive_group()
    modo.add_argument("--tudo", action="store_true",
                      help="Roda todos os casos.")
    modo.add_argument("--fp-only", action="store_true",
                      help="Só casos FP do dataset.")
    modo.add_argument("--tp-only", action="store_true",
                      help="Só pares TP.")
    ap.add_argument("--amostra", type=int, metavar="N",
                    help="Limita a N casos (prioriza o que já está em cache). "
                         "Combinável com --fp-only/--tp-only.")
    ap.add_argument("--trilha", action="append", choices=TRILHAS, metavar="TRILHA",
                    help=f"Restringe a uma trilha ({'|'.join(TRILHAS)}). "
                         "Repetível. Aplicado depois do modo.")
    ap.add_argument("--uma-location", action="store_true",
                    help="Só a primeira location de cada alerta (comportamento "
                         "antigo). Por padrão usa todas.")
    ap.add_argument("--todas-extensoes", action="store_true",
                    help="Inclui locations que não são .go (relatórios .html, "
                         "front-end .tsx/.js). Por padrão só arquivos Go.")
    ap.add_argument("--verboso", action="store_true",
                    help="Log em nível DEBUG (mostra cada invocação do Semgrep).")
    ap.add_argument("--sem-llm", action="store_true",
                    help="Roda só as Fases 1-2 e grava a cobertura simbólica. "
                         "Mede a taxa de detecção sem gastar cota de API.")
    ap.add_argument("--dry-run", action="store_true",
                    help="Só relata a população selecionada, sem executar nada.")
    ap.add_argument("--sem-cache-simbolico", action="store_true",
                    help="Reexecuta Fases 1-2 sempre, sem ler nem gravar o "
                         "cache de resultado simbólico.")
    ap.add_argument("--entre-arquivos", action="store_true",
                    help="Liga a análise ENTRE ARQUIVOS do Semgrep (--pro). "
                         "Desligada por padrão: ligá-la muda o conjunto de "
                         "alertas, invalida o cache simbólico daquela população "
                         "e torna a rodada incomparável com as Rodadas 1-3. "
                         "Exige registro de viabilidade aprovado "
                         "(scripts/verificar_pro.py).")
    ap.add_argument("--modelo", action="append", metavar="MODELO",
                    help=f"Modelo do braço. Repetível. Padrão: {MODELO_LLM}. "
                         f"Modelo local via Ollama: ollama:<tag> "
                         f"(ex.: {MODELO_OLLAMA_PADRAO}).")
    ap.add_argument("--prompt", action="append", choices=TIPOS, metavar="TIPO",
                    help=f"Tipo de prompt ({'|'.join(TIPOS)}). Repetível. "
                         f"Padrão: {PROMPT_TYPE}.")
    ap.add_argument("--matriz", action="store_true",
                    help=f"Matriz 2x2 completa: {MODELO_GEMINI_PADRAO} e "
                         f"{MODELO_OPENAI_PADRAO} x {BASELINE} e {ESPECIALISTA}.")
    ap.add_argument("--run-id", metavar="ID",
                    help="Reaproveita um run_id existente (retoma a rodada).")
    ap.add_argument("--reaproveitar-anteriores", action="store_true",
                    help="Considera resultados de rodadas passadas e da Parte 1 "
                         "no checkpoint. Desligado por padrão: as linhas da "
                         "Parte 1 pertencem ao braço (gemini-2.5-flash-lite, "
                         "especialista) e deixariam esse braço com menos casos "
                         "que os outros três.")
    args = ap.parse_args()

    configurar_log(args.verboso)

    if not any([args.amostra, args.tudo, args.fp_only, args.tp_only]):
        ap.error("Informe um modo: --amostra N, --tudo, --fp-only ou --tp-only")
    if args.matriz and (args.modelo or args.prompt):
        ap.error("--matriz já define os braços; não combine com --modelo/--prompt")
    # Antes de qualquer trabalho: pedir o modo sem viabilidade verificada aborta
    # aqui, e não cai no CE em silêncio no meio da população.
    if args.entre_arquivos:
        try:
            registro, _ = exigir_viabilidade()
        except ModoIndisponivelError as e:
            ap.error(str(e))
        log.info("[!] Modo ENTRE-ARQUIVOS ligado (viabilidade: %s).",
                 os.path.relpath(registro, BASE))
        log.info("    Os alertas NÃO são comparáveis com os das Rodadas 1-3.")

    with open(DATASET_PATH, encoding="utf-8") as f:
        dataset = json.load(f)
    cwe_meta = _cwe_lookup(dataset)

    casos_fp = construir_casos_fp(dataset,
                                  todas_locations=not args.uma_location,
                                  so_go=not args.todas_extensoes)
    casos_tp = (
        construir_casos_tp(TP_PAIRS_OURO, "TP_ouro", cwe_meta) +
        construir_casos_tp(TP_PAIRS_PRATA, "TP_prata", cwe_meta) +
        construir_casos_tp(TP_PAIRS_ALCANCAVEL, "TP_alcancavel", cwe_meta,
                           prefixo_id="TPA:") +
        construir_casos_tp_dataset(dataset,
                                   todas_locations=not args.uma_location,
                                   so_go=not args.todas_extensoes)
    )

    if args.fp_only:
        casos = casos_fp
    elif args.tp_only:
        casos = casos_tp
    else:
        casos = casos_fp + casos_tp

    if args.trilha:
        casos = [c for c in casos if c.origem in set(args.trilha)]

    # Antes de qualquer varredura ou chamada de LLM: um ID repetido só se
    # manifestaria como caso a menos no fim de uma rodada de horas.
    verificar_ids_unicos(casos)

    if args.amostra:
        casos = priorizar_locais(casos)[:args.amostra]

    bracos = definir_bracos(args)
    catalogo = catalogo_padrao()

    n_arq, n_bytes = estatisticas_cache()
    por_trilha = contar_por_trilha(casos)
    log.info("=== PIPELINE NEURO-SIMBÓLICA (Semgrep) ===")
    log.info("[+] Casos selecionados: %d (%s)", len(casos),
             ", ".join(f"{t}={n}" for t, n in por_trilha.items()))
    log.info("[+] Cache: %d arquivos | %.1f MB (%s/)", n_arq,
             n_bytes / 1024 / 1024, os.path.basename(CACHE_DIR))
    log.info("[+] Braços (%d): %s", len(bracos),
             ", ".join(str(b) for b in bracos))
    log.info("[+] Catálogo CWE: %d fichas | sha256 %s...",
             len(catalogo.cwes_especificas), catalogo.sha256[:12])

    if args.dry_run:
        log.info("[+] --dry-run: nada foi executado.")
        return

    # Sondagem antes do primeiro caso: sem ela, um `ollama serve` esquecido
    # produziria uma linha ERROR por caso, cada uma depois de quatro tentativas
    # com backoff — dezenas de minutos para descobrir um erro de operação.
    sondagens = {}
    if not args.sem_llm:
        try:
            sondagens = sondar_modelos_locais(bracos)
        except OllamaIndisponivel as e:
            log.error("[X] %s", e)
            sys.exit(2)
        for modelo, info in sondagens.items():
            log.info("[+] Modelo local %s: Ollama %s | %s | digest %s... | "
                     "num_ctx %d | %s", modelo, info["versao_ollama"],
                     info["quantizacao"], (info["digest"] or "?")[:12],
                     info["num_ctx"], info["processador"] or "processador ?")

    run_id = args.run_id or novo_run_id()
    dir_rodada = os.path.join(RESULTS_DIR, run_id)
    os.makedirs(dir_rodada, exist_ok=True)
    log.info("[+] Rodada: results/%s/", run_id)

    if args.sem_llm:
        log.info("[+] Modo --sem-llm: só cobertura simbólica (nenhuma chamada de API).")
    cache_simbolico = CacheSimbolico(
        ativo=not args.sem_cache_simbolico,
        motor=motor_corrente(args.entre_arquivos))
    log.info("[+] Cache simbólico: %s (rulesets %s)",
             "ativo" if cache_simbolico.ativo else "DESATIVADO",
             cache_simbolico.versao_ruleset)
    log.info("=" * 44)

    inicio = datetime.now(timezone.utc)
    try:
        executar_matriz(casos, bracos, dir_rodada, sem_llm=args.sem_llm,
                        cache_simbolico=cache_simbolico, catalogo=catalogo,
                        incluir_anteriores=args.reaproveitar_anteriores)
    finally:
        # O manifesto é gravado mesmo em rodada interrompida: sem ele os CSVs
        # parciais ficam sem procedência.
        destino = gravar_manifesto(
            dir_rodada, run_id, bracos, por_trilha, len(casos), inicio,
            datetime.now(timezone.utc), catalogo, args.sem_llm,
            cache_simbolico.ativo, " ".join(sys.argv), sondagens,
            entre_arquivos=args.entre_arquivos)
        log.info("[+] Manifesto: %s", os.path.relpath(destino, BASE))


if __name__ == "__main__":
    main()
