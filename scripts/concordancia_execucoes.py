"""Concordância entre duas execuções idênticas de uma rodada (mesmo modelo e braços).

Para cada prompt, pareia os casos com veredito válido (VP/FP) nas duas
execuções — no modo triagem, isso inclui os positivos injetados, que vêm com
Status_Semgrep NAO_DETECTADO, como no pareamento de `mcnemar` em
src/metricas.py. Reporta acordo, kappa de Cohen, trocas de veredito (e quantas
em casos vulneráveis) e o McNemar do acerto entre as execuções — exato binomial
se b+c < 25, senão qui-quadrado com Yates, como em src/metricas.py.

Uso:
    python scripts/concordancia_execucoes.py results/<run1> results/<run2> \
        --modelo gpt-6-luna --prompt baseline --prompt especialista
"""
import argparse
import csv
import math
from collections import Counter


def carregar(diretorio, modelo, prompt):
    caminho = f"{diretorio}/{modelo.replace(':', '-')}__{prompt}.csv"
    with open(caminho, encoding="utf-8") as f:
        return {
            r["ID_Caso"]: r
            for r in csv.DictReader(f)
            if r["Veredito_LLM"] in ("VP", "FP")
        }


def mcnemar(b, c):
    n = b + c
    if n == 0:
        return 1.0
    if n < 25:
        k = min(b, c)
        return min(1.0, 2 * sum(math.comb(n, i) for i in range(k + 1)) / 2**n)
    return math.erfc(math.sqrt((abs(b - c) - 1) ** 2 / n / 2))


def vulneravel(r):
    return r["Gabarito"].lower().startswith("vuln")


def acertou(r):
    return (r["Veredito_LLM"] == "VP") == vulneravel(r)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("execucao_1")
    ap.add_argument("execucao_2")
    ap.add_argument("--modelo", required=True)
    ap.add_argument("--prompt", action="append", required=True)
    args = ap.parse_args()

    for prompt in args.prompt:
        a = carregar(args.execucao_1, args.modelo, prompt)
        b = carregar(args.execucao_2, args.modelo, prompt)
        ids = sorted(set(a) & set(b))
        n = len(ids)
        acordo = sum(a[i]["Veredito_LLM"] == b[i]["Veredito_LLM"] for i in ids)
        po = acordo / n
        ca = Counter(a[i]["Veredito_LLM"] for i in ids)
        cb = Counter(b[i]["Veredito_LLM"] for i in ids)
        pe = sum(ca[k] * cb[k] for k in ("VP", "FP")) / n**2
        kappa = (po - pe) / (1 - pe)
        vuln = [i for i in ids if vulneravel(a[i])]
        trocas_v = sum(a[i]["Veredito_LLM"] != b[i]["Veredito_LLM"] for i in vuln)
        so_1 = sum(acertou(a[i]) and not acertou(b[i]) for i in ids)
        so_2 = sum(acertou(b[i]) and not acertou(a[i]) for i in ids)
        print(
            f"{prompt}: n1={len(a)} n2={len(b)} pareado={n} "
            f"acordo={acordo}/{n}={po:.4f} kappa={kappa:.4f} trocas={n - acordo} "
            f"(vulneraveis: {trocas_v}/{len(vuln)}) | "
            f"McNemar acerto exec1 x exec2: {so_1}x{so_2} p={mcnemar(so_1, so_2):.4f}"
        )


if __name__ == "__main__":
    main()
