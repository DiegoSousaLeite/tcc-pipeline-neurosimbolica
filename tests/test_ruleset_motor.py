"""Alcançabilidade e grau em função do MOTOR, não só do ruleset.

O defeito que estes testes previnem é o mesmo que criou a capability
`ruleset-alcancabilidade`: subestimar a cobertura em silêncio e, com isso,
recusar na colheita população que o motor detectaria.
"""
import json

import pytest

from src.ruleset import (
    GRAU_ALTA,
    GRAU_BAIXA,
    GRAU_MEDIA,
    cwe_alcancavel,
    cwes_alcancaveis,
    grau_alcancabilidade,
    graus_alcancabilidade,
)


@pytest.fixture
def catalogo(tmp_path):
    """Ruleset mínimo com os três perfis que decidem o grau."""
    regras = {"rules": [
        # taint + vuln  -> media sob CE, alta sob entre-arquivos
        {"id": "go.ssrf", "languages": ["go"], "mode": "taint",
         "metadata": {"cwe": ["CWE-918: SSRF"], "subcategory": ["vuln"]}},
        # nao-taint + vuln -> alta nos dois motores
        {"id": "go.sqli", "languages": ["go"], "mode": "search",
         "metadata": {"cwe": ["CWE-89: SQLi"], "subcategory": ["vuln"]}},
        # auditoria -> baixa nos dois motores
        {"id": "go.audit", "languages": ["go"], "mode": "search",
         "metadata": {"cwe": ["CWE-327: Cripto"], "subcategory": ["audit"]}},
        # outra linguagem: nunca alcança .go
        {"id": "py.ssrf", "languages": ["python"], "mode": "taint",
         "metadata": {"cwe": ["CWE-611: XXE"], "subcategory": ["vuln"]}},
    ]}
    destino = tmp_path / "_regras_teste.json"
    destino.write_text(json.dumps(regras), encoding="utf-8")
    return str(destino)


# -- 4.1 grau em função do motor ------------------------------------------

def test_cwe_de_taint_e_media_sob_ce(catalogo):
    assert grau_alcancabilidade("CWE-918", "go", catalogo) == GRAU_MEDIA


def test_cwe_de_taint_e_alta_sob_entre_arquivos(catalogo):
    """A justificativa do rebaixamento era o alcance; o alcance mudou."""
    assert grau_alcancabilidade("CWE-918", "go", catalogo,
                                entre_arquivos=True) == GRAU_ALTA


def test_cwe_nao_taint_nao_muda_com_o_motor(catalogo):
    for modo in (False, True):
        assert grau_alcancabilidade("CWE-89", "go", catalogo,
                                    entre_arquivos=modo) == GRAU_ALTA


# -- 4.3 eixo de auditoria não é afetado ----------------------------------

def test_auditoria_e_baixa_nos_dois_motores(catalogo):
    """Nenhuma análise de fluxo transforma auditoria em afirmação de vuln."""
    for modo in (False, True):
        assert grau_alcancabilidade("CWE-327", "go", catalogo,
                                    entre_arquivos=modo) == GRAU_BAIXA


def test_mapa_inteiro_muda_so_no_eixo_de_taint(catalogo):
    ce = graus_alcancabilidade("go", catalogo)
    pro = graus_alcancabilidade("go", catalogo, entre_arquivos=True)
    assert ce == {918: GRAU_MEDIA, 89: GRAU_ALTA, 327: GRAU_BAIXA}
    assert pro == {918: GRAU_ALTA, 89: GRAU_ALTA, 327: GRAU_BAIXA}
    mudaram = {c for c in ce if ce[c] != pro[c]}
    assert mudaram == {918}


# -- 4.2 limite inferior --------------------------------------------------

def test_conjunto_sob_ce_nao_e_marcado_como_piso(catalogo):
    assert cwes_alcancaveis("go", catalogo).limite_inferior is False


def test_conjunto_sob_entre_arquivos_e_marcado_como_piso(catalogo):
    """As regras próprias do modo não constam do catálogo aberto."""
    assert cwes_alcancaveis("go", catalogo,
                            entre_arquivos=True).limite_inferior is True


def test_piso_nunca_e_apresentado_como_exato(catalogo):
    """Marcado como piso, o conjunto não afirma cobertura completa."""
    pro = cwes_alcancaveis("go", catalogo, entre_arquivos=True)
    ce = cwes_alcancaveis("go", catalogo)
    assert pro.limite_inferior and not ce.limite_inferior
    # Derivados do mesmo catálogo aberto: o que difere é a CERTEZA, não o
    # conteúdo — inventar CWEs extras aqui seria o número inventado que a D5
    # recusa.
    assert set(pro) == set(ce)


def test_conjunto_continua_sendo_conjunto(catalogo):
    """A marcação não pode custar a semântica de conjunto."""
    alc = cwes_alcancaveis("go", catalogo)
    assert alc == {918, 89, 327}
    assert 918 in alc
    assert alc - {918} == {89, 327}
    assert len(alc) == 3


# -- 4.4 regressão da consulta binária sob CE -----------------------------

def test_consulta_binaria_sob_ce_nao_mudou(catalogo):
    assert cwe_alcancavel("CWE-918", "go", catalogo) is True
    assert cwe_alcancavel("CWE-89", "go", catalogo) is True
    assert cwe_alcancavel("CWE-611", "go", catalogo) is False   # é de python
    assert cwe_alcancavel("CWE-22", "go", catalogo) is False    # não consta


def test_linguagem_continua_separando(catalogo):
    assert cwe_alcancavel("CWE-611", "python", catalogo) is True
    for modo in (False, True):
        assert cwe_alcancavel("CWE-611", "go", catalogo,
                              entre_arquivos=modo) is False


def test_conjunto_em_go_sob_ce_e_o_de_sempre(catalogo):
    assert set(cwes_alcancaveis("go", catalogo)) == {918, 89, 327}
