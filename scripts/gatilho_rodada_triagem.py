"""
gatilho_rodada_triagem.py — espera a máquina liberar e dispara a rodada de triagem.

Por que existe
--------------
A rodada de triagem no provedor local leva ~7,3 h (medido: 8,23 s/chamada,
tarefa 5.3 da change `braco-triagem-classe-positiva`). Enquanto a esteira
simbólica de outra frente estiver rodando, os dois disputam RAM — Semgrep é
guloso e o `llama-server`/Ollama também. Rodar junto degrada os dois e pode
derrubar um deles no meio.

Este script fica esperando, em segundo plano, a máquina ficar quieta, e só então
executa. Ele existe para que ninguém precise ficar olhando o terminal.

O que conta como "máquina ocupada"
----------------------------------
Qualquer processo cuja linha de comando case com `PADROES_CONCORRENTES` —
Semgrep em qualquer das suas formas (`semgrep`, `pysemgrep`, `osemgrep`,
`semgrep-core*`) e os scripts pesados do projeto (`run_pipeline.py`,
`verificar_pro.py`, `tp_reconstruct.py`, `colheita*.py`).

**A janela de silêncio não é opcional.** A Fase 1 invoca o Semgrep uma vez por
caso: entre dois casos não há processo `semgrep` algum por alguns segundos. Um
gatilho que disparasse na primeira amostra vazia cairia exatamente nessa fresta e
subiria o modelo no meio da esteira alheia. Por isso a condição é *nenhum
concorrente por `--quiet-min` minutos seguidos*, e uma única amostra suja zera o
relógio.

Uso
---
    # Padrão: espera 10 min de silêncio, roda piloto + rodada completa
    python scripts/gatilho_rodada_triagem.py

    # Só confere o estado da máquina agora e sai (não espera, não roda)
    python scripts/gatilho_rodada_triagem.py --agora

    # Só o piloto (trilhas TP, ~3,7 h); não segue para a população inteira
    python scripts/gatilho_rodada_triagem.py --so-piloto

Destacar do terminal (sobrevive ao fim da sessão), no PowerShell:

    Start-Process -WindowStyle Hidden python `
      -ArgumentList 'scripts/gatilho_rodada_triagem.py' `
      -WorkingDirectory (Get-Location)

O progresso vai para `results/gatilho-triagem.log`; acompanhe com
`Get-Content results/gatilho-triagem.log -Wait`.

O portão da tarefa 5.5
----------------------
Entre o piloto e a rodada completa o script compara o acerto do LLM entre as duas
procedências. Se divergirem mais que `--limiar-portao`, ele **para** e diz por
quê: é a instrução da tarefa 5.5 — se o controle acusar artefato, o número da
triagem não pode ser reportado como está, e gastar mais 3,6 h de parede antes de
investigar a causa é desperdício. `--sem-portao` desliga, e a decisão volta a ser
de quem lê o log.
"""
import argparse
import json
import logging
import os
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

from src.metricas import carregar, comparar_procedencias  # noqa: E402

LOG_PADRAO = os.path.join(BASE, "results", "gatilho-triagem.log")
LOCK = os.path.join(BASE, "results", "gatilho-triagem.lock")
RUN_ID = "rodada-4-triagem"
# Rodada separada, de propósito: a etapa simbólica roda em modo FILTRO com
# `--sem-llm`, e gravá-la em RUN_ID misturaria modos no mesmo diretório — que é
# exatamente o que a pipeline recusa fazer.
RUN_ID_SIMBOLICO = "pre-fase1-simbolica"
MODELO = "ollama:qwen2.5-coder:7b"

# Linhas de comando que significam "a máquina está ocupada com trabalho pesado".
# Case-insensitive, casadas como substring.
PADROES_CONCORRENTES = (
    "semgrep",
    "run_pipeline.py",
    "verificar_pro.py",
    "tp_reconstruct.py",
    "colheita",
)

# Shells que apenas HOSPEDAM um comando não contam. A linha de comando de um
# `bash -c "...python scripts/verificar_pro.py..."` casa com os padrões acima,
# mas quem consome RAM é o processo filho — que é detectado por conta própria.
# Sem este filtro, um shell do harness que sobrevivesse a um comando já
# terminado deixaria o gatilho ocupado para sempre.
PADROES_HOSPEDEIROS = (
    "shell-snapshots",
    "claude",
)

log = logging.getLogger("gatilho")


# ---------------------------------------------------------------------------
# Leitura do estado da máquina
# ---------------------------------------------------------------------------

