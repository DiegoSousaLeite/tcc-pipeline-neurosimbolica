#!/usr/bin/env bash
# Rodada 7 (change ficha-por-regra-semgrep): nove braços locais, UM POR VEZ.
#
# Cada invocação roda um único (modo, modelo, prompt) sobre a população inteira
# antes de passar ao próximo. Os braços de um mesmo modelo ficam juntos, para o
# Ollama não trocar de modelo no meio. Braços do mesmo (modo, modelo) dividem o
# run_id, e por isso o mesmo diretório e o mesmo manifesto.
#
# Feito para não se perder se for interrompido:
# - retomável: rodar de novo continua do último caso gravado (checkpoint por
#   ID_Caso, Modelo_LLM, Tipo_Prompt), e o CSV é gravado linha a linha;
# - braço concluído ganha o marcador results/<run_id>/.concluido-<prompt> e não
#   roda de novo;
# - trava com PID impede duas instâncias ao mesmo tempo;
# - falha repetida não desiste: espera 2 min e tenta de novo, até 50 vezes.
#
# Uso: bash scripts/rodada7.sh   (de novo, se parar: continua de onde estava)
set -u
cd "$(dirname "$0")/.."
LOG=results/rodada-7.log
TRAVA=results/rodada-7.pid
FIM=results/rodada-7.concluida
mkdir -p results

if [ -f "$TRAVA" ] && kill -0 "$(cat "$TRAVA")" 2>/dev/null; then
  echo "[$(date '+%F %T')] já em execução (pid $(cat "$TRAVA")); saindo" >> "$LOG"
  exit 0
fi
echo $$ > "$TRAVA"
trap 'rm -f "$TRAVA"' EXIT

# braco <run_id> <modelo> <prompt> [opções extras]
braco() {
  local run_id=$1 modelo=$2 prompt=$3; shift 3
  local marca="results/$run_id/.concluido-$prompt"
  [ -f "$marca" ] && return 0
  for tentativa in $(seq 1 50); do
    echo "[$(date '+%F %T')] INICIO $run_id $prompt (tentativa $tentativa)" >> "$LOG"
    python -u run_pipeline.py --tudo --run-id "$run_id" --modelo "$modelo" \
      --prompt "$prompt" "$@" >> "results/$run_id.log" 2>&1
    local rc=$?
    echo "[$(date '+%F %T')] FIM $run_id $prompt rc=$rc" >> "$LOG"
    if [ $rc -eq 0 ]; then
      mkdir -p "results/$run_id"
      touch "$marca"
      return 0
    fi
    sleep 120
  done
  echo "[$(date '+%F %T')] DESISTIU $run_id $prompt" >> "$LOG"
  return 1
}

QWEN=ollama:qwen2.5-coder:7b
GEMMA=ollama:gemma2:9b
TRIAGEM=(--modo-montagem triagem)

braco rodada-7-filtro-qwen   $QWEN  especialista                          || exit 1
braco rodada-7-filtro-qwen   $QWEN  especialista_v2                       || exit 1
braco rodada-7-triagem-qwen  $QWEN  especialista_direto    "${TRIAGEM[@]}" || exit 1
braco rodada-7-triagem-qwen  $QWEN  especialista_direto_v2 "${TRIAGEM[@]}" || exit 1
braco rodada-7-filtro-gemma  $GEMMA baseline                              || exit 1
braco rodada-7-filtro-gemma  $GEMMA especialista                          || exit 1
braco rodada-7-filtro-gemma  $GEMMA especialista_v2                       || exit 1
braco rodada-7-triagem-gemma $GEMMA especialista_direto    "${TRIAGEM[@]}" || exit 1
braco rodada-7-triagem-gemma $GEMMA especialista_direto_v2 "${TRIAGEM[@]}" || exit 1
touch "$FIM"
echo "[$(date '+%F %T')] RODADA 7 CONCLUIDA" >> "$LOG"
