"""
fonte.py — resolve o arquivo-alvo de um caso, com cache local imutável.

Por caso, a pipeline consome UM arquivo .go em UM commit: a Fase 1 passa esse
caminho ao Semgrep (que roda sobre o arquivo isolado) e a Fase 2 relê o mesmo
arquivo para hidratar a função. Clonar o histórico completo do repositório
para isso é desperdício: um clone do cilium custa ~1 GB para entregar ~20 KB.

Ordem de resolução (a primeira que funcionar vence):
  1. cache/  — já resolvido antes; chave imutável (repo + commit + arquivo)
  2. repos/  — clone existente: `git show <commit>:<arquivo>`, sem checkout e
               sem tocar na working tree
  3. rede    — raw.githubusercontent.com no commit exato

Como a chave é imutável (commit é um SHA), o cache nunca invalida: uma vez
preenchido, a pipeline roda offline e o experimento fica reproduzível a partir
de alguns MB versionáveis, em vez de dezenas de GB de clones.
"""
import hashlib
import logging
import os
import subprocess
import time

import requests

from .config import CACHE_DIR, REPOS_DIR

log = logging.getLogger(__name__)

# raw.githubusercontent.com não exige autenticação para repositório público,
# mas um token eleva o limite de requisições se a coleta for longa.
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
FETCH_TIMEOUT = int(os.environ.get("FETCH_TIMEOUT", "30"))
_RETRY_DELAYS = [3, 10]

# Windows resolve mal caminhos acima de ~260 chars; abaixo disso preservamos a
# estrutura de diretórios do repo (legível e versionável).
_LIMITE_CAMINHO = 240


class FetchError(Exception):
    """Não foi possível obter o arquivo (rede, git ou repositório inválido)."""


class ArquivoInexistente(Exception):
    """O arquivo não existe nesse commit (404 / caminho ausente na árvore)."""


def _slug_repo(repo_name: str) -> str:
    """'argoproj/argo-cd' -> 'argoproj__argo-cd'."""
    return repo_name.replace("/", "__")


def caminho_cache(repo_name: str, commit: str, arquivo: str) -> str:
    """Caminho determinístico do arquivo no cache.

    Preserva a estrutura de diretórios do repo. Se o caminho resultante ficar
    longo demais para o Windows, achata o diretório num hash — a extensão é
    mantida em qualquer caso, porque o Semgrep infere a linguagem por ela.
    """
    raiz = os.path.join(CACHE_DIR, _slug_repo(repo_name), commit[:12])
    caminho = os.path.join(raiz, arquivo.replace("/", os.sep))
    if len(caminho) <= _LIMITE_CAMINHO:
        return caminho
    dig = hashlib.sha1(arquivo.encode("utf-8")).hexdigest()[:10]
    return os.path.join(raiz, f"{dig}__{os.path.basename(arquivo)}")


def _gravar(destino: str, conteudo: bytes):
    os.makedirs(os.path.dirname(destino), exist_ok=True)
    with open(destino, "wb") as f:
        f.write(conteudo)


def _do_clone_local(repo_name: str, commit: str, arquivo: str) -> bytes | None:
    """Lê o arquivo de um clone existente via `git show`, sem checkout.

    Devolve None se não há clone, se o commit não está presente ou se o arquivo
    não existe nessa árvore — todos casos em que vale tentar a rede.
    """
    repo_dir = os.path.join(REPOS_DIR, repo_name.split("/")[-1])
    if not os.path.isdir(os.path.join(repo_dir, ".git")):
        return None
    res = subprocess.run(
        ["git", "-C", repo_dir, "show", f"{commit}:{arquivo}"],
        capture_output=True,
    )
    return res.stdout if res.returncode == 0 else None


def _da_rede(repo_name: str, commit: str, arquivo: str) -> bytes:
    """Baixa o arquivo no commit exato via raw.githubusercontent.com."""
    url = f"https://raw.githubusercontent.com/{repo_name}/{commit}/{arquivo}"
    headers = {"Authorization": f"Bearer {GITHUB_TOKEN}"} if GITHUB_TOKEN else {}

    ultimo = None
    for tentativa, delay in enumerate([0] + _RETRY_DELAYS):
        if delay:
            time.sleep(delay)
        try:
            r = requests.get(url, headers=headers, timeout=FETCH_TIMEOUT)
        except requests.RequestException as e:
            ultimo = str(e)
            continue
        if r.status_code == 200:
            return r.content
        if r.status_code == 404:
            raise ArquivoInexistente(
                f"{arquivo} não existe em {repo_name}@{commit[:10]}")
        # 403/429 (rate limit) e 5xx valem retry
        ultimo = f"HTTP {r.status_code}"
    raise FetchError(f"Falha ao baixar {url}: {ultimo}")


def obter_arquivo(repo_name: str, commit: str, arquivo: str) -> str:
    """Garante o arquivo em disco e devolve seu caminho absoluto.

    Levanta ArquivoInexistente se o arquivo não existe nesse commit, e
    FetchError para falhas de esteira (rede indisponível, rate limit).
    """
    destino = caminho_cache(repo_name, commit, arquivo)
    if os.path.exists(destino):
        return destino

    conteudo = _do_clone_local(repo_name, commit, arquivo)
    origem = "clone local"
    if conteudo is None:
        conteudo = _da_rede(repo_name, commit, arquivo)
        origem = "rede"

    _gravar(destino, conteudo)
    log.info("    -> arquivo obtido (%s): %s", origem, arquivo)
    return destino


def estatisticas_cache() -> tuple[int, int]:
    """(quantidade de arquivos, bytes totais) no cache."""
    n = total = 0
    for raiz, _, arquivos in os.walk(CACHE_DIR):
        for a in arquivos:
            n += 1
            total += os.path.getsize(os.path.join(raiz, a))
    return n, total
