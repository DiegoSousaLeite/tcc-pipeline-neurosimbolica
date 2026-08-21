"""
preencher_cache.py — popula cache/ com todos os arquivos-alvo da pipeline.

Serve para dois momentos:

  1. ANTES de apagar repos/ — extrai tudo dos clones locais via `git show`,
     sem rede. Depois disso os clones viram descartáveis.
  2. Em qualquer máquina sem os clones — baixa o que faltar da rede, deixando
     o experimento pronto para rodar offline.

USO
  python scripts/preencher_cache.py --somente-local   # só clones, sem rede
  python scripts/preencher_cache.py                   # local, e rede p/ o resto
  python scripts/preencher_cache.py --dry-run         # só relata o que falta
"""
import argparse
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
from src.config import DATASET_PATH  # noqa: E402
from src.fonte import (  # noqa: E402
    ArquivoInexistente,
    FetchError,
    _do_clone_local,
    _gravar,
    caminho_cache,
    estatisticas_cache,
    obter_arquivo,
)


def casos_unicos(so_go=True):
    """Todos os casos da pipeline, deduplicados por (repo, commit, arquivo)."""
    with open(DATASET_PATH, encoding="utf-8") as f:
        dataset = json.load(f)
    meta = _cwe_lookup(dataset)
    casos = (
        construir_casos_fp(dataset, todas_locations=True, so_go=so_go)
        + construir_casos_tp(TP_PAIRS_OURO, "TP_ouro", meta)
        + construir_casos_tp(TP_PAIRS_PRATA, "TP_prata", meta)
        + construir_casos_tp_dataset(dataset, todas_locations=True, so_go=so_go)
    )
    vistos, unicos = set(), []
    for c in casos:
        chave = (c["repo_name"], c["commit"], c["arquivo"])
        if chave not in vistos:
            vistos.add(chave)
            unicos.append(c)
    return unicos


def main():
    ap = argparse.ArgumentParser(description="Popula o cache de arquivos-alvo.")
    ap.add_argument("--somente-local", action="store_true",
                    help="Usa só os clones em repos/; nunca acessa a rede.")
    ap.add_argument("--dry-run", action="store_true",
                    help="Só relata o que está faltando.")
    ap.add_argument("--todas-extensoes", action="store_true",
                    help="Inclui locations que não são .go.")
    args = ap.parse_args()

    casos = casos_unicos(so_go=not args.todas_extensoes)
    print(f"[+] Arquivos-alvo distintos: {len(casos)}")

    ja, do_git, da_rede, faltando = 0, 0, 0, []

    for i, c in enumerate(casos, 1):
        destino = caminho_cache(c["repo_name"], c["commit"], c["arquivo"])
        if os.path.exists(destino):
            ja += 1
            continue
        if args.dry_run:
            faltando.append(c)
            continue

        conteudo = _do_clone_local(c["repo_name"], c["commit"], c["arquivo"])
        if conteudo is not None:
            _gravar(destino, conteudo)
            do_git += 1
        elif args.somente_local:
            faltando.append(c)
        else:
            try:
                obter_arquivo(c["repo_name"], c["commit"], c["arquivo"])
                da_rede += 1
            except (FetchError, ArquivoInexistente) as e:
                faltando.append(c)
                print(f"  [x] {c['repo_dir']}/{c['arquivo']}: {str(e)[:90]}")

        if i % 100 == 0:
            print(f"    ... {i}/{len(casos)}")

    n, b = estatisticas_cache()
    print("\n=== RESUMO ===")
    print(f"  já estavam em cache : {ja}")
    if not args.dry_run:
        print(f"  extraídos de repos/ : {do_git}")
        print(f"  baixados da rede    : {da_rede}")
    print(f"  faltando            : {len(faltando)}")
    print(f"\n[+] Cache: {n} arquivos | {b/1024/1024:.1f} MB")

    if faltando:
        print("\n  Primeiros faltantes:")
        for c in faltando[:10]:
            print(f"    {c['repo_name']}@{c['commit'][:10]} {c['arquivo']}")
        if args.somente_local:
            print("\n  Rode sem --somente-local para buscar esses na rede.")
    elif not args.dry_run:
        print("\n[+] Cache completo — repos/ não é mais necessário.")


if __name__ == "__main__":
    main()
