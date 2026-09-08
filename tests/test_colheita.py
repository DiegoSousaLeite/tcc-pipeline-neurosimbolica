"""Testes da decisão da colheita (`scripts/osv_harvest_go.py`).

A colheita real depende de rede, de um dump de dezenas de MB e de dezenas de
minutos — nada disso cabe numa suíte. O que precisa de teste é a **decisão**:
aceitar, recusar, e qual CWE registrar. Ela é testável com vulnerabilidade
sintética e ruleset sintético, o mesmo padrão de `tests/test_pareamento.py`, que
testa a decisão da Fase 1 sobre SARIF sintético sem invocar o Semgrep.

O ruleset daqui é sintético de propósito: um teste contra o `p/default` real
passaria a medir o catálogo do registry — que muda sem aviso — em vez do filtro.
"""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.osv_harvest_go import SEM_CWE, extrai  # noqa: E402

# Alcançáveis em Go: 338 e 327. CWE-284 (controle de acesso) não é coberta por
# regra alguma — é justamente o perfil das CVEs de Go que o filtro recusa.
RULESET = {
    "rules": [
        {"id": "go.rand", "languages": ["go"],
         "metadata": {"cwe": ["CWE-338: Use of Cryptographically Weak PRNG"]}},
        {"id": "go.md5", "languages": ["go"],
         "metadata": {"cwe": "CWE-327: Use of a Broken Crypto Algorithm"}},
        {"id": "py.xss", "languages": ["python"],
         "metadata": {"cwe": ["CWE-79: Cross-site Scripting"]}},
    ]
}

REPO = "https://github.com/exemplo/servico"
FIX = "0123456789abcdef0123456789abcdef01234567"


@pytest.fixture
def catalogo(tmp_path):
    caminho = tmp_path / "_regras_sintetico.json"
    caminho.write_text(json.dumps(RULESET), encoding="utf-8")
    return str(caminho)


def _vuln(cwes, repo=REPO, fixed=FIX, tipo="GIT"):
    """Vulnerabilidade da OSV reduzida ao que a colheita lê."""
    ranges = []
    if repo is not None:
        eventos = [{"introduced": "0"}] + ([{"fixed": fixed}] if fixed else [])
        ranges = [{"type": tipo, "repo": repo, "events": eventos}]
    vuln = {"id": "GHSA-teste", "affected": [{"ranges": ranges}]}
    if cwes is not None:
        vuln["database_specific"] = {"cwe_ids": cwes}
    return vuln


def test_cwe_alcancavel_e_aceita(catalogo):
    ext = extrai(_vuln(["CWE-338"]), catalogo=catalogo)
    assert ext.fix_commit == FIX
    assert ext.repo_url == REPO
    assert ext.cwe == "CWE-338"
    assert ext.inalcancaveis == ()


def test_cwe_inalcancavel_e_recusada(catalogo):
    """CWE-284 é o perfil dominante das CVEs de Go e não tem regra no ruleset."""
    ext = extrai(_vuln(["CWE-284"]), catalogo=catalogo)
    assert ext.fix_commit is None
    assert ext.cwe is None
    assert ext.inalcancaveis == ("CWE-284",)


def test_cwe_de_outra_linguagem_nao_torna_alcancavel(catalogo):
    """A regra de CWE-79 é de Python; nenhuma dispara sobre um arquivo `.go`."""
    ext = extrai(_vuln(["CWE-79"]), catalogo=catalogo)
    assert ext.fix_commit is None
    assert ext.inalcancaveis == ("CWE-79",)


def test_segunda_cwe_alcancavel_e_a_registrada(catalogo):
    """A ordem de `cwe_ids` é arbitrária, e a CWE registrada é a que casou.

    Ficar com `cwes[0]`, como antes, recusaria a candidata por acidente de
    listagem — e registrar CWE-284 faria a Fase 1 procurar a fraqueza errada.
    """
    ext = extrai(_vuln(["CWE-284", "CWE-338"]), catalogo=catalogo)
    assert ext.fix_commit == FIX
    assert ext.cwe == "CWE-338"


def test_nenhuma_cwe_alcancavel_entre_varias_e_recusa(catalogo):
    ext = extrai(_vuln(["CWE-284", "CWE-862", "CWE-863"]), catalogo=catalogo)
    assert ext.fix_commit is None
    assert ext.inalcancaveis == ("CWE-284", "CWE-862", "CWE-863")


def test_sem_cwe_declarada_e_recusa(catalogo):
    """Antes virava `CWE-desconhecida` e entrava na população mesmo assim."""
    for vuln in (_vuln(None), _vuln([])):
        ext = extrai(vuln, catalogo=catalogo)
        assert ext.fix_commit is None
        assert ext.cwe is None
        assert ext.inalcancaveis == (SEM_CWE,)


def test_sem_commit_de_fix_continua_recusada(catalogo):
    """Filtro pré-existente: CWE alcançável não basta sem commit de fix."""
    ext = extrai(_vuln(["CWE-338"], fixed=None), catalogo=catalogo)
    assert ext.fix_commit is None
    assert ext.cwe == "CWE-338"
    # A recusa não é por inalcançabilidade: contá-la ali confundiria o relatório.
    assert ext.inalcancaveis == ()


def test_repo_fora_do_github_continua_recusado(catalogo):
    ext = extrai(_vuln(["CWE-338"], repo="https://gitlab.com/exemplo/servico"),
                 catalogo=catalogo)
    assert ext.fix_commit is None
    assert ext.inalcancaveis == ()


def test_range_nao_git_continua_recusado(catalogo):
    ext = extrai(_vuln(["CWE-338"], tipo="SEMVER"), catalogo=catalogo)
    assert ext.fix_commit is None
    assert ext.inalcancaveis == ()


def test_vulnerabilidade_ausente_nao_conta_recusa(catalogo):
    """A consulta à OSV pode falhar; isso não é recusa por inalcançabilidade."""
    ext = extrai(None, catalogo=catalogo)
    assert ext == (None, None, None, ())


def test_sufixo_git_e_barra_final_saem_da_url(catalogo):
    ext = extrai(_vuln(["CWE-327"], repo=REPO + ".git/"), catalogo=catalogo)
    assert ext.repo_url == REPO
    assert ext.cwe == "CWE-327"
