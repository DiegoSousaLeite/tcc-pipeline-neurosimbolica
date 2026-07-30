"""
ranking_cwe.py — volume de amostras por CWE, para dimensionar o catálogo.

Conta as locations `.go` de TODAS as entradas do dataset (false_positive e
true_positive), excluindo arquivos `_test.go`. É a medida que decide quantas
fichas o `data/catalogo_cwe.json` precisa ter para cobrir a fração declarada
das amostras — e é ela que a tarefa 5.1 exige reproduzir antes de escrever as
fichas.

Só metadado (`cwe_id`) é lido: nenhum trecho de código sai daqui, para não
contaminar quem escreve as fichas (protocolo anti-viés, D5 do design).

USO
  python scripts/ranking_cwe.py            # top 15 + cobertura acumulada
  python scripts/ranking_cwe.py --top 20
  python scripts/ranking_cwe.py --json     # saída para conferência automática
"""
import argparse
import json
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.config import DATASET_PATH  # noqa: E402

EXTENSAO = ".go"
SUFIXO_TESTE = "_test.go"


def contar(dataset) -> Counter:
    contagem = Counter()
    for entrada in dataset:
        cwe = entrada["metadata"]["cwe_id"]
        for local in entrada["to_analyzer"].get("locations", []):
            arquivo = local["file"].lower()
            if arquivo.endswith(EXTENSAO) and not arquivo.endswith(SUFIXO_TESTE):
                contagem[cwe] += 1
    return contagem


def main():
    ap = argparse.ArgumentParser(description="Ranking de CWEs por volume de amostras.")
    ap.add_argument("--top", type=int, default=15)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    with open(DATASET_PATH, encoding="utf-8") as f:
        dataset = json.load(f)

    contagem = contar(dataset)
    total = sum(contagem.values())
    top = contagem.most_common(args.top)
    cobertura = sum(n for _, n in top) / total if total else 0.0

    if args.json:
        print(json.dumps({
            "total_amostras": total,
            "total_cwes": len(contagem),
            "top": [{"cwe": c, "amostras": n} for c, n in top],
            "cobertura_top": cobertura,
        }, indent=2, ensure_ascii=False))
        return

    print(f"Total: {total} amostras .go (excluindo _test.go) em {len(contagem)} CWEs\n")
    print(f"{'#':>3}  {'CWE':<12} {'Amostras':>8}  {'%':>6}  {'acum.':>6}")
    acumulado = 0
    for i, (cwe, n) in enumerate(top, 1):
        acumulado += n
        print(f"{i:>3}  {cwe:<12} {n:>8}  {n/total*100:>5.1f}%  {acumulado/total*100:>5.1f}%")
    print(f"\nCobertura das {len(top)} primeiras: {cobertura*100:.1f}%")


if __name__ == "__main__":
    main()
