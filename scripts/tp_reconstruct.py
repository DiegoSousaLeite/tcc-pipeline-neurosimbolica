"""
tp_reconstruct.py — Reconstrução de TPs pela Opção C (pares diferenciais).

Para cada CVE, extrai a função alterada pelo fix em DUAS versões:
  - VULNERÁVEL  = estado no commit-PAI do fix (antes da correção)
  - CORRIGIDA   = estado no commit do fix (depois da correção)
O diff do fix é o gabarito: o LLM deve marcar a vulnerável como TP e liberar a
corrigida como TN. Opcionalmente roda o Semgrep no estado vulnerável e registra
se o alerta "passou no SAST" (TP de pipeline real) ou não (ponto cego do SAST).

NÃO altera a working tree dos repos: usa `git show ref:arquivo` para ler cada
versão direto do object database.

USO
  1) Gerar o esqueleto a preencher (lê o dataset, lista os 36 TPs):
       python scripts/tp_reconstruct.py --init
     Depois, preencha o campo "fix_commit" de cada CVE em tp_fixes.json
     (hash do commit que corrigiu o CVE — via CVEFixes original ou o
     GitHub Security Advisory do CVE).

  2) Reconstruir os pares (após preencher os fix_commit):
       python scripts/tp_reconstruct.py
       python scripts/tp_reconstruct.py --sast --sast-config p/go
     Saída: tp_pairs.json (pronto para alimentar o LLM).
"""
import argparse
import json
import os
import re
import subprocess
import sys
import tempfile

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPOS = os.path.join(BASE, "repos")
DATASET = os.path.join(BASE, "data", "dataset_go_limpo.json")
FIXES_FILE = os.path.join(BASE, "data", "tp_fixes.json")
OUT_FILE = os.path.join(BASE, "tp_pairs.json")

# Marcador gravado pelo osv_harvest_go.py quando o advisory não traz CWE.
CWE_DESCONHECIDA = "CWE-desconhecida"
SEMGREP = os.environ.get(
    "SEMGREP_BIN",
    r"C:\Users\Soous\AppData\Local\Programs\Python\Python314\Scripts\semgrep.exe",
)


def git(repo, *args, timeout=120):
    """Roda git no repo e devolve (rc, stdout, stderr) como texto."""
    r = subprocess.run(["git", *args], cwd=repo, capture_output=True, timeout=timeout)
    return (r.returncode,
            r.stdout.decode("utf-8", "ignore"),
            r.stderr.decode("utf-8", "ignore"))


# --------------------------------------------------------------------------- #
# 1) --init : gera o esqueleto tp_fixes.json a partir do dataset
# --------------------------------------------------------------------------- #
def init_skeleton():
    d = json.load(open(DATASET, encoding="utf-8"))
    tps = [r for r in d if r["ground_truth"] == "true_positive"]
    skeleton = []
    for r in tps:
        cves = r["metadata"].get("cve_ids") or []
        skeleton.append({
            "repo_name": r["repo_name"],
            "repo_dir": r["repo_name"].split("/")[-1],
            "cwe_id": r["metadata"]["cwe_id"],
            "cve_ids": cves,
            "commit_dataset": r["commit_hash"],   # commit (errado) do dataset, p/ referência
            "fix_commit": "",                     # << VOCÊ PREENCHE: hash do commit que corrigiu o CVE
        })
    with open(FIXES_FILE, "w", encoding="utf-8") as f:
        json.dump(skeleton, f, indent=2, ensure_ascii=False)
    print(f"[+] Esqueleto gerado: {FIXES_FILE}")
    print(f"[+] {len(skeleton)} TPs. Preencha 'fix_commit' de cada um e rode sem --init.")
    repos = sorted({s['repo_dir'] for s in skeleton})
    print(f"[+] Repos envolvidos ({len(repos)}): {', '.join(repos)}")


# --------------------------------------------------------------------------- #
# 2) Reconstrução dos pares
# --------------------------------------------------------------------------- #
HUNK_RE = re.compile(r"^@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@(.*)$")


