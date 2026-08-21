"""Testes das funções puras já existentes na pipeline (tarefa 1.4).

Cobre as quatro funções sem efeito colateral que decidem número no TCC:
classificação das duas matrizes, extração de função e construção dos casos FP.
"""
from run_pipeline import construir_casos_fp
from src.fase5_auditoria import classificar_acerto_llm, classificar_cobertura_semgrep
from src.hidratacao import extrai_funcao, nome_funcao
from tests.fixtures import CODIGO_GO, dataset_minimo

# --- Matriz 1: cobertura do Semgrep ---------------------------------------

def test_cobertura_semgrep_quatro_celulas():
    assert "VP" in classificar_cobertura_semgrep("vulneravel", detectado=True)
    assert "FN" in classificar_cobertura_semgrep("vulneravel", detectado=False)
    assert "FP" in classificar_cobertura_semgrep("seguro", detectado=True)
    assert "VN" in classificar_cobertura_semgrep("seguro", detectado=False)


# --- Matriz 2: acerto do LLM ----------------------------------------------

def test_acerto_llm_quatro_celulas():
    assert classificar_acerto_llm("vulneravel", "VP") == "Verdadeiro Positivo (Acerto)"
    assert classificar_acerto_llm("seguro", "FP") == "Verdadeiro Negativo (Acerto)"
    assert classificar_acerto_llm("vulneravel", "FP") == "Falso Negativo (Falha Crítica)"
    assert classificar_acerto_llm("seguro", "VP") == "Falso Positivo (Ruído Mantido)"


def test_acerto_llm_veredito_invalido_vira_erro():
    """Veredito fora de {VP, FP} nunca pode ser contado como acerto/erro comum:
    cai em categoria de erro de inferência, fora da matriz."""
    for veredito in ("ERROR", "TALVEZ", "", "N/A"):
        assert classificar_acerto_llm("seguro", veredito) == "Erro de Inferência (API_ERROR)"


# --- Hidratação -----------------------------------------------------------

def test_extrai_funcao_pega_a_funcao_da_linha():
    r = extrai_funcao(CODIGO_GO, alvo_idx=7)   # dentro de alpha()
    assert r["metodo"] == "funcao"
    assert r["codigo"].lstrip().startswith("func alpha")
    assert "func beta" not in r["codigo"]
    assert nome_funcao(r["codigo"]) == "alpha"


def test_extrai_funcao_fora_de_funcao_usa_janela():
    r = extrai_funcao(CODIGO_GO, alvo_idx=1)   # linha do `package main`
    assert r["metodo"] == "janela"
    assert r["linha_inicio"] == 1


def test_extrai_funcao_lista_vazia():
    assert extrai_funcao([], alvo_idx=1) is None


# --- Construção dos casos FP ----------------------------------------------

def test_construir_casos_fp_ignora_true_positive():
    casos = construir_casos_fp(dataset_minimo())
    assert {c.origem for c in casos} == {"FP"}
    assert all(c.gabarito == "seguro" for c in casos)
    assert not any(c.id.startswith("tp") for c in casos)


def test_construir_casos_fp_filtra_extensao_sem_renumerar():
    """A location 1 (.html) some, mas a location 2 mantém o índice 2 no ID:
    trocar o filtro não pode renumerar casos já gravados em CSV."""
    casos = [c for c in construir_casos_fp(dataset_minimo()) if c.id.startswith("fp1")]
    assert [c.id for c in casos] == ["fp1", "fp1#2"]
    assert [c.arquivo for c in casos] == ["handler.go", "render.go"]


def test_construir_casos_fp_uma_location():
    casos = construir_casos_fp(dataset_minimo(), todas_locations=False)
    assert [c.id for c in casos] == ["fp1", "fp2"]


def test_construir_casos_fp_todas_extensoes():
    casos = [c for c in construir_casos_fp(dataset_minimo(), so_go=False)
             if c.id.startswith("fp1")]
    assert [c.arquivo for c in casos] == ["handler.go", "relatorio.html", "render.go"]


def test_construir_casos_fp_preenche_metadados():
    caso = next(c for c in construir_casos_fp(dataset_minimo()) if c.id == "fp2")
    assert caso.repo_name == "acme/servico"
    assert caso.repo_dir == "servico"
    assert caso.commit == "b" * 40
    assert caso.cwe == "CWE-327"
    assert caso.cwe_name == "Nome de CWE-327"
    assert caso.description == "Descrição de CWE-327."
