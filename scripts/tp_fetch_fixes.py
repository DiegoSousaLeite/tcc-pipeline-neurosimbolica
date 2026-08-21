"""
tp_fetch_fixes.py — preenche automaticamente o `fix_commit` de cada CVE em
tp_fixes.json consultando a OSV.dev (https://osv.dev), de graça e sem login.

Para cada CVE:
  - GET https://api.osv.dev/v1/vulns/{CVE}
  - procura ranges do tipo GIT com evento 'fixed' (hash do commit de correção)
  - prefere o range cujo 'repo' casa com o repositório do dataset
  - escreve fix_commit (SÓ se estiver vazio) + fix_status + candidatos

Não destrói nada: nunca sobrescreve um fix_commit já preenchido à mão.
Roda na SUA máquina (precisa de internet). É idempotente: re-rodar só tenta
de novo os que ainda não foram preenchidos.

USO
  python scripts/tp_fetch_fixes.py            # preenche tp_fixes.json
  python scripts/tp_fetch_fixes.py --selftest # valida a lógica sem internet
"""
import json
import os
import sys
import time
import urllib.error
import urllib.request

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIXES_FILE = os.path.join(BASE, "data", "tp_fixes.json")
OSV_URL = "https://api.osv.dev/v1/vulns/"


def osv_get(cve):
    """Consulta a OSV por um ID (CVE/GHSA). Retorna (json|None, erro|None)."""
    req = urllib.request.Request(OSV_URL + cve,
                                 headers={"User-Agent": "tcc-tp-fetch/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode("utf-8")), None
    except urllib.error.HTTPError as e:
        return None, ("nao_encontrado_osv" if e.code == 404 else f"http_{e.code}")
    except Exception as e:
        return None, f"erro_rede:{str(e)[:80]}"


def extrai_fix_commits(vuln, repo_name):
    """Extrai commits de fix de um registro OSV.
    Retorna (melhor_commit|None, candidatos[(repo,commit)], so_versao: bool, repo_casou: bool).
    """
    candidatos, so_versao = [], False
    for aff in vuln.get("affected", []):
        for rng in aff.get("ranges", []):
            tipo = rng.get("type")
            if tipo == "GIT":
                repo = rng.get("repo", "")
                for ev in rng.get("events", []):
                    if ev.get("fixed"):
                        candidatos.append((repo, ev["fixed"]))
            elif tipo in ("SEMVER", "ECOSYSTEM"):
                if any(ev.get("fixed") for ev in rng.get("events", [])):
                    so_versao = True

    # prefere o commit do repo que casa com o repositório do dataset
    alvo = (repo_name or "").lower()
    for repo, commit in candidatos:
        if alvo and alvo in (repo or "").lower():
            return commit, candidatos, so_versao, True
    if candidatos:
        return candidatos[0][1], candidatos, so_versao, False  # achou, mas revisar
    return None, candidatos, so_versao, False


def preencher():
    if not os.path.exists(FIXES_FILE):
        print(f"[ERRO] {FIXES_FILE} não existe. Rode antes: "
              f"python scripts/tp_reconstruct.py --init")
        sys.exit(1)
    fixes = json.load(open(FIXES_FILE, encoding="utf-8"))

    stats = {"ja_tinha": 0, "ok_repo": 0, "ok_revisar": 0,
             "so_versao": 0, "sem_cve": 0, "nao_achou": 0}

    for i, item in enumerate(fixes, 1):
        repo_name = item.get("repo_name", "")
        cves = item.get("cve_ids") or []
        prefixo = f"[{i}/{len(fixes)}] {item.get('repo_dir','?'):16} {','.join(cves) or '(sem CVE)'}"

        if (item.get("fix_commit") or "").strip():
            stats["ja_tinha"] += 1
            print(f"{prefixo} -> já preenchido, pulando")
            continue
        if not cves:
            item["fix_status"] = "sem_cve_id"
            stats["sem_cve"] += 1
            print(f"{prefixo} -> sem CVE, manual")
            continue

        achou = False
        for cve in cves:
            vuln, erro = osv_get(cve)
            time.sleep(0.2)  # educado com a API
            if erro == "nao_encontrado_osv":
                continue
            if erro:
                item["fix_status"] = erro
                print(f"{prefixo} -> {erro}")
                achou = True  # erro de rede: não marca como 'não achou', tenta de novo depois
                break
            commit, cands, so_versao, repo_casou = extrai_fix_commits(vuln, repo_name)
            if commit:
                item["fix_commit"] = commit
                item["fix_source"] = f"osv:{cve}"
                item["fix_status"] = "ok_repo_casou" if repo_casou else "ok_REVISAR_repo_nao_casou"
                item["fix_candidatos"] = [f"{r} @ {c}" for r, c in cands]
                stats["ok_repo" if repo_casou else "ok_revisar"] += 1
                print(f"{prefixo} -> {commit[:12]} ({'repo ok' if repo_casou else 'REVISAR'})")
                achou = True
                break
            if so_versao:
                item["fix_status"] = "so_versao_sem_commit"
                item["fix_candidatos"] = []
                stats["so_versao"] += 1
                print(f"{prefixo} -> OSV só tem versão, sem commit (manual)")
                achou = True
                break

        if not achou:
            item["fix_status"] = "nao_encontrado_osv"
            stats["nao_achou"] += 1
            print(f"{prefixo} -> não encontrado na OSV (manual via GHSA)")

    with open(FIXES_FILE, "w", encoding="utf-8") as f:
        json.dump(fixes, f, indent=2, ensure_ascii=False)

    print("\n=== RESUMO ===")
    print(f"  já preenchidos (pulados)      : {stats['ja_tinha']}")
    print(f"  preenchidos (repo casou)      : {stats['ok_repo']}")
    print(f"  preenchidos (REVISAR repo)    : {stats['ok_revisar']}")
    print(f"  só versão, sem commit (manual): {stats['so_versao']}")
    print(f"  sem CVE id (manual)           : {stats['sem_cve']}")
    print(f"  não achou na OSV (manual)     : {stats['nao_achou']}")
    auto = stats['ok_repo'] + stats['ok_revisar']
    print(f"\n[+] Preenchidos automaticamente: {auto}. Arquivo: {FIXES_FILE}")
    print("[+] Revise os marcados 'REVISAR' e resolva os 'manual' antes de tp_reconstruct.py")


def selftest():
    """Valida a extração sem internet, com um registro OSV de exemplo."""
    exemplo = {
        "id": "GHSA-xxxx",
        "aliases": ["CVE-2025-0001"],
        "affected": [{
            "package": {"name": "github.com/argoproj/argo-cd", "ecosystem": "Go"},
            "ranges": [
                {"type": "SEMVER", "events": [{"introduced": "0"}, {"fixed": "2.11.0"}]},
                {"type": "GIT", "repo": "https://github.com/argoproj/argo-cd",
                 "events": [{"introduced": "0"}, {"fixed": "abc123def456"}]},
            ],
        }],
    }
    commit, cands, so_versao, repo_casou = extrai_fix_commits(exemplo, "argoproj/argo-cd")
    print("=== SELFTEST (sem rede) ===")
    print(f"  commit extraído : {commit}     (esperado: abc123def456)")
    print(f"  repo casou?     : {repo_casou} (esperado: True)")
    print(f"  candidatos      : {cands}")
    print(f"  tinha só versão : {so_versao} (esperado: True, pelo range SEMVER)")
    ok = commit == "abc123def456" and repo_casou and so_versao
    print(f"\n  {'PASSOU (OK)' if ok else 'FALHOU'}")


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        selftest()
    else:
        preencher()
