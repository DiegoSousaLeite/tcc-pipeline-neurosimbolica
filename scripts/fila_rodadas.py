"""
fila_rodadas.py — executa rodadas em sequência, desatendido, trocando de modelo.

Por que existe
--------------
Depois da Rodada 4 sobraram duas perguntas confundidas uma na outra:

- o recall de 1,29 % é efeito do **enquadramento do prompt** (pedir para validar
  um alerta que não existe) ou da **capacidade do modelo**?

Trocar as duas coisas de uma vez não responde nenhuma. Esta fila roda as duas
rodadas que isolam cada eixo, cada uma pareada com a anterior pelos mesmos
`ID_Caso`, o mesmo cache simbólico e a mesma semente:

| rodada | modelo | enquadramento | isola |
|---|---|---|---|
| 4 (feita) | qwen2.5-coder:7b | alerta | — |
| **5** | qwen2.5-coder:7b | **direto** | o ENQUADRAMENTO (modelo constante) |
| **6** | **gemma2:9b** | direto | o MODELO (enquadramento constante) |

A quarta célula (gemma × alerta) não é necessária: cada eixo já tem uma
comparação pareada que o isola sozinho.

Entre rodadas o modelo anterior é descarregado e o próximo é aquecido, porque
dois modelos residentes não cabem nos 8 GB da RX 7600 desta máquina.

USO
    python scripts/fila_rodadas.py                # roda a fila inteira
    python scripts/fila_rodadas.py --so-listar    # mostra o plano e sai

Destacado do terminal (PowerShell):
    Start-Process -WindowStyle Hidden python `
      -ArgumentList 'scripts/fila_rodadas.py' -WorkingDirectory (Get-Location)
"""
import argparse
import logging
import os
import subprocess
import sys
import time
from datetime import timedelta

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

from scripts.gatilho_rodada_triagem import (  # noqa: E402
    aquecer_modelo,
    descarregar_modelo,
    esperar_maquina,
)

LOG_PADRAO = os.path.join(BASE, "results", "fila-rodadas.log")
LOCK = os.path.join(BASE, "results", "fila-rodadas.lock")

# (run_id, modelo, [tipos de prompt], o que a rodada isola)
FILA = [
    ("rodada-5-direto", "ollama:qwen2.5-coder:7b",
     ["baseline_direto", "especialista_direto"],
     "ENQUADRAMENTO — mesmo modelo da Rodada 4, pergunta pelo código"),
    ("rodada-6-gemma", "ollama:gemma2:9b",
     ["baseline_direto", "especialista_direto"],
     "MODELO — mesmo enquadramento da Rodada 5, modelo maior"),
]

log = logging.getLogger("fila")


def rodar(run_id, modelo, prompts) -> int:
    cmd = [sys.executable, "run_pipeline.py", "--tudo",
           "--modo-montagem", "triagem", "--modelo", modelo]
    for p in prompts:
        cmd += ["--prompt", p]
    cmd += ["--run-id", run_id]
    log.info("[%s] %s", run_id, " ".join(cmd))
    t0 = time.time()
    r = subprocess.run(cmd, cwd=BASE)
    log.info("[%s] código %d em %s", run_id, r.returncode,
             timedelta(seconds=int(time.time() - t0)))
    return r.returncode


def metricas(run_id):
    r = subprocess.run(
        [sys.executable, "src/metricas.py", f"results/{run_id}",
         "--mcnemar", "--estratificar", "--latex"],
        cwd=BASE, capture_output=True, text=True)
    for linha in (r.stdout or "").splitlines():
        log.info("  | %s", linha)


def main():
    ap = argparse.ArgumentParser(description="Fila de rodadas desatendida.")
    ap.add_argument("--quiet-min", type=float, default=3.0)
    ap.add_argument("--ram-livre-gb", type=float, default=8.0)
    ap.add_argument("--intervalo", type=float, default=60.0)
    ap.add_argument("--limite-h", type=float, default=24.0)
    ap.add_argument("--so-listar", action="store_true")
    ap.add_argument("--log", default=LOG_PADRAO)
    args = ap.parse_args()

    handlers = [logging.StreamHandler(sys.stdout)]
    try:
        os.makedirs(os.path.dirname(args.log), exist_ok=True)
        handlers.insert(0, logging.FileHandler(args.log, encoding="utf-8"))
    except OSError as e:
        print(f"[aviso] sem arquivo de log: {e}", file=sys.stderr)
    logging.basicConfig(level=logging.INFO, handlers=handlers,
                        format="%(asctime)s %(levelname)-7s %(message)s",
                        datefmt="%Y-%m-%d %H:%M:%S")

    if args.so_listar:
        for run_id, modelo, prompts, isola in FILA:
            log.info("%-18s %-26s %-40s %s", run_id, modelo,
                     ",".join(prompts), isola)
        return 0

    if os.path.exists(LOCK):
        log.error("já existe uma fila rodando (lock %s). Saindo.", LOCK)
        return 1
    os.makedirs(os.path.dirname(LOCK), exist_ok=True)
    with open(LOCK, "w", encoding="utf-8") as f:
        f.write(str(os.getpid()))

    anterior = None
    try:
        log.info("=" * 70)
        log.info("FILA DE RODADAS — %d rodadas", len(FILA))
        for run_id, modelo, prompts, isola in FILA:
            log.info("  %s | %s | %s", run_id, modelo, isola)
        log.info("=" * 70)

        for run_id, modelo, prompts, isola in FILA:
            log.info("")
            log.info(">>> %s — isola: %s", run_id, isola)

            # A DESCARGA VEM ANTES DA ESPERA, e a ordem não é estética.
            #
            # O modelo da rodada anterior é peso morto assim que ela termina: o
            # `llama-server` segurava 12,5 GB de working set ao fim da Rodada 5.
            # Se a espera viesse primeiro, ela ficaria aguardando uma RAM que só
            # a descarga libera, e a descarga só aconteceria depois da espera —
            # impasse circular, e a fila dormiria as 24 h do limite sem sair do
            # lugar. Foi exatamente o que aconteceu em 2026-09-16 12:19.
            if anterior and anterior != modelo:
                descarregar_modelo(anterior)

            if not esperar_maquina(args.quiet_min, args.intervalo,
                                   args.ram_livre_gb, args.limite_h):
                log.error("máquina não liberou; parando a fila em %s.", run_id)
                return 2
            if not aquecer_modelo(modelo):
                log.error("não consegui aquecer %s; parando a fila.", modelo)
                return 3
            anterior = modelo

            if rodar(run_id, modelo, prompts) != 0:
                log.error("%s falhou. O checkpoint preserva o que rodou; "
                          "reexecute com o mesmo --run-id.", run_id)
                return 4
            metricas(run_id)

        if anterior:
            descarregar_modelo(anterior)
        log.info("")
        log.info("FILA CONCLUÍDA. %s", ", ".join(r for r, _, _, _ in FILA))
        return 0
    finally:
        try:
            os.remove(LOCK)
        except OSError:
            pass


if __name__ == "__main__":
    sys.exit(main())
