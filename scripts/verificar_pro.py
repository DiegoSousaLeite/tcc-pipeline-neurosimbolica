"""
verificar_pro.py — portão de viabilidade do modo entre-arquivos do Semgrep.

Por que existe
--------------
As duas maiores CWEs da classe positiva são baldes secos (CWE-22: 114 pares, 0
detecções; CWE-918: 112 pares, 1) e a causa medida é o alcance do motor: 0 de
807 alertas do corpus trouxeram trilha de dataflow, mesmo com
`--dataflow-traces`. O Semgrep CE rastreia taint apenas DENTRO de um arquivo.

O modo entre-arquivos ataca exatamente essa causa — mas a evidência de que ele é
gratuito veio de `semgrep.dev/pricing`, página comercial, não de documentação
técnica nem de termo de licença. Este script é o portão: mede, com evidência
própria e datada, se o modo está disponível nas condições deste projeto antes de
qualquer investimento de implementação.

Por que o alvo NÃO é o cache de fontes
--------------------------------------
`cache/` guarda UM arquivo por caso — 69 dos 226 casos de CWE-22 e CWE-918 têm
um único arquivo no diretório do commit, e os vizinhos, quando existem, são
arquivos vulneráveis de OUTROS casos, não os chamadores. O diagnóstico que
motiva o portão é que a fonte do taint está em outro arquivo; esse arquivo não
está no cache. Rodar o modo entre-arquivos ali devolveria zero trilhas
INDEPENDENTEMENTE de o motor funcionar, e a classificação `inconclusivo`
descreveria a forma do cache, não o alcance do Semgrep — o pior resultado
possível, porque pareceria evidência. Por isso alvo de arquivo isolado é
RECUSADO, não classificado.

Três etapas, custo crescente
----------------------------
1. `sintetica` — projeto Go mínimo escrito para este fim, com fonte num arquivo
   e sumidouro em outro. Custa segundos e pode devolver `indisponivel`, o que
   encerra o portão sem clonar nada.
2. `real` — checkout raso de repositórios da população nos `parent_commit`,
   metade de CWE-22 e metade de CWE-918. Custa disco e rede, escassos nesta
   máquina; só roda se a etapa 1 não tiver matado a change.
3. `gabarito` — a mesma coisa, mas olhando SÓ os arquivos do gabarito e
   aplicando a regra de pareamento da Fase 1.

ATENÇÃO AO CRITÉRIO. As etapas 1 e 2 classificam `viavel` com "≥1 trilha entre
arquivos", que mede a CAPACIDADE DO MOTOR. A etapa 3 classifica `viavel` só se
o motor novo DETECTAR UM CASO QUE O CE PERDEU. São perguntas diferentes, e elas
divergiram na medição de 2026-09-15: o portão passou pelas etapas 1 e 2, e o
cruzamento do `seaweedfs` mostrou 0 alertas nos arquivos do gabarito nos dois
modos. Um portão que passa quando o ganho não chega aos casos não é portão —
para decidir repopulação, use a etapa 3.

O controle positivo
-------------------
A etapa sintética inclui um terceiro arquivo com fonte e sumidouro na MESMA
função, que o motor CE já detecta hoje. Sem ele, "nenhuma trilha" seria
ambíguo entre "o motor não atravessa arquivos" e "o alvo ou o ruleset estão
errados". Com ele, a ausência de detecção no controle denuncia o instrumento em
vez de acusar o motor.

USO
  python scripts/verificar_pro.py --selftest        # valida a lógica, sem rede
  python scripts/verificar_pro.py --etapa sintetica # só a etapa barata
  python scripts/verificar_pro.py --etapa real      # só a etapa cara
  python scripts/verificar_pro.py --etapa gabarito  # detecta os NOSSOS casos?
  python scripts/verificar_pro.py                   # as duas, na ordem

EXIGE rede e `semgrep login` + `semgrep install-semgrep-pro` (exceto --selftest).
NÃO grava nem invalida entrada de cache simbólico, e não produz CSV de rodada.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

from src.fase1_semgrep import (  # noqa: E402
    SEMGREP,
    SEMGREP_CONFIG,
    _cwe_nas_tags,
)
from src.fonte import caminho_cache  # noqa: E402

POPULACAO = os.path.join(BASE, "tp_pairs_osv_alcancavel.json")
DATA_DIR = os.path.join(BASE, "data")

# Classificações possíveis. Um resultado ambíguo NUNCA é sucesso: `inconclusivo`
# não autoriza a implementação, exatamente como `indisponivel`.
VIAVEL = "viavel"
INCONCLUSIVO = "inconclusivo"
INDISPONIVEL = "indisponivel"

# Motivos, para que a classificação não precise ser interpretada depois.
MOTIVO_TRILHA = "trilha_entre_arquivos_presente"
MOTIVO_SEM_TRILHA = "modo_executou_sem_trilha"
MOTIVO_PLANO = "recusado_por_plano_ou_binario_ausente"
MOTIVO_CONTROLE = "controle_positivo_falhou"

# Marcas de recusa do lado do servidor/binário. Distinguem "o recurso exige
# plano pago" e "o binário Pro não está instalado" de um erro qualquer de
# execução — os dois primeiros são resposta do portão, o terceiro é defeito.
_MARCAS_INDISPONIVEL = (
    "install-semgrep-pro",
    "requires a semgrep pro",
    "pro engine",
    "not available on your plan",
    "requires a paid",
    "upgrade your plan",
    "you are not logged in",
    "run `semgrep login`",
    "run 'semgrep login'",
    "login required",
)

SEMGREP_TIMEOUT_ALVO = int(os.environ.get("VERIFICAR_PRO_TIMEOUT", "900"))


def _matar_arvore(pid):
    """Mata o processo e TODOS os descendentes dele.

    No Windows, `taskkill /T` é o que alcança os netos; sem isso o binário do
    Semgrep continua rodando depois de o pai ter sido morto, e continua
    segurando o pipe.
    """
    if os.name == "nt":
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)],
                       capture_output=True)
    else:                                       # pragma: no cover - CI é Windows
        import signal
        try:
            os.killpg(os.getpgid(pid), signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass


def apagar(caminho):
    """Apaga uma árvore, inclusive os objetos somente-leitura do git.

    `shutil.rmtree(ignore_errors=True)` falha em silêncio no Windows: o git
    grava os arquivos de `.git/objects` sem permissão de escrita, e a remoção
    para ali sem levantar nada. O resultado é um checkout de centenas de MB que
    fica em disco enquanto o script afirma tê-lo apagado — e `repos/` já foi
    apagado três vezes nesta máquina por pressão de disco, justamente o custo
    que este script promete não repetir. Devolve True se a árvore sumiu.
    """
    def _forcar(func, alvo, _exc):
        os.chmod(alvo, 0o700)
        func(alvo)

    shutil.rmtree(caminho, onerror=_forcar)
    return not os.path.exists(caminho)


class AlvoInvalidoError(Exception):
    """O alvo não permite que o modo entre-arquivos atravesse coisa alguma.

    É erro, e não classificação: medir alcance entre arquivos sobre um alvo de
    arquivo único mede o alvo, não o motor.
    """


# -- alvo ------------------------------------------------------------------

def arquivos_go(diretorio):
    """Caminhos `.go` sob o diretório, em ordem estável."""
    achados = []
    for raiz, _, arquivos in os.walk(diretorio):
        for a in arquivos:
            if a.endswith(".go"):
                achados.append(os.path.join(raiz, a))
    return sorted(achados)


def validar_alvo(diretorio):
    """Garante que o alvo tem para onde atravessar. Devolve os `.go` achados."""
    if not os.path.isdir(diretorio):
        raise AlvoInvalidoError(f"alvo não é diretório: {diretorio}")
    achados = arquivos_go(diretorio)
    if len(achados) < 2:
        raise AlvoInvalidoError(
            f"alvo com {len(achados)} arquivo(s) Go em {diretorio}: o modo "
            f"entre-arquivos não tem para onde atravessar. Um resultado daqui "
            f"descreveria o alvo, não o motor.")
    return achados


# -- leitura do SARIF ------------------------------------------------------

def _uris_da_trilha(code_flow):
    """URIs distintas tocadas por uma trilha de dataflow do SARIF."""
    uris = set()
    for tf in code_flow.get("threadFlows", []):
        for loc in tf.get("locations", []):
            uri = (loc.get("location", {}).get("physicalLocation", {})
                   .get("artifactLocation", {}).get("uri"))
            if uri:
                uris.add(uri)
    return uris


def contar_trilhas(sarif):
    """`(alertas, com_trilha, entre_arquivos, regras)` de um documento SARIF.

    `entre_arquivos` é o número que importa: uma trilha confinada a um arquivo
    é o que o CE já produzia, e não é evidência de alcance novo. As duas
    contagens vão para o relatório porque esconder a diferença entre elas seria
    o mesmo tipo de silêncio que o portão existe para evitar.
    """
    resultados = []
    for run in sarif.get("runs", []):
        resultados.extend(run.get("results", []))

    com_trilha = entre_arquivos = 0
    for r in resultados:
        fluxos = r.get("codeFlows") or []
        if not fluxos:
            continue
        com_trilha += 1
        if any(len(_uris_da_trilha(f)) > 1 for f in fluxos):
            entre_arquivos += 1

    regras = sorted({str(r.get("ruleId")) for r in resultados if r.get("ruleId")})
    return len(resultados), com_trilha, entre_arquivos, regras


def indica_indisponivel(stderr):
    """A saída de erro diz que o recurso exige plano ou binário ausente?"""
    baixo = (stderr or "").lower()
    return any(marca in baixo for marca in _MARCAS_INDISPONIVEL)


# -- classificação ---------------------------------------------------------

def classificar(pro_executou, erro_indisponivel, trilhas_entre_arquivos,
                controle_ok=True):
    """Classificação final do portão, a partir dos fatos medidos.

    Pura de propósito: é a única lógica do script que o `--selftest` consegue
    validar sem rede, e é a que decide se a change continua.
    """
    if erro_indisponivel or not pro_executou:
        return INDISPONIVEL, MOTIVO_PLANO
    if not controle_ok:
        # O instrumento falhou. Acusar o motor aqui seria atribuir a ele um
        # defeito nosso, e a change morreria pelo motivo errado.
        return INCONCLUSIVO, MOTIVO_CONTROLE
    if trilhas_entre_arquivos > 0:
        return VIAVEL, MOTIVO_TRILHA
    return INCONCLUSIVO, MOTIVO_SEM_TRILHA


# -- execução do Semgrep ---------------------------------------------------

def rodar_semgrep(alvo, pro):
    """Roda o Semgrep sobre o alvo num dos dois modos.

    Devolve dict com sarif (ou None), tempo de parede, rc e stderr. Não levanta
    por rc != 0: um rc de recusa por plano é RESULTADO do portão, não falha.

    O timeout mata a ÁRVORE de processos, e não só o filho direto. A cadeia real
    é `semgrep.exe` -> `pysemgrep.exe` -> `python.exe` ->
    `semgrep-core-proprietary.exe`, e `subprocess.run(timeout=)` mata apenas o
    topo: os netos sobrevivem segurando o pipe de stdout, o `communicate()`
    espera um pipe que nunca fecha, e a execução trava. Medido: 56 minutos
    contra um teto de 20, e só destravou quando os netos foram mortos à mão.
    """
    cmd = [SEMGREP, "--config", SEMGREP_CONFIG, "--sarif", "--quiet",
           "--dataflow-traces"]
    if pro:
        cmd.append("--pro")
    cmd.append(alvo)

    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    t0 = time.time()
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                         env=env)
    estourou = False
    try:
        out, err = p.communicate(timeout=SEMGREP_TIMEOUT_ALVO)
    except subprocess.TimeoutExpired:
        _matar_arvore(p.pid)
        out, err = p.communicate()
        estourou = True
    rc, saida, erro = (p.returncode,
                       out.decode("utf-8", "ignore").strip(),
                       err.decode("utf-8", "ignore").strip())
    if estourou:
        return {"sarif": None, "segundos": time.time() - t0, "rc": rc,
                "stderr": f"timeout de {SEMGREP_TIMEOUT_ALVO}s; {erro[:400]}"}

    segundos = time.time() - t0
    sarif = None
    if saida:
        try:
            sarif = json.loads(saida)
        except json.JSONDecodeError:
            sarif = None
    return {"sarif": sarif, "segundos": segundos, "rc": rc, "stderr": erro}


def medir(alvo, rotulo):
    """Mede os dois modos sobre o mesmo alvo e devolve o bloco do relatório."""
    validar_alvo(alvo)
    bloco = {"alvo": rotulo, "arquivos_go": len(arquivos_go(alvo))}
    for modo, pro in (("ce", False), ("pro", True)):
        r = rodar_semgrep(alvo, pro)
        if r["sarif"] is None:
            bloco[modo] = {"executou": False, "segundos": round(r["segundos"], 1),
                           "rc": r["rc"], "stderr": r["stderr"][:1000]}
            continue
        alertas, com_trilha, entre, regras = contar_trilhas(r["sarif"])
        bloco[modo] = {
            "executou": True,
            "segundos": round(r["segundos"], 1),
            "rc": r["rc"],
            "alertas": alertas,
            "alertas_com_trilha": com_trilha,
            "alertas_com_trilha_entre_arquivos": entre,
            "regras": regras,
            "stderr": r["stderr"][:1000],
        }
    return bloco


# -- etapa sintética -------------------------------------------------------

# Projeto Go mínimo. A fonte (`r.URL`, num handler HTTP) e o sumidouro
# (`http.Get`) ficam em arquivos DIFERENTES: é a forma exata que
# `go.lang.security.injection.tainted-url-host` (CWE-918) descreve e que o
# motor CE, por rastrear taint só dentro do arquivo, não consegue fechar.
_SINTETICO = {
    "go.mod": "module portao\n\ngo 1.21\n",
    # fonte, sem sumidouro
    "handler.go": (
        "package portao\n\n"
        "import \"net/http\"\n\n"
        "// Handle recebe a entrada não confiável e a entrega a outro arquivo.\n"
        "func Handle(w http.ResponseWriter, r *http.Request) {\n"
        "\talvo := r.URL.Query().Get(\"u\")\n"
        "\tBuscar(alvo)\n"
        "}\n"
    ),
    # sumidouro, sem fonte
    "fetch.go": (
        "package portao\n\n"
        "import \"net/http\"\n\n"
        "// Buscar é o sumidouro. A origem do argumento está em handler.go.\n"
        "func Buscar(u string) {\n"
        "\thttp.Get(u)\n"
        "}\n"
    ),
    # CONTROLE POSITIVO: fonte e sumidouro na mesma função. O CE detecta isto
    # hoje; se não detectar, o problema é do instrumento, não do motor.
    "controle.go": (
        "package portao\n\n"
        "import \"net/http\"\n\n"
        "// Controle tem fonte e sumidouro na MESMA função: é o que o motor CE\n"
        "// já alcança, e serve para provar que alvo e ruleset estão sãos.\n"
        "func Controle(w http.ResponseWriter, r *http.Request) {\n"
        "\talvo := r.URL.Query().Get(\"u\")\n"
        "\thttp.Get(alvo)\n"
        "}\n"
    ),
}


def escrever_sintetico(destino):
    """Materializa o projeto mínimo em disco. Devolve o diretório."""
    os.makedirs(destino, exist_ok=True)
    for nome, conteudo in _SINTETICO.items():
        with open(os.path.join(destino, nome), "w", encoding="utf-8",
                  newline="\n") as f:
            f.write(conteudo)
    return destino


def etapa_sintetica(manter=False):
    """Etapa barata: o motor entre-arquivos roda, e atravessa arquivos em Go?"""
    tmp = tempfile.mkdtemp(prefix="portao_pro_sintetico_")
    try:
        alvo = escrever_sintetico(os.path.join(tmp, "portao"))
        bloco = medir(alvo, "sintetico")
        # O controle positivo é o alerta do CE sobre controle.go. Basta que o
        # CE tenha emitido algum alerta da regra de SSRF para o alvo estar são.
        ce = bloco.get("ce", {})
        bloco["controle_ce_ok"] = bool(ce.get("executou") and ce.get("alertas"))
        return bloco
    finally:
        if not manter:
            apagar(tmp)


# -- etapa real ------------------------------------------------------------

def amostra_real(n_por_cwe=5):
    """Amostra fixa e determinística de casos de CWE-22 e CWE-918.

    A ordenação é explícita e o sorteio é por posição espaçada, não pelos
    primeiros da lista: o corte alfabético entregaria `1panel`, `alist`,
    `aqua`… — determinístico, mas enviesado para uma ponta do alfabeto e, com
    ela, para um recorte arbitrário de tamanho e idade de projeto. O
    espaçamento uniforme mantém a determinismo (duas execuções do portão medem
    os mesmos repositórios, ou os números não se comparam) sem escolher a
    vizinhança.

    Um repositório por caso, sem repetir — clonar o mesmo repo duas vezes
    pagaria o custo caro duas vezes pela mesma evidência.
    """
    with open(POPULACAO, encoding="utf-8") as f:
        pares = json.load(f)

    escolhidos, vistos = [], set()
    for cwe in ("CWE-22", "CWE-918"):
        candidatos = []
        for p in sorted((p for p in pares if p.get("cwe_id") == cwe),
                        key=lambda p: (p["repo"], p["parent_commit"],
                                       p["arquivo"])):
            if p["repo"] in vistos:
                continue
            # Só interessa caso cujo arquivo já está no cache: é a garantia de
            # que o caso é o mesmo que as rodadas CE mediram.
            if not os.path.exists(caminho_cache(p["repo"], p["parent_commit"],
                                                p["arquivo"])):
                continue
            vistos.add(p["repo"])
            candidatos.append(p)

        if not candidatos:
            continue
        if len(candidatos) <= n_por_cwe:
            escolhidos.extend(candidatos)
            continue
        passo = len(candidatos) / n_por_cwe
        escolhidos.extend(candidatos[int(i * passo)] for i in range(n_por_cwe))
    return escolhidos


def clonar_raso(repo, commit, destino):
    """Traz UM commit, sem histórico. Devolve o diretório ou levanta.

    `git init` + `fetch --depth 1 <sha>` é a forma mais barata de obter uma
    árvore num commit arbitrário: um clone completo do cilium custa ~1 GB para
    entregar o que aqui são alguns MB, e `repos/` já foi apagado três vezes
    nesta máquina por pressão de disco.
    """
    os.makedirs(destino, exist_ok=True)
    url = f"https://github.com/{repo}.git"
    passos = [
        ["git", "init", "-q"],
        ["git", "remote", "add", "origin", url],
        ["git", "fetch", "-q", "--depth", "1", "--filter=blob:none",
         "origin", commit],
        ["git", "checkout", "-q", "FETCH_HEAD"],
    ]
    for passo in passos:
        res = subprocess.run(passo, cwd=destino, capture_output=True, timeout=600)
        if res.returncode != 0:
            raise RuntimeError(
                f"{' '.join(passo)} falhou em {repo}@{commit[:10]}: "
                f"{res.stderr.decode('utf-8', 'ignore')[:300]}")
    return destino


def etapa_real(n_por_cwe=5, manter=False):
    """Etapa cara: o motor alcança os casos DESTE experimento?"""
    casos = amostra_real(n_por_cwe)
    blocos = []
    tmp = tempfile.mkdtemp(prefix="portao_pro_real_")
    try:
        for i, p in enumerate(casos, 1):
            rotulo = f"{p['repo']}@{p['parent_commit'][:10]} ({p['cwe_id']})"
            print(f"[{i}/{len(casos)}] {rotulo}")
            destino = os.path.join(tmp, f"r{i}")
            try:
                clonar_raso(p["repo"], p["parent_commit"], destino)
            except Exception as e:
                blocos.append({"alvo": rotulo, "erro_clone": str(e)[:500]})
                continue
            try:
                bloco = medir(destino, rotulo)
            except AlvoInvalidoError as e:
                blocos.append({"alvo": rotulo, "alvo_invalido": str(e)})
                continue
            bloco["cwe"] = p["cwe_id"]
            bloco["arquivo_do_caso"] = p["arquivo"]
            blocos.append(bloco)
            # O checkout é apagado assim que medido: dez repositórios vivos ao
            # mesmo tempo é exatamente a pressão de disco que motivou apagar
            # `repos/` três vezes.
            if not manter:
                if not apagar(destino):
                    print(f"   [!] não consegui apagar {destino}")
    finally:
        if not manter:
            apagar(tmp)
    return blocos


# -- etapa gabarito --------------------------------------------------------
#
# Esta etapa existe porque o critério das outras duas está errado para a decisão
# que elas deveriam apoiar. Elas classificam `viavel` com "≥1 trilha entre
# arquivos no alvo", o que mede a CAPACIDADE DO MOTOR. A pergunta que autoriza
# gastar repopulação é outra: **o motor novo detecta os casos que o antigo
# perdeu?** As duas divergiram na medição de 2026-09-15 — o portão passou e o
# cruzamento manual do seaweedfs mostrou 0 alertas nos arquivos do gabarito nos
# dois modos.

def _relativo(uri, raiz):
    u = str(uri).replace("\\", "/")
    base = str(raiz).replace("\\", "/").rstrip("/")
    return u[len(base):].lstrip("/") if u.startswith(base) else u


def analisar_gabarito(sarif, raiz, arquivos_gabarito, cwe):
    """O que o motor viu NOS arquivos do gabarito, e não no repositório todo."""
    run = (sarif.get("runs") or [{}])[0]
    resultados = run.get("results", [])
    tags = {r.get("id"): (r.get("properties") or {}).get("tags", [])
            for r in run.get("tool", {}).get("driver", {}).get("rules", [])}

    no_gabarito, casados, trilhas_tocando = [], [], []
    for r in resultados:
        loc = (r.get("locations") or [{}])[0].get("physicalLocation", {})
        arq = _relativo(loc.get("artifactLocation", {}).get("uri", ""), raiz)
        rid = r.get("ruleId")

        tocadas = {_relativo(u, raiz) for f in (r.get("codeFlows") or [])
                   for tf in f.get("threadFlows", [])
                   for loc2 in tf.get("locations", [])
                   for u in [loc2.get("location", {})
                             .get("physicalLocation", {})
                             .get("artifactLocation", {}).get("uri", "")]}
        if len(tocadas) > 1 and (tocadas & arquivos_gabarito
                                 or arq in arquivos_gabarito):
            trilhas_tocando.append({"regra": rid, "arquivos": sorted(tocadas)})

        if arq in arquivos_gabarito:
            entrada = {"regra": rid, "arquivo": arq,
                       "linha": loc.get("region", {}).get("startLine")}
            no_gabarito.append(entrada)
            # MESMA regra de pareamento da Fase 1, importada e não recopiada:
            # se a medição aceitasse por um critério e a pipeline por outro, o
            # número aqui não descreveria o que a rodada produziria.
            if _cwe_nas_tags(tags.get(rid, []), cwe):
                casados.append(entrada)

    return {
        "alertas_no_repo": len(resultados),
        "alertas_no_gabarito": no_gabarito,
        "casam_com_a_cwe": casados,
        "veredito_fase1": "DETECTADO" if casados else "NAO_DETECTADO",
        "trilhas_entre_arquivos_tocando_gabarito": trilhas_tocando,
    }


def etapa_gabarito(n_por_cwe=2, manter=False, ao_medir=None):
    """Mede, por caso, se o motor novo detecta o que o CE perdeu.

    `ao_medir` recebe cada bloco assim que ele fica pronto, para que o relatório
    seja gravado INCREMENTALMENTE. Na etapa real o relatório só era escrito no
    fim, e quando a execução travou no 9º de 10 as 8 medições anteriores — cerca
    de duas horas — só não se perderam porque foi possível destravar o processo
    em vez de matá-lo. Não é uma aposta para repetir.
    """
    casos = amostra_real(n_por_cwe)
    blocos = []
    tmp = tempfile.mkdtemp(prefix="portao_pro_gabarito_")
    try:
        for i, p in enumerate(casos, 1):
            rotulo = f"{p['repo']}@{p['parent_commit'][:10]} ({p['cwe_id']})"
            print(f"[{i}/{len(casos)}] {rotulo} :: {p['arquivo']}", flush=True)
            bloco = {"alvo": rotulo, "repo": p["repo"],
                     "commit": p["parent_commit"], "cwe": p["cwe_id"],
                     "arquivo_do_caso": p["arquivo"]}
            destino = os.path.join(tmp, f"g{i}")
            try:
                clonar_raso(p["repo"], p["parent_commit"], destino)
                validar_alvo(destino)
            except (RuntimeError, AlvoInvalidoError) as e:
                bloco["erro"] = str(e)[:400]
                blocos.append(bloco)
                if ao_medir:
                    ao_medir(blocos)
                continue

            gabarito = {p["arquivo"]}
            for modo, pro in (("ce", False), ("pro", True)):
                r = rodar_semgrep(destino, pro)
                if r["sarif"] is None:
                    bloco[modo] = {"executou": False,
                                   "segundos": round(r["segundos"], 1),
                                   "stderr": r["stderr"][:400]}
                    continue
                dados = analisar_gabarito(r["sarif"], destino, gabarito,
                                          p["cwe_id"])
                dados["executou"] = True
                dados["segundos"] = round(r["segundos"], 1)
                bloco[modo] = dados
                print(f"     {modo}: {dados['veredito_fase1']} "
                      f"({len(dados['alertas_no_gabarito'])} alertas no arquivo "
                      f"do caso, {dados['segundos']}s)", flush=True)

            bloco["ganho"] = _ganho(bloco)
            blocos.append(bloco)
            if ao_medir:
                ao_medir(blocos)
            if not manter and not apagar(destino):
                print(f"   [!] não consegui apagar {destino}", flush=True)
    finally:
        if not manter:
            apagar(tmp)
    return blocos


def _ganho(bloco):
    """O Pro detectou um caso que o CE perdeu?

    Só isto é ganho. Alerta novo em outro arquivo do repositório não é: o
    experimento pontua o veredito contra o gabarito DAQUELE caso, e um alerta
    que não pertence ao caso não vira amostra avaliável.
    """
    ce, pro = bloco.get("ce") or {}, bloco.get("pro") or {}
    if not (ce.get("executou") and pro.get("executou")):
        return "sem_dado"
    antes = ce.get("veredito_fase1")
    depois = pro.get("veredito_fase1")
    if antes == "NAO_DETECTADO" and depois == "DETECTADO":
        return "ganho"
    if antes == "DETECTADO" and depois == "NAO_DETECTADO":
        return "perda"
    return "igual"


def classificar_gabarito(blocos):
    """`viavel` só se o motor novo detectar algum caso que o CE perdeu."""
    ganhos = [b for b in blocos if b.get("ganho") == "ganho"]
    medidos = [b for b in blocos if b.get("ganho") in ("ganho", "igual", "perda")]
    if not medidos:
        return INDISPONIVEL, "nenhum_caso_medido"
    if ganhos:
        return VIAVEL, f"deteccao_nova_em_{len(ganhos)}_de_{len(medidos)}"
    return INCONCLUSIVO, f"nenhuma_deteccao_nova_em_{len(medidos)}_casos"


# -- relatório -------------------------------------------------------------

def versao_semgrep():
    try:
        res = subprocess.run([SEMGREP, "--version"], capture_output=True,
                             timeout=120)
        return res.stdout.decode("utf-8", "ignore").strip().splitlines()[-1]
    except Exception as e:
        return f"indisponível: {e}"


def _agregar(blocos):
    """Somatório dos blocos medidos, no modo pro."""
    trilhas = executou = 0
    indisponivel = False
    for b in blocos:
        pro = b.get("pro") or {}
        if pro.get("executou"):
            executou += 1
            trilhas += pro.get("alertas_com_trilha_entre_arquivos", 0)
        elif indica_indisponivel(pro.get("stderr", "")):
            indisponivel = True
    return executou, trilhas, indisponivel


def _gravar(relatorio):
    """Grava o relatório, FUNDINDO com as etapas já medidas hoje.

    Chamado a cada caso medido, e não só no fim: na etapa real o relatório só
    era escrito no encerramento, e quando a execução travou no 9º de 10 as oito
    medições anteriores — cerca de duas horas — quase se perderam.

    A fusão existe porque o nome do arquivo é por data: rodar uma etapa isolada
    depois de outra sobrescreveria a primeira, e o portão perderia justamente a
    evidência que autoriza (ou não) a implementação. Etapa remedida no mesmo dia
    substitui a anterior; etapa não rodada é preservada.
    """
    os.makedirs(DATA_DIR, exist_ok=True)
    destino = os.path.join(
        DATA_DIR,
        f"viabilidade_pro_{datetime.now().strftime('%Y%m%d')}.json")

    saida = dict(relatorio)
    if os.path.exists(destino):
        try:
            with open(destino, encoding="utf-8") as f:
                anterior = json.load(f)
        except (OSError, json.JSONDecodeError):
            anterior = {}
        etapas = dict(anterior.get("etapas") or {})
        etapas.update(saida.get("etapas") or {})
        saida["etapas"] = etapas
        # A classificação de cada etapa fica junto dela; a do topo é a da última
        # etapa executada, e o histórico das outras não é apagado.
        historico = dict(anterior.get("classificacao_por_etapa") or {})
        if anterior.get("classificacao"):
            for nome in (anterior.get("etapas") or {}):
                historico.setdefault(nome, {
                    "classificacao": anterior["classificacao"],
                    "motivo": anterior.get("motivo")})
        saida["classificacao_por_etapa"] = historico

    with open(destino, "w", encoding="utf-8", newline="\n") as f:
        json.dump(saida, f, ensure_ascii=False, indent=1)
    return destino


def executar(etapas, n_por_cwe, manter):
    relatorio = {
        "data": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "semgrep_versao": versao_semgrep(),
        "ruleset": SEMGREP_CONFIG,
        "etapas": {},
    }

    classificacao = motivo = None

    if "sintetica" in etapas:
        print("== etapa sintética ==")
        bloco = etapa_sintetica(manter)
        relatorio["etapas"]["sintetica"] = bloco
        executou, trilhas, indisp = _agregar([bloco])
        classificacao, motivo = classificar(
            pro_executou=bool(executou), erro_indisponivel=indisp,
            trilhas_entre_arquivos=trilhas,
            controle_ok=bloco.get("controle_ce_ok", True))
        print(f"   -> {classificacao} ({motivo})")
        if classificacao == INDISPONIVEL and "real" in etapas:
            print("   etapa real dispensada: o modo não está disponível.")
            etapas = [e for e in etapas if e != "real"]

    if "gabarito" in etapas:
        print("== etapa gabarito ==")

        def _parcial(blocos):
            relatorio["etapas"]["gabarito"] = blocos
            c, m = classificar_gabarito(blocos)
            relatorio["classificacao"], relatorio["motivo"] = c, m
            _gravar(relatorio)

        blocos = etapa_gabarito(n_por_cwe, manter, ao_medir=_parcial)
        relatorio["etapas"]["gabarito"] = blocos
        classificacao, motivo = classificar_gabarito(blocos)
        print(f"   -> {classificacao} ({motivo})")

    if "real" in etapas:
        print("== etapa real ==")
        blocos = etapa_real(n_por_cwe, manter)
        relatorio["etapas"]["real"] = blocos
        executou, trilhas, indisp = _agregar(blocos)
        classificacao, motivo = classificar(
            pro_executou=bool(executou), erro_indisponivel=indisp,
            trilhas_entre_arquivos=trilhas)
        print(f"   -> {classificacao} ({motivo})")

    relatorio["classificacao"] = classificacao
    relatorio["motivo"] = motivo

    destino = _gravar(relatorio)

    print(f"\n=== CLASSIFICAÇÃO: {classificacao} ({motivo}) ===")
    print(f"[+] Relatório: {destino}")
    if classificacao != VIAVEL:
        print("[!] Portão NÃO autoriza a implementação (tarefa 1.4): registre o "
              "resultado em docs/MAPA-TCC-O-QUE-REESCREVER.md e arquive a change.")
    return relatorio


# -- selftest --------------------------------------------------------------

def selftest():
    """Valida classificação, leitura de trilha e recusa de alvo, sem rede."""
    falhas = []

    def checa(rotulo, obtido, esperado):
        ok = obtido == esperado
        print(f"  {'ok  ' if ok else 'FALHA'} {rotulo}: {obtido!r} "
              f"(esperado {esperado!r})")
        if not ok:
            falhas.append(rotulo)

    print("=== SELFTEST (sem rede) ===")
    print("-- classificação --")
    checa("trilha entre arquivos -> viável",
          classificar(True, False, 3), (VIAVEL, MOTIVO_TRILHA))
    checa("rodou sem trilha -> inconclusivo",
          classificar(True, False, 0), (INCONCLUSIVO, MOTIVO_SEM_TRILHA))
    checa("recusado por plano -> indisponível",
          classificar(False, True, 0), (INDISPONIVEL, MOTIVO_PLANO))
    checa("não executou -> indisponível",
          classificar(False, False, 0), (INDISPONIVEL, MOTIVO_PLANO))
    checa("controle falhou -> inconclusivo, e não viável",
          classificar(True, False, 5, controle_ok=False),
          (INCONCLUSIVO, MOTIVO_CONTROLE))

    print("-- marcas de indisponibilidade --")
    checa("pede install-semgrep-pro",
          indica_indisponivel("Error: you need to run `semgrep install-semgrep-pro`"),
          True)
    checa("erro comum não é indisponibilidade",
          indica_indisponivel("Syntax error while parsing rule"), False)

    print("-- leitura de trilha no SARIF --")
    def _loc(uri):
        return {"location": {"physicalLocation": {
            "artifactLocation": {"uri": uri}, "region": {"startLine": 1}}}}

    sarif = {"runs": [{"results": [
        # trilha que atravessa arquivos
        {"ruleId": "regra.a", "codeFlows": [{"threadFlows": [
            {"locations": [_loc("handler.go"), _loc("fetch.go")]}]}]},
        # trilha confinada a um arquivo
        {"ruleId": "regra.b", "codeFlows": [{"threadFlows": [
            {"locations": [_loc("controle.go"), _loc("controle.go")]}]}]},
        # alerta sem trilha alguma
        {"ruleId": "regra.c"},
    ]}]}
    alertas, com_trilha, entre, regras = contar_trilhas(sarif)
    checa("alertas", alertas, 3)
    checa("com trilha", com_trilha, 2)
    checa("com trilha ENTRE arquivos", entre, 1)
    checa("regras", regras, ["regra.a", "regra.b", "regra.c"])
    checa("SARIF vazio", contar_trilhas({"runs": []}), (0, 0, 0, []))

    print("-- ganho: só detecção nova nos casos do gabarito conta --")
    def _bloco(antes, depois):
        return {"ce": {"executou": True, "veredito_fase1": antes},
                "pro": {"executou": True, "veredito_fase1": depois}}

    checa("CE perdeu, Pro achou -> ganho",
          _ganho(_bloco("NAO_DETECTADO", "DETECTADO")), "ganho")
    checa("os dois perderam -> igual",
          _ganho(_bloco("NAO_DETECTADO", "NAO_DETECTADO")), "igual")
    checa("os dois acharam -> igual",
          _ganho(_bloco("DETECTADO", "DETECTADO")), "igual")
    checa("CE achou, Pro perdeu -> perda",
          _ganho(_bloco("DETECTADO", "NAO_DETECTADO")), "perda")
    checa("modo que não executou -> sem_dado",
          _ganho({"ce": {"executou": True, "veredito_fase1": "NAO_DETECTADO"},
                  "pro": {"executou": False}}), "sem_dado")

    checa("nenhuma deteccao nova -> inconclusivo",
          classificar_gabarito([{"ganho": "igual"}, {"ganho": "igual"}]),
          (INCONCLUSIVO, "nenhuma_deteccao_nova_em_2_casos"))
    checa("uma deteccao nova -> viavel",
          classificar_gabarito([{"ganho": "ganho"}, {"ganho": "igual"}]),
          (VIAVEL, "deteccao_nova_em_1_de_2"))
    checa("timeout NAO conta como ausencia de deteccao",
          classificar_gabarito([{"ganho": "sem_dado"}]),
          (INDISPONIVEL, "nenhum_caso_medido"))

    print("-- recusa de alvo inválido --")
    tmp = tempfile.mkdtemp(prefix="portao_pro_selftest_")
    try:
        with open(os.path.join(tmp, "unico.go"), "w") as f:
            f.write("package p\n")
        try:
            validar_alvo(tmp)
            checa("um arquivo recusado", "não levantou", "AlvoInvalidoError")
        except AlvoInvalidoError:
            checa("um arquivo recusado", "AlvoInvalidoError",
                  "AlvoInvalidoError")
        with open(os.path.join(tmp, "outro.go"), "w") as f:
            f.write("package p\n")
        checa("dois arquivos aceitos", len(validar_alvo(tmp)), 2)
    finally:
        apagar(tmp)

    print("-- projeto sintético --")
    tmp = tempfile.mkdtemp(prefix="portao_pro_selftest_")
    try:
        alvo = escrever_sintetico(os.path.join(tmp, "portao"))
        nomes = {os.path.basename(p) for p in validar_alvo(alvo)}
        checa("fonte e sumidouro em arquivos separados, mais o controle",
              nomes, {"handler.go", "fetch.go", "controle.go"})
        fonte = open(os.path.join(alvo, "handler.go"), encoding="utf-8").read()
        sumidouro = open(os.path.join(alvo, "fetch.go"), encoding="utf-8").read()
        checa("o arquivo da fonte não contém o sumidouro",
              "http.Get" in fonte, False)
        checa("o arquivo do sumidouro não contém a fonte",
              "r.URL" in sumidouro, False)
    finally:
        apagar(tmp)

    print(f"\n  {'PASSOU (OK)' if not falhas else 'FALHOU: ' + ', '.join(falhas)}")
    return 0 if not falhas else 1


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--selftest", action="store_true",
                    help="valida a lógica sem rede e sai")
    ap.add_argument("--etapa",
                    choices=["sintetica", "real", "gabarito", "ambas"],
                    default="ambas",
                    help="`gabarito` mede o critério CORRETO: o motor novo "
                         "detecta os casos que o CE perdeu? As outras duas "
                         "medem a capacidade do motor, que é pergunta "
                         "diferente.")
    ap.add_argument("--casos-por-cwe", type=int, default=5,
                    help="repositórios por CWE na etapa real (padrão: 5)")
    ap.add_argument("--manter", action="store_true",
                    help="não apaga os checkouts nem o projeto sintético")
    args = ap.parse_args()

    if args.selftest:
        return selftest()

    etapas = ["sintetica", "real"] if args.etapa == "ambas" else [args.etapa]
    relatorio = executar(etapas, args.casos_por_cwe, args.manter)
    return 0 if relatorio["classificacao"] == VIAVEL else 1


if __name__ == "__main__":
    sys.exit(main())