def _powershell(comando: str) -> str:
    """Roda um comando PowerShell e devolve o stdout (vazio em qualquer falha).

    Falha de leitura NÃO é lida como "máquina livre": quem chama trata o vazio
    como indeterminado e continua esperando. Um gatilho que disparasse porque
    não conseguiu enxergar os processos seria pior que um que nunca dispara.
    """
    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", comando],
            capture_output=True, text=True, timeout=60)
        return r.stdout or ""
    except (OSError, subprocess.SubprocessError):
        return ""


def processos() -> list | None:
    """`[(pid, cmdline)]` dos processos visíveis, ou None se não deu para ler."""
    saida = _powershell(
        "Get-CimInstance Win32_Process | "
        "Select-Object ProcessId,CommandLine | ConvertTo-Json -Compress")
    if not saida.strip():
        return None
    try:
        dados = json.loads(saida)
    except json.JSONDecodeError:
        return None
    if isinstance(dados, dict):
        dados = [dados]
    return [(p.get("ProcessId"), p.get("CommandLine") or "") for p in dados]


def ram_livre_gb() -> float | None:
    saida = _powershell(
        "(Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory")
    try:
        return int(saida.strip()) / 1024 / 1024
    except (ValueError, AttributeError):
        return None


def concorrentes(procs, ignorar_pids=()) -> list:
    """Processos pesados em execução, exceto os nossos.

    Exclui o próprio gatilho, a rodada que ele dispara (identificada pelo
    `--run-id` na linha de comando) e o que for passado em `ignorar_pids`.
    """
    meus = set(ignorar_pids) | {os.getpid()}
    achados = []
    for pid, cmd in procs:
        if pid in meus or RUN_ID in cmd:
            continue
        baixo = cmd.lower()
        if any(h in baixo for h in PADROES_HOSPEDEIROS):
            continue
        for padrao in PADROES_CONCORRENTES:
            if padrao in baixo:
                achados.append((pid, padrao, cmd[:120]))
                break
    return achados


def estado(ram_minima, ignorar_pids=()) -> tuple:
    """`(livre, motivo)` — `livre` é None quando não deu para determinar."""
    procs = processos()
    if procs is None:
        return None, "não consegui listar os processos"
    ocupando = concorrentes(procs, ignorar_pids)
    if ocupando:
        quais = ", ".join(sorted({p for _, p, _ in ocupando}))
        return False, f"{len(ocupando)} processo(s) concorrente(s): {quais}"
    livre = ram_livre_gb()
    if livre is None:
        return None, "não consegui ler a RAM livre"
    if livre < ram_minima:
        return False, f"RAM livre {livre:.1f} GB < {ram_minima:.1f} GB"
    return True, f"ocioso, RAM livre {livre:.1f} GB"


def esperar_maquina(quiet_min, intervalo, ram_minima, limite_h) -> bool:
    """Bloqueia até a máquina ficar quieta por `quiet_min` minutos seguidos.

    Devolve False se estourar `limite_h` sem nunca alcançar a janela.
    """
    preciso = timedelta(minutes=quiet_min)
    limite = datetime.now(timezone.utc) + timedelta(hours=limite_h)
    quieta_desde = None
    ultimo_motivo = None

    while datetime.now(timezone.utc) < limite:
        livre, motivo = estado(ram_minima)
        if livre:
            if quieta_desde is None:
                quieta_desde = datetime.now(timezone.utc)
                log.info("máquina ficou ociosa (%s); começando a contar os "
                         "%d min de silêncio.", motivo, quiet_min)
            decorrido = datetime.now(timezone.utc) - quieta_desde
            if decorrido >= preciso:
                log.info("silêncio de %s confirmado. Liberado.", decorrido)
                return True
        else:
            # Indeterminado (None) também zera: na dúvida, continua esperando.
            if quieta_desde is not None:
                log.info("relógio zerado: %s", motivo)
            elif motivo != ultimo_motivo:
                log.info("aguardando: %s", motivo)
            quieta_desde = None
            ultimo_motivo = motivo
        time.sleep(intervalo)

    log.error("limite de %.1f h esperando a máquina liberar. Desistindo.",
              limite_h)
    return False


# ---------------------------------------------------------------------------
# Provedor local
# ---------------------------------------------------------------------------