def arquivos_e_funcoes_do_fix(repo, fix, parent):
    """Lê o diff fix^..fix e devolve [(arquivo, func_hint, linha_pai, linha_fix)]."""
    rc, out, err = git(repo, "diff", parent, fix, "--", "*.go")
    if rc != 0:
        return [], f"diff falhou: {err[:160]}"

    alvos, arquivo = [], None
    for ln in out.splitlines():
        if ln.startswith("+++ b/"):
            arquivo = ln[6:].strip()
        m = HUNK_RE.match(ln)
        if m and arquivo:
            l_pai = int(m.group(1))
            l_fix = int(m.group(2))
            hint = m.group(3).strip()  # git costuma colocar a assinatura da func aqui
            alvos.append((arquivo, hint, l_pai, l_fix))
    return alvos, None


def conteudo(repo, ref, path):
    """Retorna as linhas do arquivo no ref (ou None se não existir)."""
    rc, out, _ = git(repo, "show", f"{ref}:{path}")
    return out.splitlines() if rc == 0 else None


def nome_funcao(codigo):
    """Extrai o nome da função Go da assinatura (1a linha 'func ...')."""
    m = re.search(r"^func\s+(?:\([^)]*\)\s+)?(\w+)", codigo.lstrip(), re.M)
    return m.group(1) if m else None


def funcoes_do_dataset_por_cve():
    """Mapa cve_id -> set de nomes de função que o dataset marcou como a CWE
    (usado para filtrar os pares aos que realmente são a vulnerabilidade)."""
    d = json.load(open(DATASET, encoding="utf-8"))
    mapa = {}
    for r in d:
        if r["ground_truth"] != "true_positive":
            continue
        nomes = set()
        for loc in r["to_analyzer"].get("locations", []):
            fn = (loc.get("function") or "").strip()
            if fn and fn != "FILE_SCOPE":
                nomes.add(fn.lower())
        for cve in (r["metadata"].get("cve_ids") or []):
            mapa.setdefault(cve, set()).update(nomes)
    return mapa


def extrai_funcao(linhas, alvo_idx):
    """Extrai a função Go que contém a linha alvo (1-based).
    Sobe até um 'func ...' e faz balanceamento de chaves. Fallback: janela ±25.
    """
    if not linhas:
        return None
    i = min(max(alvo_idx - 1, 0), len(linhas) - 1)
    # sobe ate achar a assinatura da funcao
    inicio = None
    for j in range(i, -1, -1):
        if linhas[j].lstrip().startswith("func "):
            inicio = j
            break
    if inicio is None:
        ini = max(0, i - 25)
        fim = min(len(linhas), i + 25)
        return {"metodo": "janela", "linha_inicio": ini + 1, "linha_fim": fim,
                "codigo": "\n".join(linhas[ini:fim])}
    # balanceia chaves a partir do inicio
    saldo, fim = 0, None
    viu_abre = False
    for j in range(inicio, len(linhas)):
        saldo += linhas[j].count("{") - linhas[j].count("}")
        if "{" in linhas[j]:
            viu_abre = True
        if viu_abre and saldo <= 0:
            fim = j
            break
    if fim is None:
        fim = min(len(linhas), inicio + 60)
    return {"metodo": "funcao", "linha_inicio": inicio + 1, "linha_fim": fim + 1,
            "codigo": "\n".join(linhas[inicio:fim + 1])}


def roda_semgrep_no_vulneravel(repo, path, linhas_vuln, func_ini, func_fim, config):
    """Extrai o arquivo vulnerável para um temp e roda o Semgrep. Retorna
    (passou_no_sast: bool|None, linhas_alertadas, status)."""
    if linhas_vuln is None:
        return None, [], "arquivo_inexistente_no_pai"
    tmpdir = tempfile.mkdtemp(prefix="tp_sast_")
    tmp = os.path.join(tmpdir, os.path.basename(path))
    with open(tmp, "w", encoding="utf-8") as f:
        f.write("\n".join(linhas_vuln))
    try:
        # PYTHONIOENCODING=utf-8 evita o crash do banner com emoji no console
        # cp1252 do Windows (causa do antigo 'rc7'); --quiet tira o banner.
        env = dict(os.environ, PYTHONIOENCODING="utf-8")
        r = subprocess.run([SEMGREP, "--config", config, "--json", "--quiet", tmp],
                           capture_output=True, timeout=240, env=env)
        data = json.loads(r.stdout.decode("utf-8", "ignore") or "{}")
        alertadas = [x["start"]["line"] for x in data.get("results", [])]
        if not data.get("results") and r.returncode not in (0, 1):
            return None, [], f"semgrep_erro_rc{r.returncode}"
        # passou no SAST se algum alerta cai dentro da funcao vulneravel
        passou = any(func_ini <= ln <= func_fim for ln in alertadas)
        return passou, alertadas, "ok"
    except subprocess.TimeoutExpired:
        return None, [], "semgrep_timeout"
    except Exception as e:
        return None, [], f"semgrep_falha:{str(e)[:80]}"


