#!/usr/bin/env bash
# Rodada 7 (change ficha-por-regra-semgrep): quatro sub-rodadas locais em
# sequência, uma por (modo, modelo), para nunca alternar modelo no Ollama caso
# a caso. Cada uma é retomável: rodar de novo com o mesmo --run-id continua de
# onde parou (checkpoint por ID_Caso, Modelo_LLM, Tipo_Prompt).
set -u
cd "$(dirname "$0")/.."
LOG=results/rodada-7.log
mkdir -p results

rodar() {
  local run_id=$1; shift
  for tentativa in 1 2 3; do
    echo "[$(date '+%F %T')] INICIO $run_id (tentativa $tentativa)" >> "$LOG"
    python run_pipeline.py --tudo --run-id "$run_id" "$@" >> "results/$run_id.log" 2>&1
    local rc=$?
    echo "[$(date '+%F %T')] FIM $run_id rc=$rc" >> "$LOG"
    [ $rc -eq 0 ] && return 0
    sleep 60
  done
  echo "[$(date '+%F %T')] DESISTIU $run_id" >> "$LOG"
  return 1
}

rodar rodada-7-filtro-qwen --modelo ollama:qwen2.5-coder:7b \
  --prompt especialista --prompt especialista_v2
rodar rodada-7-triagem-qwen --modo-montagem triagem --modelo ollama:qwen2.5-coder:7b \
  --prompt especialista_direto --prompt especialista_direto_v2
rodar rodada-7-filtro-gemma --modelo ollama:gemma2:9b \
  --prompt baseline --prompt especialista --prompt especialista_v2
rodar rodada-7-triagem-gemma --modo-montagem triagem --modelo ollama:gemma2:9b \
  --prompt especialista_direto --prompt especialista_direto_v2
echo "[$(date '+%F %T')] RODADA 7 CONCLUIDA" >> "$LOG"
