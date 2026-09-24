#!/usr/bin/env bash
# Reexecução das Rodadas 4, 5 e 6 — as MESMAS rodadas, não testes novos.
#
# Os CSVs caso a caso das três rodadas foram apagados de results/ antes de
# 2026-09-22; restaram só os números publicados em docs/ANALISE-RODADA-{4,5,6}.md.
# Este script as roda de novo com a configuração das originais (mesmo modelo,
# templates, catálogo por CWE, população, semente 42, temperatura 0) e com os
# MESMOS run_ids, para que a pasta de cada rodada volte a existir com o nome que
# a análise cita.
#
# Um braço por vez; braços do mesmo modelo juntos. Retomável (checkpoint por
# caso). Braço concluído: marcador .concluido-<prompt>, cópia para
# resultados_parte2/<run_id>/ e commit SÓ dessa pasta.
#
# Uso: bash scripts/reexecutar_rodadas_4_5_6.sh   (de novo, se parar)
set -u
cd "$(dirname "$0")/.."
LOG=results/reexecucao-4-5-6.log
TRAVA=results/reexecucao-4-5-6.pid
FIM=results/reexecucao-4-5-6.concluida
mkdir -p results resultados_parte2

if [ -f "$TRAVA" ] && kill -0 "$(cat "$TRAVA")" 2>/dev/null; then
  echo "[$(date '+%F %T')] já em execução (pid $(cat "$TRAVA")); saindo" >> "$LOG"
  exit 0
fi
echo $$ > "$TRAVA"
trap 'rm -f "$TRAVA"' EXIT

# Nunca usar o catálogo por regra aqui: as originais rodaram com o por CWE.
HASH_CWE=e5db7d4008428a0f31404645380ad28c7a95255185e4e0cfb6a37ebac56c2676
if [ "$(sha256sum data/catalogo_cwe.json | cut -d' ' -f1)" != "$HASH_CWE" ]; then
  echo "[$(date '+%F %T')] ABORTADO: data/catalogo_cwe.json não é o catálogo por CWE das Rodadas 1-6" >> "$LOG"
  exit 1
fi

salvar() {
  local run_id=$1 prompt=$2
  mkdir -p "resultados_parte2/$run_id"
  cp results/"$run_id"/*.csv results/"$run_id"/manifesto.json "resultados_parte2/$run_id/" 2>/dev/null
  cp "results/$run_id/manifesto.json" "resultados_parte2/$run_id/manifesto-$prompt.json" 2>/dev/null
  git add "resultados_parte2/$run_id" >> "$LOG" 2>&1
  git commit -q -m "chore: reexecução de $run_id, braço $prompt

Mesma rodada citada em docs/ANALISE-RODADA-*.md, reexecutada para recuperar
os CSVs caso a caso apagados de results/. Não é experimento novo.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>" -- "resultados_parte2/$run_id" >> "$LOG" 2>&1
}

# braco <run_id> <modelo> <prompt>   (todas em modo triagem, como as originais)
braco() {
  local run_id=$1 modelo=$2 prompt=$3
  local marca="results/$run_id/.concluido-$prompt"
  [ -f "$marca" ] && return 0
  for tentativa in $(seq 1 50); do
    echo "[$(date '+%F %T')] INICIO $run_id $prompt (tentativa $tentativa)" >> "$LOG"
    python -u run_pipeline.py --tudo --modo-montagem triagem --run-id "$run_id" \
      --modelo "$modelo" --prompt "$prompt" >> "results/$run_id.log" 2>&1
    local rc=$?
    echo "[$(date '+%F %T')] FIM $run_id $prompt rc=$rc" >> "$LOG"
    if [ $rc -eq 0 ]; then
      touch "$marca"
      salvar "$run_id" "$prompt"
      return 0
    fi
    sleep 120
  done
  echo "[$(date '+%F %T')] DESISTIU $run_id $prompt" >> "$LOG"
  return 1
}

QWEN=ollama:qwen2.5-coder:7b
GEMMA=ollama:gemma2:9b

braco rodada-4-triagem $QWEN  baseline            || exit 1
braco rodada-4-triagem $QWEN  especialista        || exit 1
braco rodada-5-direto  $QWEN  baseline_direto     || exit 1
braco rodada-5-direto  $QWEN  especialista_direto || exit 1
braco rodada-6-gemma   $GEMMA baseline_direto     || exit 1
braco rodada-6-gemma   $GEMMA especialista_direto || exit 1
touch "$FIM"
echo "[$(date '+%F %T')] REEXECUCAO 4-5-6 CONCLUIDA" >> "$LOG"