def reconstruir(usar_sast, sast_config, filtrar_dataset=True, incluir_janela=False,
                max_funcs=8):
    if not os.path.exists(FIXES_FILE):
        print(f"[ERRO] {FIXES_FILE} não existe. Rode com --init primeiro.")
        sys.exit(1)
    fixes = json.load(open(FIXES_FILE, encoding="utf-8"))
    mapa_funcs = funcoes_do_dataset_por_cve() if filtrar_dataset else {}

    pares, sem_fix, falhas = [], 0, 0
    vistos = set()          # dedup por (repo, arquivo, função)
    descartados = 0         # janela e/ou funções fora do que o dataset marcou
    sem_cwe = 0             # advisory da OSV sem CWE — inútil para a Fase 1
    for item in fixes:
        fix = (item.get("fix_commit") or "").strip()
        repo_dir = item["repo_dir"]
        repo = os.path.join(REPOS, repo_dir)
        if not fix:
            sem_fix += 1
            continue
        # A Fase 1 casa o alerta pela tag de CWE. Sem CWE o caso só produziria
        # NAO_DETECTADO e entraria na matriz de cobertura como ponto cego
        # artificial — lacuna do metadado, não limitação do Semgrep.
        if (item.get("cwe_id") or CWE_DESCONHECIDA) == CWE_DESCONHECIDA:
            sem_cwe += 1
            continue
        if not os.path.isdir(repo):
            print(f"  [!] repo não clonado: {repo_dir} (pulando {item.get('cve_ids')})")
            falhas += 1
            continue

        rc, parent, err = git(repo, "rev-parse", f"{fix}^")
        parent = parent.strip()
        if rc != 0:
            print(f"  [!] não achei o pai de {fix[:10]} em {repo_dir}: {err[:80]}")
            falhas += 1
            continue

        alvos, erro = arquivos_e_funcoes_do_fix(repo, fix, parent)
        if erro:
            print(f"  [!] {repo_dir} {fix[:10]}: {erro}")
            falhas += 1
            continue

        # funções que o dataset marca como a CWE deste item (vazio para OSV)
        esperadas = set()
        if filtrar_dataset:
            for cve in (item.get("cve_ids") or []):
                esperadas |= mapa_funcs.get(cve, set())

        # 1a passada: coleta candidatos (sem SAST ainda)
        candidatos_item = []
        for arquivo, hint, l_pai, l_fix in alvos:
            if arquivo.endswith("_test.go"):
                continue
            linhas_vuln = conteudo(repo, parent, arquivo)
            linhas_fix = conteudo(repo, fix, arquivo)
            f_vuln = extrai_funcao(linhas_vuln, l_pai)
            f_fix = extrai_funcao(linhas_fix, l_fix)
            if not f_vuln or not f_fix:
                continue
            if f_vuln["codigo"].strip() == f_fix["codigo"].strip():
                continue  # função não mudou de verdade -> ignora
            if f_vuln["metodo"] == "janela" and not incluir_janela:
                descartados += 1
                continue
            fnome = nome_funcao(f_vuln["codigo"]) or hint
            # Precisão (dataset): mantém só as funções nomeadas pela base, se houver
            if esperadas and (not fnome or fnome.lower() not in esperadas):
                descartados += 1
                continue
            chave = (repo_dir, arquivo, (fnome or "").lower())
            if chave in vistos:
                continue  # mesma função já capturada por outro hunk
            vistos.add(chave)
            candidatos_item.append((arquivo, fnome, hint, f_vuln, f_fix, linhas_vuln))

        # Guard anti-refactor: sem funções nomeadas pelo dataset, um fix que mexe
        # em MUITAS funções é refactor -> não dá p/ cravar a vuln. Descarta o item.
        if max_funcs and not esperadas and len(candidatos_item) > max_funcs:
            descartados += len(candidatos_item)
            continue

        # 2a passada: monta o registro (e roda SAST só nos que ficaram)
        for arquivo, fnome, hint, f_vuln, f_fix, linhas_vuln in candidatos_item:
            registro = {
                "repo": item["repo_name"],
                "cwe_id": item["cwe_id"],
                "cve_ids": item["cve_ids"],
                "fix_commit": fix,
                "parent_commit": parent,
                "arquivo": arquivo,
                "funcao": fnome,
                "func_hint": hint,
                "vulneravel": f_vuln,    # gabarito = true_positive
                "corrigido": f_fix,      # gabarito = false_positive (seguro)
            }
            if usar_sast:
                passou, alertadas, status = roda_semgrep_no_vulneravel(
                    repo, arquivo, linhas_vuln,
                    f_vuln["linha_inicio"], f_vuln["linha_fim"], sast_config)
                registro["passou_no_sast"] = passou
                registro["sast_linhas_alertadas"] = alertadas
                registro["sast_status"] = status
            pares.append(registro)

    with open(OUT_FILE, "w", encoding="utf-8") as f:
        json.dump(pares, f, indent=2, ensure_ascii=False)

    print("\n=== RESUMO DA RECONSTRUÇÃO ===")
    print(f"  CVEs sem fix_commit preenchido : {sem_fix}")
    print(f"  CVEs sem CWE no advisory        : {sem_cwe}")
    print(f"  Falhas de reconstrução          : {falhas}")
    print(f"  Descartados (janela/fora do dataset): {descartados}")
    print(f"  Pares diferenciais reconstruídos: {len(pares)}")
    if usar_sast and pares:
        passou = sum(1 for p in pares if p.get("passou_no_sast") is True)
        nao = sum(1 for p in pares if p.get("passou_no_sast") is False)
        print(f"    -> passaram no SAST (TP pipeline real): {passou}")
        print(f"    -> NÃO passaram (ponto cego/sonda)    : {nao}")
    print(f"\n[+] Saída: {OUT_FILE}")


