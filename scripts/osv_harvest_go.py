"""
osv_harvest_go.py — colhe vulnerabilidades reais de Go da OSV.dev para virar TPs.

Baixa o dump de Go da OSV, e para cada vuln consulta a OSV por CVE/GHSA atrás do
commit de fix (range GIT) + repo no GitHub. Junta um conjunto de candidatos no
mesmo formato do tp_fixes.json (com repo_url incluído), pronto para:
    python scripts/fetch_raso.py     --input tp_fixes_osv.json
    python scripts/tp_reconstruct.py --input tp_fixes_osv.json

Todos os tipos de CWE. Filtros: precisa de commit de fix + repo GitHub.
Limita por repo (diversidade) e para ao atingir o alvo.

USO
  python scripts/osv_harvest_go.py --alvo 100
  python scripts/osv_harvest_go.py --alvo 100 --por-repo 5 --max-scan 600
"""
import argparse
import io
import json
import os
import time
import urllib.request
import zipfile
from collections import Counter

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(BASE, "tp_fixes_osv.json")
DUMP_URL = "https://osv-vulnerabilities.storage.googleapis.com/Go/all.zip"
OSV_VULN = "https://api.osv.dev/v1/vulns/"


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


def extrai(vuln):
    """Devolve (repo_url, fix_commit, cwe) do primeiro range GIT com fix no GitHub."""
    if not vuln:
        return None, None, None
    cwe = None
    ds = vuln.get("database_specific", {}) or {}
    cwes = ds.get("cwe_ids") or []
    if cwes:
        cwe = cwes[0]
    for aff in vuln.get("affected", []):
        for rng in aff.get("ranges", []):
            if rng.get("type") != "GIT":
                continue
            repo = rng.get("repo", "")
            if "github.com" not in repo:
                continue
            for ev in rng.get("events", []):
                if ev.get("fixed"):
                    return repo.rstrip("/").removesuffix(".git"), ev["fixed"], cwe
    return None, None, cwe


def main():
    ap = argparse.ArgumentParser(description="Colhe TPs de Go da OSV.")
    ap.add_argument("--alvo", type=int, default=100, help="Quantos candidatos colher (default 100).")
    ap.add_argument("--por-repo", type=int, default=5, help="Máx. de vulns por repo (diversidade).")
    ap.add_argument("--max-scan", type=int, default=800, help="Teto de entradas a varrer.")
    args = ap.parse_args()

    z = baixar_dump()
    nomes = sorted(z.namelist())
    print(f"[+] {len(nomes)} vulns Go no dump. Alvo: {args.alvo} candidatos.\n")

    candidatos, por_repo, vistos_commit = [], Counter(), set()
    scan = 0
    for n in nomes:
        if len(candidatos) >= args.alvo or scan >= args.max_scan:
            break
        scan += 1
        v0 = json.loads(z.read(n))
        ids = ([x for x in v0.get("aliases", []) if x.startswith("CVE")]
               + [x for x in v0.get("aliases", []) if x.startswith("GHSA")]
               + [v0.get("id")])

        repo_url = fix = cwe = None
        cve_usado = None
        for idv in ids[:2]:
            vuln = osv_por_id(idv)
            time.sleep(0.15)
            repo_url, fix, cwe = extrai(vuln)
            if fix:
                cve_usado = idv
                break
        if not fix or not repo_url:
            continue

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
            "cwe_id": cwe or "CWE-desconhecida",
            "cve_ids": [cve_usado] if cve_usado else [],
            "fix_commit": fix,
            "fonte": "osv",
        })
        if len(candidatos) % 20 == 0:
            print(f"    coletados {len(candidatos)}/{args.alvo} (varridos {scan})...")

    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(candidatos, f, indent=2, ensure_ascii=False)

    print("\n=== RESUMO ===")
    print(f"  varridos: {scan} | candidatos colhidos: {len(candidatos)}")
    print(f"  repos distintos: {len(por_repo)}")
    print(f"  top CWEs: {Counter(c['cwe_id'] for c in candidatos).most_common(8)}")
    print(f"\n[+] Saída: {OUT}")
    print("[+] Próximo: python scripts/fetch_raso.py --input tp_fixes_osv.json")
    print("            python scripts/tp_reconstruct.py --input tp_fixes_osv.json")


if __name__ == "__main__":
    main()
