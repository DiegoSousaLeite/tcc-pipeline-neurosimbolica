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


# --- Grau ordinal de alcançabilidade ---------------------------------------
#
# A consulta binária responde "existe regra?". A Rodada 3 mediu que essa resposta
# comporta realidades muito diferentes: CWEs cobertas só por regras de auditoria
# renderam 1 detecção em 336 pares, contra 17 em 354 das demais. O grau vem de
# campo declarado pela regra — `metadata.subcategory` e `mode` —, nunca de uma
# lista de CWEs no código, que passaria a mentir em silêncio quando o ruleset
# mudasse.

RULESET_GRAUS = {
    "rules": [
        # CWE-89: regra que afirma vulnerabilidade e não depende de taint.
        {"id": "go.sqli.direta", "languages": ["go"], "mode": None,
         "metadata": {"cwe": ["CWE-89: SQL Injection"], "subcategory": ["vuln"]}},
        # CWE-918: única regra de vulnerabilidade é de taint.
        {"id": "go.ssrf.taint", "languages": ["go"], "mode": "taint",
         "metadata": {"cwe": ["CWE-918: SSRF"], "subcategory": ["vuln"]}},
        # CWE-400: só auditoria.
        {"id": "go.limite.audit", "languages": ["go"],
         "metadata": {"cwe": ["CWE-400: Resource Exhaustion"],
                      "subcategory": ["audit"]}},
        # CWE-611: metadado ausente — degrada para auditoria, não quebra.
        {"id": "go.xxe.sem_sub", "languages": ["go"],
         "metadata": {"cwe": ["CWE-611: XXE"]}},
        # CWE-352: vocabulário desconhecido — idem.
        {"id": "go.csrf.estranho", "languages": ["go"],
         "metadata": {"cwe": ["CWE-352: CSRF"], "subcategory": ["inventado"]}},
        # CWE-79: alta em Python, baixa em Go — o grau é por linguagem.
        {"id": "py.xss.vuln", "languages": ["python"],
         "metadata": {"cwe": ["CWE-79: XSS"], "subcategory": ["vuln"]}},
        {"id": "go.xss.audit", "languages": ["go"],
         "metadata": {"cwe": ["CWE-79: XSS"], "subcategory": ["audit"]}},
        # `subcategory` como string única, como `cwe` já ocorre.
        {"id": "go.cripto.str", "languages": ["go"],
         "metadata": {"cwe": "CWE-327: Broken Crypto", "subcategory": "vuln"}},
    ]
}


@pytest.fixture
def catalogo_graus(tmp_path):
    caminho = tmp_path / "_regras_graus.json"
    caminho.write_text(json.dumps(RULESET_GRAUS), encoding="utf-8")
    return str(caminho)


def test_grau_alto_para_regra_vuln_sem_taint(catalogo_graus):
    assert ruleset.grau_alcancabilidade("CWE-89", "go", catalogo_graus) == "alta"


def test_grau_intermediario_quando_so_ha_vuln_de_taint(catalogo_graus):
    """Taint exige origem e destino no mesmo arquivo, e o motor não faz fluxo
    entre arquivos: CWE-918 rendeu 1 detecção em 112 pares na Rodada 3."""
    assert ruleset.grau_alcancabilidade("CWE-918", "go", catalogo_graus) == "media"


def test_grau_baixo_quando_so_ha_auditoria(catalogo_graus):
    assert ruleset.grau_alcancabilidade("CWE-400", "go", catalogo_graus) == "baixa"


def test_metadado_ausente_ou_desconhecido_degrada_para_auditoria(catalogo_graus):
    """O pior caso precisa ser o comportamento binário de hoje, não uma exceção."""
    assert ruleset.grau_alcancabilidade("CWE-611", "go", catalogo_graus) == "baixa"
    assert ruleset.grau_alcancabilidade("CWE-352", "go", catalogo_graus) == "baixa"


def test_subcategory_como_string_unica(catalogo_graus):
    assert ruleset.grau_alcancabilidade("CWE-327", "go", catalogo_graus) == "alta"


def test_grau_e_por_linguagem(catalogo_graus):
    assert ruleset.grau_alcancabilidade("CWE-79", "python", catalogo_graus) == "alta"
    assert ruleset.grau_alcancabilidade("CWE-79", "go", catalogo_graus) == "baixa"


def test_cwe_inalcancavel_nao_tem_grau(catalogo_graus):
    assert ruleset.grau_alcancabilidade("CWE-22", "go", catalogo_graus) is None


def test_graus_por_linguagem_devolve_o_mapa(catalogo_graus):
    graus = ruleset.graus_alcancabilidade("go", catalogo_graus)
    assert graus == {89: "alta", 327: "alta", 918: "media",
                     400: "baixa", 611: "baixa", 352: "baixa", 79: "baixa"}


def test_ordem_dos_graus_e_ordinal():
    assert ruleset.ORDEM_GRAUS == ("baixa", "media", "alta")


def test_grau_baixo_continua_alcancavel(catalogo_graus):
    """REDE DE PROTEÇÃO: o grau não pode estreitar a fronteira que a Fase 1
    respeita. Grau baixo é diagnóstico, não exclusão."""
    assert cwe_alcancavel("CWE-400", "go", catalogo_graus)
    assert 400 in cwes_alcancaveis("go", catalogo_graus)