def _ollama(caminho: str, corpo: dict, timeout: int) -> bool:
    import urllib.error
    import urllib.request
    base = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
    req = urllib.request.Request(
        base + caminho, data=json.dumps(corpo).encode("utf-8"),
        headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            r.read()
        return True
    except (urllib.error.URLError, OSError, TimeoutError) as e:
        log.error("Ollama em %s%s: %s", base, caminho, e)
        return False


def _tag(modelo=None) -> str:
    return (modelo or MODELO).split(":", 1)[1]


def descarregar_modelo(modelo=None) -> bool:
    """Tira o modelo da memória antes da etapa simbólica.

    Semgrep e o modelo local disputam RAM. A etapa simbólica pode ter que
    reexecutar o Semgrep sobre os casos que faltarem no cache, e fazer isso com
    7 B de pesos residentes é o cenário que este gatilho existe para evitar.
    `keep_alive: 0` devolve a memória imediatamente.
    """
    tag = _tag(modelo)
    ok = _ollama("/api/generate", {"model": tag, "keep_alive": 0}, 120)
    log.info("modelo %s descarregado: %s", tag, "ok" if ok else "FALHOU")
    return ok


def aquecer_modelo(modelo=None) -> bool:
    """Sobe o modelo antes do primeiro caso e o mantém residente.

    Sem isto, a primeira chamada paga o carregamento e a estimativa de parede de
    5.3 — medida com o modelo já carregado — não vale.
    """
    tag = _tag(modelo)
    ok = _ollama("/api/generate",
                 {"model": tag, "prompt": "ping", "stream": False,
                  "keep_alive": "24h"}, 300)
    if ok:
        log.info("modelo %s aquecido e residente (keep_alive 24h).", tag)
    return ok


# ---------------------------------------------------------------------------
# Execução
# ---------------------------------------------------------------------------

def rodar(etapa: str, escopo: str) -> int:
    """Uma etapa da esteira. Devolve o código de saída."""
    cmd = [sys.executable, "run_pipeline.py", escopo,
           "--modo-montagem", "triagem",
           "--modelo", MODELO,
           "--prompt", "baseline", "--prompt", "especialista",
           "--run-id", RUN_ID]
    log.info("[%s] %s", etapa, " ".join(cmd))
    t0 = time.time()
    r = subprocess.run(cmd, cwd=BASE)
    log.info("[%s] terminou com código %d em %s", etapa, r.returncode,
             timedelta(seconds=int(time.time() - t0)))
    return r.returncode


def popular_fase1() -> int:
    """Tarefa 5b.1 — garante a Fase 1 em cache para a população inteira.

    Roda em modo filtro com `--sem-llm`, que é o recorte barato: se tudo já
    estiver no cache simbólico, termina em segundos; se faltar, é aqui que o
    Semgrep roda — e aqui é o único lugar onde ele pode rodar sem disputar RAM
    com o modelo, porque o modelo ainda não subiu.
    """
    cmd = [sys.executable, "run_pipeline.py", "--tudo", "--sem-llm",
           "--modelo", MODELO, "--prompt", "especialista",
           "--run-id", RUN_ID_SIMBOLICO]
    log.info("[FASE1] %s", " ".join(cmd))
    t0 = time.time()
    r = subprocess.run(cmd, cwd=BASE)
    log.info("[FASE1] terminou com código %d em %s", r.returncode,
             timedelta(seconds=int(time.time() - t0)))
    return r.returncode


def metricas() -> str:
    cmd = [sys.executable, "src/metricas.py", f"results/{RUN_ID}",
           "--mcnemar", "--estratificar", "--latex"]
    log.info("métricas: %s", " ".join(cmd))
    r = subprocess.run(cmd, cwd=BASE, capture_output=True, text=True)
    saida = r.stdout or ""
    for linha in saida.splitlines():
        log.info("  | %s", linha)
    return saida


def portao_do_controle(limiar: float) -> tuple:
    """Portão da tarefa 5.5: o controle acusa artefato?

    Devolve `(passou, explicação)`.

    **O portão é direcional, e isso não é detalhe.** A spec nomeia um sentido:
    "se o LLM acertar sistematicamente mais nos INJETADOS do que nos detectados,
    a diferença não vem do código — vem de alguma propriedade da montagem". É
    esse caso que torna o número da triagem indefensável, porque infla o
    resultado por artefato.

    O sentido contrário — o modelo indo PIOR nos injetados — não é esse artefato.
    É consistente com a explicação simples de que o Semgrep detecta justamente as
    vulnerabilidades mais fáceis, e as que ele perde são mais difíceis para
    qualquer um. Isso é resultado, não contaminação, e bloquear a rodada por
    causa dele gastaria o portão na direção errada. Continua sendo reportado em
    alto e bom som, porque é a ameaça da "natureza das localizações" (§4b.4 do
    mapa do LaTeX) se manifestando — mas não interrompe.

    Grupo de controle vazio, sim, fecha: sem controle não há o que concluir, e
    seguir seria gastar as horas que a tarefa manda não gastar.
    """
    bracos = carregar(os.path.join(BASE, "results", RUN_ID))
    piores = []
    for br in bracos:
        comp = comparar_procedencias(br.linhas)
        alerta = comp.get("alerta")
        gabarito = comp.get("gabarito")
        if not alerta or not alerta["n"]:
            return False, (f"[{br.rotulo}] grupo de controle VAZIO: nenhum "
                           f"positivo detectado pelo Semgrep chegou ao LLM. "
                           f"Sem controle não dá para afirmar que a injeção não "
                           f"criou artefato.")
        if not gabarito or not gabarito["n"]:
            return False, (f"[{br.rotulo}] nenhum candidato injetado com "
                           f"veredito válido: não há braço de triagem a "
                           f"controlar.")
        # Positivo = injetado indo MELHOR que o detectado. É o sinal de artefato.
        piores.append((gabarito["acerto"] - alerta["acerto"], br.rotulo,
                       alerta, gabarito))

    d, rotulo, alerta, gabarito = max(piores)
    detalhe = (f"[{rotulo}] acerto alerta={alerta['acerto']:.4f} "
               f"(n={alerta['n']}) vs gabarito={gabarito['acerto']:.4f} "
               f"(n={gabarito['n']}) -> gabarito - alerta = {d:+.4f}")
    if d > limiar:
        return False, (f"{detalhe}, acima do limiar {limiar:.2f}. O LLM acerta "
                       f"sistematicamente MAIS nos injetados: o controle acusa "
                       f"artefato e o número da triagem NÃO pode ser reportado "
                       f"como está (tarefa 5.5).")

    menor = min(piores)[0]
    if menor < -limiar:
        log.warning("o LLM acerta MUITO MENOS nos injetados (diferença "
                    "%+.4f). Não é o artefato que o portão barra — é "
                    "consistente com o Semgrep detectar as vulnerabilidades "
                    "mais fáceis —, mas é a ameaça da 'natureza das "
                    "localizações' aparecendo, e precisa ir para a análise da "
                    "rodada e para o mapa do LaTeX.", menor)
    return True, f"{detalhe}, dentro do limiar {limiar:.2f}."


# ---------------------------------------------------------------------------
# Trava de instância única
# ---------------------------------------------------------------------------

def tomar_lock() -> bool:
    os.makedirs(os.path.dirname(LOCK), exist_ok=True)
    if os.path.exists(LOCK):
        try:
            with open(LOCK, encoding="utf-8") as f:
                pid = int(f.read().strip())
        except (OSError, ValueError):
            pid = None
        if pid is not None:
            procs = processos()
            if procs is not None and any(p == pid for p, _ in procs):
                log.error("já existe um gatilho rodando (PID %d). Saindo.", pid)
                return False
        log.info("lock órfão encontrado; assumindo.")
    with open(LOCK, "w", encoding="utf-8") as f:
        f.write(str(os.getpid()))
    return True


def soltar_lock():
    try:
        os.remove(LOCK)
    except OSError:
        pass


# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(
        description="Espera a máquina liberar e dispara a rodada de triagem.")
    ap.add_argument("--quiet-min", type=float, default=10.0, metavar="MIN",
                    help="Minutos SEGUIDOS sem processo concorrente antes de "
                         "disparar. Padrão: 10. A Fase 1 chama o Semgrep uma "
                         "vez por caso, então uma janela curta demais dispara "
                         "no intervalo entre dois casos.")
    ap.add_argument("--ram-livre-gb", type=float, default=8.0, metavar="GB",
                    help="RAM livre mínima para considerar a máquina liberada. "
                         "Padrão: 8.")
    ap.add_argument("--intervalo", type=float, default=60.0, metavar="SEG",
                    help="Intervalo entre sondagens. Padrão: 60 s.")
    ap.add_argument("--limite-h", type=float, default=72.0, metavar="H",
                    help="Desiste depois de tantas horas esperando. Padrão: 72.")
    ap.add_argument("--so-piloto", action="store_true",
                    help="Roda só o piloto (--tp-only) e para. Não segue para "
                         "a população inteira.")
    ap.add_argument("--sem-portao", action="store_true",
                    help="Segue para a rodada completa mesmo que o controle "
                         "acuse divergência entre procedências (tarefa 5.5).")
    ap.add_argument("--limiar-portao", type=float, default=0.25, metavar="D",
                    help="Diferença absoluta de acerto entre procedências que "
                         "faz o portão fechar. Padrão: 0.25.")
    ap.add_argument("--agora", action="store_true",
                    help="Só relata o estado da máquina e sai.")
    ap.add_argument("--log", default=LOG_PADRAO, metavar="ARQUIVO")
    args = ap.parse_args()

    # O arquivo de log é conveniência, não requisito: um `--log` sem diretório,
    # apontando para um caminho não-criável ou para um dispositivo (`/dev/null`)
    # não pode derrubar o gatilho antes de ele sequer olhar a máquina.
    handlers = [logging.StreamHandler(sys.stdout)]
    try:
        pasta = os.path.dirname(args.log)
        if pasta:
            os.makedirs(pasta, exist_ok=True)
        handlers.insert(0, logging.FileHandler(args.log, encoding="utf-8"))
    except OSError as e:
        print(f"[aviso] sem arquivo de log ({args.log}): {e}", file=sys.stderr)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-7s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=handlers)

    if args.agora:
        livre, motivo = estado(args.ram_livre_gb)
        rotulo = {True: "LIVRE", False: "OCUPADA", None: "INDETERMINADA"}[livre]
        log.info("estado agora: %s — %s", rotulo, motivo)
        procs = processos() or []
        for pid, padrao, cmd in concorrentes(procs):
            log.info("  concorrente: pid=%s padrão=%s | %s", pid, padrao, cmd)
        return 0

    if not tomar_lock():
        return 1
    try:
        log.info("=" * 70)
        log.info("GATILHO DA RODADA DE TRIAGEM")
        log.info("  run-id     : %s", RUN_ID)
        log.info("  modelo     : %s", MODELO)
        log.info("  silêncio   : %.0f min | RAM livre >= %.1f GB | sonda a cada "
                 "%.0f s", args.quiet_min, args.ram_livre_gb, args.intervalo)
        log.info("  escopo     : Fase 1 em cache (sem LLM), %s",
                 "só piloto (--tp-only)" if args.so_piloto
                 else "piloto (--tp-only) e depois população inteira (--tudo)")
        log.info("  portão 5.5 : %s", "DESLIGADO" if args.sem_portao
                 else f"limiar {args.limiar_portao:.2f}")
        log.info("=" * 70)

        if not esperar_maquina(args.quiet_min, args.intervalo,
                               args.ram_livre_gb, args.limite_h):
            return 2

        # Ordem obrigatória (5b.1): simbólico com o modelo FORA da memória,
        # depois o modelo sobe e nada mais chama o Semgrep.
        descarregar_modelo()
        if popular_fase1() != 0:
            log.error("a etapa simbólica não terminou bem; parando antes de "
                      "subir o modelo.")
            return 7

        if not aquecer_modelo():
            return 3

        if rodar("PILOTO", "--tp-only") != 0:
            log.error("o piloto não terminou bem; não sigo para a rodada "
                      "completa. O checkpoint preserva o que já rodou: "
                      "reexecute com o mesmo --run-id.")
            return 4
        metricas()

        if args.so_piloto:
            log.info("--so-piloto: parando aqui, como pedido.")
            return 0

        passou, explicacao = portao_do_controle(args.limiar_portao)
        log.info("PORTÃO 5.5: %s", explicacao)
        if not passou and not args.sem_portao:
            log.warning("PARANDO antes da rodada completa. Registre a decisão "
                        "em docs/MAPA-TCC-O-QUE-REESCREVER.md e investigue a "
                        "causa antes de gastar as horas restantes. Para seguir "
                        "assim mesmo: --sem-portao.")
            return 5
        if not passou:
            log.warning("--sem-portao: seguindo apesar do controle.")

        # A máquina pode ter sido retomada durante as horas do piloto.
        livre, motivo = estado(args.ram_livre_gb)
        if livre is False:
            log.warning("a máquina voltou a ficar ocupada (%s); esperando de "
                        "novo antes da rodada completa.", motivo)
            if not esperar_maquina(args.quiet_min, args.intervalo,
                                   args.ram_livre_gb, args.limite_h):
                return 2

        if rodar("COMPLETA", "--tudo") != 0:
            log.error("a rodada completa não terminou bem. O checkpoint "
                      "preserva o que já rodou.")
            return 6
        metricas()
        log.info("FIM. Resultados em results/%s/", RUN_ID)
        return 0
    finally:
        soltar_lock()


if __name__ == "__main__":
    sys.exit(main())
