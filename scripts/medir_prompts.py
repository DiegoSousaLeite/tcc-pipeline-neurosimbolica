"""
medir_prompts.py — distribuição de tamanho de prompt sobre a população.

Por que existe
--------------
O braço local roda com uma janela de contexto FIXA (`num_ctx`), e o servidor
Ollama descarta em silêncio o que não couber. Escolher esse número no chute tem
dois modos de falha, os dois ruins: apertado demais, os arquivos maiores viram
`ERROR` só no braço local e a população dele deixa de ser a mesma dos braços
comerciais — o McNemar pareado perde a premissa; folgado demais, o cache KV não
cabe nos 8 GB de VRAM e a inferência escorrega para a CPU.

Este script mede antes de decidir. Ele NÃO chama LLM, não roda Semgrep e não
toca a rede: monta os mesmos prompts que a Fase 3/4 montaria, a partir do
contexto já gravado no cache simbólico, e conta tokens pela mesma estimativa que
o provedor local usa para recusar um prompt grande demais.

A estimativa (`len(prompt)/3.5`) superestima de propósito em código: ela erra
para o lado de recusar um prompt que talvez coubesse, nunca para o de aceitar um
que será truncado sem aviso.

Uso
---
  python scripts/medir_prompts.py
  python scripts/medir_prompts.py --num-ctx 16384
  python scripts/medir_prompts.py --trilha FP
"""
import argparse
import json
import os
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from run_pipeline import (  # noqa: E402
    TP_PAIRS_OURO,
    TP_PAIRS_PRATA,
    TRILHAS,
    _cwe_lookup,
    construir_casos_fp,
    construir_casos_tp,
    construir_casos_tp_dataset,
)
from src.cache_simbolico import CacheSimbolico  # noqa: E402
from src.catalogo import catalogo_padrao  # noqa: E402
from src.config import DATASET_PATH  # noqa: E402
from src.prompts import TIPOS, montar_prompt  # noqa: E402
from src.provedores.ollama import (  # noqa: E402
    NUM_CTX_PADRAO,
    NUM_PREDICT,
    ProvedorOllama,
)


def percentil(valores, p):
    """p-ésimo percentil pelo método do vizinho mais próximo.

    Sem interpolação de propósito: o número serve para escolher um `num_ctx`, e
    um valor observado é mais defensável no texto que uma média entre dois.
    """
    if not valores:
        return 0
    ordenados = sorted(valores)
    i = min(len(ordenados) - 1, int(round(p / 100 * (len(ordenados) - 1))))
    return ordenados[i]


def medir(casos, cache, catalogo, provedor):
    """`{tipo: [tokens estimados]}` mais a contagem de casos sem contexto."""
    por_tipo = {tipo: [] for tipo in TIPOS}
    sem_cache = nao_detectado = 0

    for caso in casos:
        payload = cache.ler(caso["repo_name"], caso["commit"], caso["arquivo"],
                            caso["cwe"])
        if payload is None:
            sem_cache += 1
            continue
        contexto = payload.get("contexto_hidratado") or ""
        if payload.get("status_semgrep") != "DETECTADO" or not contexto:
            # Sem alerta do Semgrep não há chamada de LLM: o caso não entra na
            # distribuição porque nunca vira prompt.
            nao_detectado += 1
            continue
        ficha = catalogo.ficha(caso["cwe"], caso["cwe_name"])
        for tipo in TIPOS:
            prompt = montar_prompt(tipo, contexto=contexto, cwe_id=caso["cwe"],
                                   cwe_name=caso["cwe_name"],
                                   description=caso["description"], ficha=ficha)
            por_tipo[tipo].append(provedor.tokens_estimados(prompt))

    return por_tipo, sem_cache, nao_detectado


def main():
    ap = argparse.ArgumentParser(
        description="Distribuição de tamanho de prompt, em tokens estimados.")
    ap.add_argument("--num-ctx", type=int, default=NUM_CTX_PADRAO,
                    help=f"Janela avaliada. Padrão: {NUM_CTX_PADRAO}.")
    ap.add_argument("--num-predict", type=int, default=NUM_PREDICT,
                    help=f"Reserva para a saída. Padrão: {NUM_PREDICT}.")
    ap.add_argument("--trilha", action="append", choices=TRILHAS, metavar="TRILHA",
                    help=f"Restringe a uma trilha ({'|'.join(TRILHAS)}). Repetível.")
    ap.add_argument("--uma-location", action="store_true",
                    help="Só a primeira location de cada alerta.")
    ap.add_argument("--todas-extensoes", action="store_true",
                    help="Inclui locations que não são .go.")
    args = ap.parse_args()

    with open(DATASET_PATH, encoding="utf-8") as f:
        dataset = json.load(f)
    cwe_meta = _cwe_lookup(dataset)
    todas = not args.uma_location
    so_go = not args.todas_extensoes

    casos = (construir_casos_fp(dataset, todas_locations=todas, so_go=so_go)
             + construir_casos_tp(TP_PAIRS_OURO, "TP_ouro", cwe_meta)
             + construir_casos_tp(TP_PAIRS_PRATA, "TP_prata", cwe_meta)
             + construir_casos_tp_dataset(dataset, todas_locations=todas,
                                          so_go=so_go))
    if args.trilha:
        casos = [c for c in casos if c.origem in set(args.trilha)]

    provedor = ProvedorOllama(num_ctx=args.num_ctx, num_predict=args.num_predict)
    por_tipo, sem_cache, nao_detectado = medir(
        casos, CacheSimbolico(), catalogo_padrao(), provedor)

    teto = provedor.teto_do_prompt
    print(f"População: {len(casos)} casos | fora do cache simbólico: {sem_cache} "
          f"| sem alerta do Semgrep: {nao_detectado}")
    print(f"Janela avaliada: num_ctx={args.num_ctx} - "
          f"num_predict={args.num_predict} => teto de {teto} tokens de entrada\n")
    print(f"{'prompt':<14}{'n':>7}{'mín':>9}{'mediana':>10}{'p95':>9}"
          f"{'máx':>9}{'acima do teto':>16}")
    for tipo, valores in por_tipo.items():
        if not valores:
            print(f"{tipo:<14}{0:>7}   (nenhum caso com contexto em cache)")
            continue
        estouram = sum(1 for v in valores if v > teto)
        print(f"{tipo:<14}{len(valores):>7}{min(valores):>9}"
              f"{int(statistics.median(valores)):>10}"
              f"{percentil(valores, 95):>9}{max(valores):>9}"
              f"{estouram:>10} ({estouram / len(valores):.1%})")

    maximo = max((max(v) for v in por_tipo.values() if v), default=0)
    if maximo:
        print(f"\nPara não perder nenhum caso por contexto: "
              f"num_ctx >= {maximo + args.num_predict} "
              f"(maior prompt observado + reserva de saída).")
    if sem_cache:
        print(f"[!] {sem_cache} casos não estão no cache simbólico e ficaram de "
              "fora da medição. Rode a pipeline (--sem-llm) para preenchê-lo "
              "antes de fixar num_ctx.")


if __name__ == "__main__":
    main()
