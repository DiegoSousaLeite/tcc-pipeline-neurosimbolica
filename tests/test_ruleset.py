"""Testes da consulta de alcançabilidade (`src/ruleset.py`).

O ruleset destes testes é sintético, não um recorte do `p/default`: o que precisa
ser fixado são os casos-limite — `metadata.cwe` como string única, prefixo de CWE,
zeros à esquerda, tag sem CWE alguma —, e o catálogo real não garante conter todos
nem manter os que contém. Um teste que dependesse do registry passaria a medir a
rede em vez da decisão.
"""
import json

import pytest

from src import ruleset
from src.ruleset import RulesetIndisponivelError, carregar_regras, cwe_alcancavel, cwes_alcancaveis

# Uma regra por caso-limite. `cwe` alterna entre lista e string única de
# propósito: as duas formas ocorrem no registry (959 listas contra 85 strings).
RULESET = {
    "rules": [
        {"id": "go.rand", "languages": ["go"],
         "metadata": {"cwe": ["CWE-338: Use of Cryptographically Weak PRNG"]}},
        {"id": "go.md5", "languages": ["go"],
         "metadata": {"cwe": "CWE-327: Use of a Broken Crypto Algorithm"}},
        {"id": "go.zeros", "languages": ["go"],
         "metadata": {"cwe": ["CWE-077: Command Injection"]}},
        {"id": "go.limite", "languages": ["go"],
         "metadata": {"cwe": ["CWE-770: Allocation Without Limits"]}},
        {"id": "go.sem_cwe", "languages": ["go"],
         "metadata": {"category": "best-practice"}},
        {"id": "go.tag_livre", "languages": ["go"],
         "metadata": {"cwe": ["nada de identificador aqui"]}},
        {"id": "py.xss", "languages": ["python"],
         "metadata": {"cwe": ["CWE-79: Cross-site Scripting"]}},
        {"id": "multi.ssrf", "languages": ["python", "go"],
         "metadata": {"cwe": ["CWE-918: Server-Side Request Forgery"]}},
    ]
}


@pytest.fixture
def catalogo(tmp_path):
    caminho = tmp_path / "_regras_sintetico.json"
    caminho.write_text(json.dumps(RULESET), encoding="utf-8")
    return str(caminho)


def test_carregar_preserva_linguagens(catalogo):
    """`languages` era descartado no carregamento antigo — é ele que decide."""
    regras = carregar_regras(catalogo)
    assert regras["multi.ssrf"].linguagens == ["python", "go"]
    assert regras["go.rand"].cwes == ["CWE-338: Use of Cryptographically Weak PRNG"]


def test_cwe_da_linguagem_e_alcancavel(catalogo):
    assert 338 in cwes_alcancaveis("go", catalogo)
    assert cwe_alcancavel("CWE-338", "go", catalogo)


def test_cwe_de_outra_linguagem_nao_e_alcancavel(catalogo):
    """Nenhuma regra de Python dispara sobre um arquivo `.go`."""
    assert not cwe_alcancavel("CWE-79", "go", catalogo)
    assert cwe_alcancavel("CWE-79", "python", catalogo)


def test_mesma_cwe_difere_por_linguagem(catalogo):
    assert cwe_alcancavel("CWE-327", "go", catalogo)
    assert not cwe_alcancavel("CWE-327", "python", catalogo)


def test_regra_multilingue_vale_para_as_duas(catalogo):
    assert cwe_alcancavel("CWE-918", "go", catalogo)
    assert cwe_alcancavel("CWE-918", "python", catalogo)


def test_metadata_cwe_como_string_unica(catalogo):
    """Iterar a string percorreria CARACTERES e nenhuma CWE seria extraída."""
    assert 327 in cwes_alcancaveis("go", catalogo)


def test_prefixo_de_cwe_nao_casa(catalogo):
    """O catálogo só declara CWE-770; `CWE-77` é outra fraqueza."""
    assert cwe_alcancavel("CWE-770", "go", catalogo)
    alcancaveis = cwes_alcancaveis("go", catalogo)
    assert 770 in alcancaveis
    # 77 está no conjunto por causa de `go.zeros` (CWE-077), não de CWE-770.
    assert 77 in alcancaveis


def test_prefixo_ausente_nao_e_inventado(tmp_path):
    """Sem a regra de zeros à esquerda, `CWE-77` não pode vir de `CWE-770`."""
    catalogo = tmp_path / "so_770.json"
    catalogo.write_text(json.dumps({"rules": [
        {"id": "go.limite", "languages": ["go"],
         "metadata": {"cwe": ["CWE-770: Allocation Without Limits"]}}]}), encoding="utf-8")
    assert not cwe_alcancavel("CWE-77", "go", str(catalogo))


def test_zeros_a_esquerda_sao_a_mesma_cwe(catalogo):
    assert cwe_alcancavel("CWE-77", "go", catalogo)
    assert cwe_alcancavel("CWE-077", "go", catalogo)


def test_tag_sem_cwe_nao_contribui(catalogo):
    """Regra sem `metadata.cwe` e regra com tag livre não viram CWE alguma."""
    assert cwes_alcancaveis("go", catalogo) == {338, 327, 77, 770, 918}
    assert not cwe_alcancavel("texto qualquer", "go", catalogo)


def test_sem_cache_e_sem_rede_levanta_erro(tmp_path, monkeypatch):
    """Conjunto vazio recusaria a população inteira em silêncio; erro não."""
    def cai(url):
        raise ConnectionError("sem rede")

    monkeypatch.setattr(ruleset, "_obter_ruleset", cai)
    ausente = str(tmp_path / "nao_existe.json")
    with pytest.raises(RulesetIndisponivelError):
        cwes_alcancaveis("go", ausente)


def test_snapshot_expoe_origem_e_data(catalogo):
    snap = ruleset.metadados_snapshot(catalogo)
    assert snap.origem.startswith("https://semgrep.dev/c/")
    assert snap.regras == len(RULESET["rules"])
    assert snap.obtido_em[:2] == "20"
