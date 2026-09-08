"""
medir_pareamento.py — quanto o pareamento estrito muda em relação ao antigo.

Por que existe
--------------
A regra de pareamento da Fase 1 mudou em dois pontos ao mesmo tempo: saiu o
fallback que aceitava o alerta só por ser o único do arquivo, e o casamento de
CWE deixou de ser por substring. Os dois derrubam casos hoje `DETECTADO`, e
reportar o efeito somado esconderia o segundo — que é o mais insidioso, porque
emparelhava o caso à regra ERRADA e o resultado era indistinguível de um
emparelhamento legítimo em qualquer artefato existente.

Este script separa as duas contagens SEM re-executar o Semgrep: lê o cache
simbólico gravado sob a regra antiga e decide, caso a caso, o que a regra nova
faria com aquele mesmo alerta.

O que ele NÃO mede: casos que continuariam `NAO_DETECTADO`. O cache antigo não
registra quais regras dispararam, então a separação entre `SEM_ALERTA` e
`ALERTA_OUTRA_CWE` só existe depois da varredura nova.

USO
  python scripts/medir_pareamento.py
  python scripts/medir_pareamento.py --cache cache_simbolico --json
"""
import argparse
import glob
import json
import os
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.fase1_semgrep import _cwe_nas_tags  # noqa: E402
from src.ruleset import carregar_regras, metadados_snapshot  # noqa: E402

# O registry entrega o ruleset com `metadata.cwe` por regra — as mesmas strings
# que viram tags no SARIF. É a única fonte de tags para um alerta já cacheado:
# o payload guarda o alerta normalizado (check_id, linha, mensagem), não a regra.
# Quem busca e cacheia o ruleset é `src/ruleset.py`.


def _casava_por_substring(cwes, cwe):
    """A regra ANTIGA: `cwe_id` procurado como substring dentro da tag.

    Descreve o pareamento da VERSAO_PAREAMENTO 1, aquele em que `CWE-77` casava
    com `CWE-770`. Existe só para reproduzir as medições já registradas em
    `docs/ANALISE-RODADA-1.md` §7.1 e `docs/ANALISE-RODADA-2.md`: sem ela, aquela
    coluna some e os números documentados ficam irreproduzíveis.

    NÃO é para ser exportada nem reaproveitada — a comparação corrente vive em
    `src/fase1_semgrep._cwe_nas_tags`, e é dela que `src/ruleset.py` depende.
    """
    alvo = cwe.upper()
    return any(alvo in str(t).upper() for t in cwes)


def medir(dir_cache, regras):
    """Classifica cada entrada `DETECTADO` do cache sob a regra nova."""
    contagem = Counter()
    exemplos = defaultdict(list)

    for caminho in glob.glob(os.path.join(dir_cache, "*", "*", "*.json")):
        try:
            with open(caminho, encoding="utf-8") as f:
                p = json.load(f)
        except (OSError, json.JSONDecodeError):
            contagem["ilegivel"] += 1
            continue

        contagem["entradas"] += 1
        if p.get("status_semgrep") != "DETECTADO":
            contagem[p.get("status_semgrep", "?")] += 1
            continue

        contagem["detectado_antes"] += 1
        cwe = p["cwe"]
        check_id = (p.get("alerta") or {}).get("check_id", "")
        regra = regras.get(check_id)
        cwes_da_regra = None if regra is None else regra.cwes

        if cwes_da_regra is None:
            # Regra fora do ruleset baixado (versão diferente, regra removida):
            # sem as tags não dá para decidir, e chutar contaminaria a medida.
            motivo = "indeterminado (regra ausente do ruleset)"
        elif _cwe_nas_tags(cwes_da_regra, cwe):
            motivo = "continua emparelhado"
        elif _casava_por_substring(cwes_da_regra, cwe):
            motivo = "cai por prefixo de CWE"
        else:
            motivo = "cai por fallback de alerta unico"

        contagem[motivo] += 1
        if len(exemplos[motivo]) < 5:
            exemplos[motivo].append(f"{cwe} <- {check_id} {cwes_da_regra}")

    return contagem, exemplos


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--cache", default="cache_simbolico")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    regras = carregar_regras()
    contagem, exemplos = medir(args.cache, regras)

    if args.json:
        print(json.dumps(contagem, ensure_ascii=False, indent=2))
        return

    print("=" * 70)
    print(f"EFEITO DO PAREAMENTO ESTRITO SOBRE O CACHE ANTIGO ({args.cache})")
    print("=" * 70)
    snapshot = metadados_snapshot()
    print(f"  regras no ruleset baixado : {len(regras)}")
    print(f"  snapshot                  : {snapshot.origem} ({snapshot.obtido_em})")
    print(f"  entradas de cache         : {contagem['entradas']}")
    print(f"  DETECTADO sob a regra antiga: {contagem['detectado_antes']}")
    print(f"  NAO_DETECTADO             : {contagem['NAO_DETECTADO']}")
    print("\n  Destino dos DETECTADO sob a regra nova:")
    for motivo in ("continua emparelhado", "cai por fallback de alerta unico",
                   "cai por prefixo de CWE",
                   "indeterminado (regra ausente do ruleset)"):
        print(f"    {motivo:44} {contagem[motivo]:>5}")
        for ex in exemplos[motivo]:
            print(f"        {ex}")


if __name__ == "__main__":
    main()
