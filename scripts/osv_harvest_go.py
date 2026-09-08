"""
osv_harvest_go.py — colhe vulnerabilidades reais de Go da OSV.dev para virar TPs.

Baixa o dump de Go da OSV, e para cada vuln consulta a OSV por CVE/GHSA atrás do
commit de fix (range GIT) + repo no GitHub. Junta um conjunto de candidatos no
mesmo formato do tp_fixes.json (com repo_url incluído), pronto para:
    python scripts/fetch_raso.py     --input data/tp_fixes_osv_alcancavel.json
    python scripts/tp_reconstruct.py --input data/tp_fixes_osv_alcancavel.json

Filtros: CWE alcançável pelo motor simbólico em Go + commit de fix + repo GitHub.
Limita por repo (diversidade) e para ao atingir o alvo.

Por que o filtro de alcançabilidade existe
------------------------------------------
A colheita antiga aceitava qualquer CWE. O resultado, medido em
`docs/ANALISE-RODADA-2.md`: 70,1% dos casos vulneráveis tinham CWE que nenhuma
regra Go do `p/default` declara — indetectáveis por construção. O motor não pode
falhar em achar o que não sabe procurar, e o recall medido sobre essa população
mede a lacuna do catálogo de regras, não a capacidade do motor.

Todas as CWEs declaradas são avaliadas, não só a primeira: a ordem de
`database_specific.cwe_ids` é arbitrária, e a CWE registrada tem de ser a que
casou com o ruleset — é ela que a Fase 1 vai procurar no arquivo.

USO
  python scripts/osv_harvest_go.py --alvo 100
  python scripts/osv_harvest_go.py --alvo 100 --por-repo 5 --max-scan 600
"""
import argparse
import io
import json
import os
import sys
import time
import urllib.request
import zipfile
from collections import Counter
from typing import NamedTuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.config import DATA_DIR  # noqa: E402
from src.ruleset import cwe_alcancavel, metadados_snapshot  # noqa: E402

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Arquivo próprio: `data/tp_fixes_osv.json` é a colheita sem filtro, e os pares
# vindos dela são a evidência do achado dos 70%. Sobrescrevê-la apagaria a
# evidência, e `tp_pairs.json` é irrecuperável — só `tp_reconstruct.py` o
# regenera, e ele exige o histórico git que não está mais em disco.
OUT = os.path.join(DATA_DIR, "tp_fixes_osv_alcancavel.json")
DUMP_URL = "https://osv-vulnerabilities.storage.googleapis.com/Go/all.zip"
OSV_VULN = "https://api.osv.dev/v1/vulns/"

LINGUAGEM = "go"
SEM_CWE = "(sem CWE declarada)"


class Extracao(NamedTuple):
    """O que se conseguiu tirar de uma vulnerabilidade da OSV.

    `cwe` é a que casou com o ruleset, não a primeira declarada.
    `inalcancaveis` traz as CWEs que causaram a recusa — vazio quando a recusa
    veio de outro filtro (sem commit de fix, repo fora do GitHub), para que o
    relatório não confunda "a OSV tem pouca coisa nestas fraquezas" com "o
    filtro está recusando tudo por defeito".
    """

    repo_url: object
    fix_commit: object
    cwe: object
    inalcancaveis: tuple = ()


def baixar_dump():
    print("[+] Baixando dump de Go da OSV...")
    data = urllib.request.urlopen(DUMP_URL, timeout=180).read()
    return zipfile.ZipFile(io.BytesIO(data))


def osv_por_id(idv):
    try:
        req = urllib.request.Request(OSV_VULN + idv, headers={"User-Agent": "tcc-harvest/1.0"})
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.loads(r.read())
    except Exception:
        return None


def extrai(vuln, linguagem=LINGUAGEM, catalogo=None):
    """Extrai repo, commit de fix e a CWE alcançável de uma vulnerabilidade.

    A alcançabilidade é decidida aqui, junto da leitura da CWE: este é o único
    ponto que conhece a estrutura da vulnerabilidade, e o laço principal
    continua responsável apenas por diversidade de repo, dedup e alvo.
    """
    if not vuln:
        return Extracao(None, None, None)

    ds = vuln.get("database_specific", {}) or {}
    declaradas = [c for c in (ds.get("cwe_ids") or []) if c]
    if not declaradas:
        # Aceitar como "CWE-desconhecida", como se fazia, colocaria na população
        # um caso sobre o qual não se pode afirmar que o motor o alcança.
        return Extracao(None, None, None, (SEM_CWE,))

    cwe = next((c for c in declaradas
                if cwe_alcancavel(c, linguagem, catalogo)), None)
    if cwe is None:
        return Extracao(None, None, None, tuple(declaradas))

    for aff in vuln.get("affected", []):
        for rng in aff.get("ranges", []):
            if rng.get("type") != "GIT":
                continue
            repo = rng.get("repo", "")
            if "github.com" not in repo:
                continue
            for ev in rng.get("events", []):
                if ev.get("fixed"):
                    return Extracao(repo.rstrip("/").removesuffix(".git"),
                                    ev["fixed"], cwe)
    return Extracao(None, None, cwe)