def main():
    ap = argparse.ArgumentParser(description="Reconstrução de TPs (Opção C).")
    ap.add_argument("--init", action="store_true",
                    help="Gera tp_fixes.json (esqueleto a preencher).")
    ap.add_argument("--sast", action="store_true",
                    help="Roda o Semgrep no estado vulnerável e registra se passou no SAST.")
    ap.add_argument("--sast-config", default="p/golang",
                    help="Config/ruleset do Semgrep (default: p/golang; ou um caminho local de regras .yaml).")
    ap.add_argument("--todas-funcoes", action="store_true",
                    help="Não filtrar pelas funções que o dataset marcou (mantém todas as alteradas).")
    ap.add_argument("--incluir-janela", action="store_true",
                    help="Inclui pares cuja extração caiu no fallback de janela (menos preciso).")
    ap.add_argument("--max-funcs-por-fix", type=int, default=8,
                    help="Descarta CVEs (sem função nomeada pelo dataset) cujo fix mexe em mais que N funções (refactor). 0 desliga.")
    ap.add_argument("--input", default=None,
                    help="Lista de fixes alternativa (ex.: tp_fixes_osv.json). "
                         "A saída vira tp_pairs_<nome>.json.")
    args = ap.parse_args()

    if args.input:
        global FIXES_FILE, OUT_FILE
        input_path = args.input
        if not os.path.isabs(input_path):
            input_path = os.path.join(BASE, input_path)
        FIXES_FILE = input_path
        sufixo = os.path.splitext(os.path.basename(args.input))[0].replace("tp_fixes", "").strip("_")
        OUT_FILE = os.path.join(BASE, f"tp_pairs_{sufixo}.json" if sufixo else "tp_pairs.json")

    if args.init:
        init_skeleton()
    else:
        reconstruir(args.sast, args.sast_config,
                    filtrar_dataset=not args.todas_funcoes,
                    incluir_janela=args.incluir_janela,
                    max_funcs=args.max_funcs_por_fix)


if __name__ == "__main__":
    main()
