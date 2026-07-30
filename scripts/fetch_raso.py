"""
fetch_raso.py — baixa só os commits necessários para reconstruir pares TP.

`tp_reconstruct.py` precisa de histórico git (`git diff parent..fix` e
`git show <ref>:<arquivo>`), mas só de DOIS commits por CVE: o commit do fix e
o seu pai. Clonar o repositório inteiro para isso custa GBs; um fetch raso
custa dezenas de MB.

Para cada repo cria um esqueleto git em repos/<repo_dir> e faz
`git fetch --depth 2 origin <fix_commit>` para cada CVE daquele repo. Não faz
checkout: a working tree fica vazia, o que basta porque tp_reconstruct lê tudo
do object database.

Depois de rodar o tp_reconstruct e o preencher_cache.py, esses esqueletos podem
ser apagados — os arquivos-alvo já estarão em cache/.

USO
  python scripts/fetch_raso.py --input data/tp_fixes_osv.json
  python scripts/fetch_raso.py --input data/tp_fixes_osv.json --dry-run
"""
import argparse
import json
import os
import subprocess

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPOS = os.path.join(BASE, "repos")

# 2 = o commit do fix e o pai dele, que é exatamente o par que precisamos.
PROFUNDIDADE = 2
TIMEOUT = 300


def git(*args, cwd=None, timeout=TIMEOUT):
    """Roda git e devolve (rc, stderr). Timeout vira falha comum (rc 124) para
    que um repo lento não derrube a coleta inteira."""
    try:
        r = subprocess.run(["git", *args], cwd=cwd, capture_output=True,
                           timeout=timeout)
    except subprocess.TimeoutExpired:
        return 124, f"timeout apos {timeout}s"
    return r.returncode, r.stderr.decode("utf-8", "ignore").strip()


def preparar_esqueleto(destino, url):
    """git init + remote, sem baixar nada ainda."""
    if not os.path.isdir(os.path.join(destino, ".git")):
        os.makedirs(destino, exist_ok=True)
        rc, err = git("init", "-q", cwd=destino)
        if rc != 0:
            return f"git init falhou: {err[:120]}"
        rc, err = git("remote", "add", "origin", url, cwd=destino)
        if rc != 0:
            return f"remote add falhou: {err[:120]}"
    return None


def tem_commit(destino, sha):
    rc, _ = git("cat-file", "-e", f"{sha}^{{commit}}", cwd=destino)
    return rc == 0


def main():
    ap = argparse.ArgumentParser(description="Fetch raso dos commits de fix.")
    ap.add_argument("--input", default="data/tp_fixes_osv.json",
                    help="Manifesto de fixes (default: data/tp_fixes_osv.json).")
    ap.add_argument("--dry-run", action="store_true",
                    help="Só lista o que baixaria.")
    ap.add_argument("--depth", type=int, default=PROFUNDIDADE,
                    help=f"Profundidade do fetch (default {PROFUNDIDADE}).")
    args = ap.parse_args()

    caminho = args.input
    if not os.path.isabs(caminho):
        caminho = os.path.join(BASE, caminho)
    with open(caminho, encoding="utf-8") as f:
        fixes = json.load(f)

    # repo_dir -> (url, [fix_commits])
    info = {}
    for it in fixes:
        fc = (it.get("fix_commit") or "").strip()
        if not fc:
            continue
        rd = it["repo_dir"]
        info.setdefault(rd, [it.get("repo_url"), []])
        if fc not in info[rd][1]:
            info[rd][1].append(fc)

    total_commits = sum(len(v[1]) for v in info.values())
    print(f"[+] Repos: {len(info)} | commits de fix a buscar: {total_commits}")
    print(f"[+] Profundidade: {args.depth} (fix + pai)\n")

    if args.dry_run:
        for rd, (url, commits) in sorted(info.items()):
            print(f"  {rd:38} {len(commits)} commit(s)  <- {url}")
        return

    ok_repo, falhas, ja = 0, [], 0
    for i, (rd, (url, commits)) in enumerate(sorted(info.items()), 1):
        destino = os.path.join(REPOS, rd)
        if not url:
            falhas.append((rd, "sem repo_url"))
            continue

        erro = preparar_esqueleto(destino, url)
        if erro:
            falhas.append((rd, erro))
            continue

        obtidos = 0
        for sha in commits:
            if tem_commit(destino, sha):
                ja += 1
                obtidos += 1
                continue
            rc, err = git("fetch", "--depth", str(args.depth), "-q",
                          "origin", sha, cwd=destino)
            if rc == 0 and tem_commit(destino, sha):
                obtidos += 1
            else:
                falhas.append((f"{rd}@{sha[:10]}", err[:100] or "commit inacessível"))

        if obtidos:
            ok_repo += 1
        print(f"  [{i:2}/{len(info)}] {rd:38} {obtidos}/{len(commits)} commits")

    print("\n=== RESUMO ===")
    print(f"  repos com ao menos 1 commit : {ok_repo}/{len(info)}")
    print(f"  commits já presentes        : {ja}")
    print(f"  falhas                      : {len(falhas)}")
    for nome, err in falhas[:15]:
        print(f"    [x] {nome}: {err}")
    if len(falhas) > 15:
        print(f"    ... e mais {len(falhas)-15}")

    rel = args.input.replace(os.sep, "/")
    print(f"\n[+] Próximo: python scripts/tp_reconstruct.py --input {rel}")


if __name__ == "__main__":
    main()