def main():
    ap = argparse.ArgumentParser(description="Colhe TPs de Go da OSV.")
    ap.add_argument("--alvo", type=int, default=100, help="Quantos candidatos colher (default 100).")
    ap.add_argument("--por-repo", type=int, default=5, help="Máx. de vulns por repo (diversidade).")
    ap.add_argument("--max-scan", type=int, default=800, help="Teto de entradas a varrer.")
    args = ap.parse_args()

    # Antes do dump de dezenas de MB: sem ruleset não há filtro, e colheita sem
    # filtro é exatamente o que este script passou a existir para impedir.
    snap = metadados_snapshot()
    print(f"[+] Ruleset: {snap.origem} ({snap.regras} regras, obtido em {snap.obtido_em})")

    z = baixar_dump()
    nomes = sorted(z.namelist())
    print(f"[+] {len(nomes)} vulns Go no dump. Alvo: {args.alvo} candidatos.\n")

    candidatos, por_repo, vistos_commit = [], Counter(), set()
    recusas_cwe = Counter()
    scan = 0
    for n in nomes:
        if len(candidatos) >= args.alvo or scan >= args.max_scan:
            break
        scan += 1
        v0 = json.loads(z.read(n))
        ids = ([x for x in v0.get("aliases", []) if x.startswith("CVE")]
               + [x for x in v0.get("aliases", []) if x.startswith("GHSA")]
               + [v0.get("id")])

        ext = Extracao(None, None, None)
        inalcancaveis = set()
        cve_usado = None
        for idv in ids[:2]:
            vuln = osv_por_id(idv)
            time.sleep(0.15)
            ext = extrai(vuln)
            # Conjunto, e não contador: os dois aliases descrevem a MESMA
            # vulnerabilidade e contariam a recusa duas vezes.
            inalcancaveis.update(ext.inalcancaveis)
            if ext.fix_commit:
                cve_usado = idv
                break
        if not ext.fix_commit or not ext.repo_url:
            recusas_cwe.update(inalcancaveis)
            continue

        repo_url, fix, cwe = ext.repo_url, ext.fix_commit, ext.cwe
        if (repo_url, fix) in vistos_commit:
            continue
        repo_name = "/".join(repo_url.split("github.com/")[-1].split("/")[:2])
        repo_dir = repo_name.split("/")[-1]
        if por_repo[repo_name] >= args.por_repo:
            continue
        vistos_commit.add((repo_url, fix))
        por_repo[repo_name] += 1
        candidatos.append({
            "repo_name": repo_name,
            "repo_dir": repo_dir,
            "repo_url": repo_url,
            "cwe_id": cwe,
            "cve_ids": [cve_usado] if cve_usado else [],
            "fix_commit": fix,
            "fonte": "osv",
        })
        if len(candidatos) % 20 == 0:
            print(f"    coletados {len(candidatos)}/{args.alvo} (varridos {scan})...")

    print("\n=== RESUMO ===")
    print(f"  varridos: {scan} | candidatos colhidos: {len(candidatos)}")
    print(f"  repos distintos: {len(por_repo)}")
    print(f"  ruleset: {snap.origem} | obtido em: {snap.obtido_em}")
    print(f"  CWEs aceitas: {Counter(c['cwe_id'] for c in candidatos).most_common()}")
    print(f"  recusadas por inalcançabilidade: {sum(recusas_cwe.values())}")
    print(f"  recusadas por CWE: {recusas_cwe.most_common()}")

    if not candidatos:
        print("\n[!] NENHUMA candidata sobreviveu ao filtro de alcançabilidade.")
        print(f"[!] Nada foi gravado — {OUT} não foi criado nem alterado.")
        print("[!] Confira as recusas por CWE acima: recusa concentrada em poucas")
        print("[!] CWEs é resultado; recusa uniforme de tudo é suspeita de defeito.")
        return

    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(candidatos, f, indent=2, ensure_ascii=False)

    rel = os.path.relpath(OUT, BASE).replace(os.sep, "/")
    print(f"\n[+] Saída: {OUT}")
    print(f"[+] Próximo: python scripts/fetch_raso.py --input {rel}")
    print(f"            python scripts/tp_reconstruct.py --input {rel}")


if __name__ == "__main__":
    main()
