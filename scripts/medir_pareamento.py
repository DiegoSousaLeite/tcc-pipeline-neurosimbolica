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

from src.fase1_semgrep import SEMGREP_CONFIG, _cwe_nas_tags  # noqa: E402

# O registry entrega o ruleset com `metadata.cwe` por regra — as mesmas strings
# que viram tags no SARIF. É a única fonte de tags para um alerta já cacheado:
# o payload guarda o alerta normalizado (check_id, linha, mensagem), não a regra.
URL_REGISTRY = f"https://semgrep.dev/c/{SEMGREP_CONFIG}"
REGRAS_CACHE = os.path.join("cache_simbolico", "_regras_p_default.json")


def carregar_regras(destino=REGRAS_CACHE):
    """`check_id` -> lista de CWEs declaradas, baixada uma vez e cacheada."""
    if not os.path.exists(destino):
        import requests
        print(f"[+] baixando {URL_REGISTRY} ...", file=sys.stderr)
        resp = requests.get(URL_REGISTRY, timeout=120,
                            headers={"User-Agent": "semgrep"})
        resp.raise_for_status()
        os.makedirs(os.path.dirname(destino), exist_ok=True)
        with open(destino, "wb") as f:
            f.write(resp.content)

    with open(destino, encoding="utf-8") as f:
        dados = json.load(f)
    return {r["id"]: _lista(( r.get("metadata") or {}).get("cwe"))
            for r in dados.get("rules", [])}


def _lista(cwe):
    """`metadata.cwe` vem ora como lista, ora como string única no registry.

    Tratar a string como iterável percorreria CARACTERES e nenhuma regra
    casaria — a medição sairia inteira na coluna errada.
    """
    if cwe is None:
        return []
    return [cwe] if isinstance(cwe, str) else list(cwe)


def _casava_por_substring(cwes, cwe):
    """A regra ANTIGA: `cwe_id` procurado como substring dentro da tag."""
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
        cwes_da_regra = regras.get(check_id)

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
    print(f"  regras no ruleset baixado : {len(regras)}")
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
