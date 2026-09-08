"""
pares_alcancaveis.py — quais pares já colhidos o motor simbólico alcança.

Os pools de pares vuln/corrigido (`tp_pairs.json`, `tp_pairs_osv.json`) foram
montados antes de existir o filtro de alcançabilidade: a colheita nunca
consultou o ruleset, e 70,1% dos casos vulneráveis da rodada
`20260731T140000Z-af9bc32` acabaram com CWE que nenhuma regra Go do `p/default`
declara (`docs/ANALISE-RODADA-2.md`). Parte dos pares, porém, é aproveitável —
e recolhê-los do zero gastaria rede para reobter o que já está em disco.

SOMENTE LEITURA. Este script identifica e lista; não escreve nos pools nem monta
população. Separar identificação de mutação é o que torna a operação repetível e
segura: `tp_pairs.json` é irrecuperável — só `scripts/tp_reconstruct.py` o
regenera, e ele exige o histórico git completo dos repositórios, que não está
mais em disco.

USO
  python scripts/pares_alcancaveis.py
  python scripts/pares_alcancaveis.py --pools tp_pairs.json
  python scripts/pares_alcancaveis.py --json    # saída para conferência automática
"""
import argparse
import json
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.ruleset import cwe_alcancavel, metadados_snapshot  # noqa: E402

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
POOLS = ["tp_pairs.json", "tp_pairs_osv.json"]
LINGUAGEM = "go"


def avaliar(pares, linguagem=LINGUAGEM, catalogo=None):
    """Separa os pares em alcançáveis e inalcançáveis pelo motor.

    A CWE do par é registrada junto: é ela que a Fase 1 vai procurar no arquivo,
    e é contra ela que o gabarito será pontuado.
    """
    alcancaveis, inalcancaveis = [], []
    for par in pares:
        cwe = par.get("cwe_id")
        destino = alcancaveis if cwe_alcancavel(cwe, linguagem, catalogo) else inalcancaveis
        destino.append(par)
    return alcancaveis, inalcancaveis


def main():
    ap = argparse.ArgumentParser(
        description="Lista os pares de TP já colhidos cuja CWE o motor alcança.")
    ap.add_argument("--pools", nargs="+", default=POOLS,
                    help=f"Arquivos de pares a avaliar (default: {' '.join(POOLS)}).")
    ap.add_argument("--json", action="store_true", help="Saída em JSON.")
    args = ap.parse_args()

    snap = metadados_snapshot()
    relatorio, total_alc, total = {}, 0, 0
    for pool in args.pools:
        caminho = pool if os.path.isabs(pool) else os.path.join(BASE, pool)
        if not os.path.exists(caminho):
            print(f"[!] Pool ausente, ignorado: {caminho}")
            continue
        with open(caminho, encoding="utf-8") as f:
            pares = json.load(f)
        alc, inalc = avaliar(pares)
        total_alc += len(alc)
        total += len(pares)
        relatorio[pool] = {
            "total": len(pares),
            "alcancaveis": len(alc),
            "cwes_alcancaveis": Counter(p["cwe_id"] for p in alc).most_common(),
            "cwes_inalcancaveis": Counter(p["cwe_id"] for p in inalc).most_common(),
            "pares": [{"repo": p.get("repo"), "cwe_id": p.get("cwe_id"),
                       "cve_ids": p.get("cve_ids", []),
                       "arquivo": p.get("arquivo"), "funcao": p.get("funcao"),
                       "fix_commit": p.get("fix_commit")} for p in alc],
        }

    if args.json:
        print(json.dumps({"ruleset": snap._asdict(),
                          "total": total, "alcancaveis": total_alc,
                          "pools": relatorio}, indent=2, ensure_ascii=False))
        return

    print(f"[+] Ruleset: {snap.origem} ({snap.regras} regras, obtido em {snap.obtido_em})")
    print(f"[+] Linguagem: {LINGUAGEM}\n")
    for pool, dados in relatorio.items():
        print(f"=== {pool} — {dados['alcancaveis']}/{dados['total']} alcançáveis ===")
        for p in dados["pares"]:
            cves = ",".join(p["cve_ids"]) or "-"
            print(f"  {p['cwe_id']:<10} {p['repo']:<40} {p['arquivo']}::{p['funcao']} ({cves})")
        print(f"  aceitas por CWE:   {dados['cwes_alcancaveis']}")
        print(f"  recusadas por CWE: {dados['cwes_inalcancaveis']}\n")

    print(f"=== TOTAL: {total_alc}/{total} pares aproveitáveis sem recolheita ===")
    print("[i] Somente leitura: nenhum pool foi modificado.")


if __name__ == "__main__":
    main()
