"""
auditar_regras_ficha.py — quais regras do Semgrep disparam em cada CWE.

Por que existe
--------------
A ficha do prompt especialista era escolhida só pela CWE do caso, mas uma CWE
agrupa regras que olham para construções diferentes: em CWE-327 a ficha ensina
`md5` em senha e a regra que dispara é `missing-ssl-minversion` (TLS). Este
script produz a tabela regra × CWE × detecções que decide quais regras ganham
ficha própria no bloco `regras` do catálogo.

Protocolo anti-viés
-------------------
O script lê do cache simbólico **apenas** o `check_id` do alerta e o status.
Nunca lê `contexto_hidratado` nem o código das amostras: a seleção das regras
usa só metadado, e as fichas são escritas a partir da documentação da regra e
da stdlib de Go, não do que as amostras contêm.

Uso
---
  python scripts/auditar_regras_ficha.py
  python scripts/auditar_regras_ficha.py --minimo 5
"""
import argparse
import collections
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from run_pipeline import (  # noqa: E402
    TP_PAIRS_OURO,
    TP_PAIRS_PRATA,
    _cwe_lookup,
    construir_casos_fp,
    construir_casos_tp,
    construir_casos_tp_dataset,
)
from src.cache_simbolico import CacheSimbolico  # noqa: E402
from src.catalogo import catalogo_padrao  # noqa: E402
from src.config import DATASET_PATH  # noqa: E402


def contar(casos, cache):
    """`{(check_id, cwe): detecções}` só a partir de metadado do cache."""
    contagem = collections.Counter()
    for caso in casos:
        payload = cache.ler(caso["repo_name"], caso["commit"], caso["arquivo"],
                            caso["cwe"])
        if not payload or payload.get("status_semgrep") != "DETECTADO":
            continue
        check_id = (payload.get("alerta") or {}).get("check_id")
        if check_id:
            contagem[(check_id, caso["cwe"])] += 1
    return contagem


def main():
    ap = argparse.ArgumentParser(
        description="Tabela regra × CWE × detecções, a partir do cache simbólico.")
    ap.add_argument("--minimo", type=int, default=5,
                    help="Só lista regras com pelo menos N detecções (padrão 5).")
    args = ap.parse_args()

    with open(DATASET_PATH, encoding="utf-8") as f:
        dataset = json.load(f)
    cwe_meta = _cwe_lookup(dataset)
    casos = (construir_casos_fp(dataset)
             + construir_casos_tp(TP_PAIRS_OURO, "TP_ouro", cwe_meta)
             + construir_casos_tp(TP_PAIRS_PRATA, "TP_prata", cwe_meta)
             + construir_casos_tp_dataset(dataset))
    catalogo = catalogo_padrao()
    contagem = contar(casos, CacheSimbolico())

    print(f"{'detecções':>9}  {'CWE':<9} {'ficha':<11} regra (check_id)")
    for (check_id, cwe), n in sorted(contagem.items(), key=lambda x: -x[1]):
        if n < args.minimo:
            continue
        if catalogo.tem_ficha_de_regra(check_id):
            origem = "regra"
        elif catalogo.tem_ficha(cwe):
            origem = "cwe"
        else:
            origem = "fallback"
        print(f"{n:>9}  {cwe:<9} {origem:<11} {check_id}")
    print(f"\nTotal de detecções: {sum(contagem.values())} "
          f"| regras distintas: {len({c for c, _ in contagem})}")


if __name__ == "__main__":
    main()
