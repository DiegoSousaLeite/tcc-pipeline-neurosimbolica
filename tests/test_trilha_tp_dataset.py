"""Testes da trilha TP_dataset (tarefas 2.1 a 2.3).

Além dos casos sintéticos, dois testes medem o dataset real: são eles que
sustentam os números citados no proposal (66 alvos brutos, 9 descartados por
serem arquivo de teste) e falham se o dataset mudar sem a documentação mudar
junto.
"""
import json

import pytest

from run_pipeline import (
    construir_casos_fp,
    construir_casos_tp_dataset,
    contar_por_trilha,
)
from src.config import DATASET_PATH
from tests.fixtures import dataset_minimo


@pytest.fixture(scope="module")
def dataset_real():
    with open(DATASET_PATH, encoding="utf-8") as f:
        return json.load(f)


# --- 2.1 Construção dos casos ---------------------------------------------

def test_true_positive_vira_caso_vulneravel():
    casos = construir_casos_tp_dataset(dataset_minimo())
    assert casos, "a fixture tem entradas true_positive com .go não-teste"
    assert {c.origem for c in casos} == {"TP_dataset"}
    assert {c.gabarito for c in casos} == {"vulneravel"}
    assert {c.commit for c in casos} == {"c" * 40}   # commit_hash da entrada tp1


def test_false_positive_nao_entra_na_trilha_nova():
    casos = construir_casos_tp_dataset(dataset_minimo())
    assert not any(c.id.startswith("TPD:fp") for c in casos)


def test_ids_tem_prefixo_proprio():
    """O prefixo `TPD:` garante que nenhum ID novo colida com os já gravados
    nos resultados_tcc*.csv da Parte 1."""
    casos = construir_casos_tp_dataset(dataset_minimo())
    assert all(c.id.startswith("TPD:") for c in casos)


def test_construir_casos_fp_nao_muda_com_a_trilha_nova():
    """Requisito 'Entrada false_positive não é afetada': mesmos IDs de sempre."""
    ids = [c.id for c in construir_casos_fp(dataset_minimo())]
    assert ids == ["fp1", "fp1#2", "fp2"]


# --- 2.2 Filtro de arquivos de teste ---------------------------------------

def test_arquivo_de_teste_descartado_sem_renumerar():
    """A entrada tp1 tem locations [header.go, header_test.go, CHANGELOG.md,
    token.go]: sobram os índices 0 e 3, com os índices ORIGINAIS no ID."""
    casos = construir_casos_tp_dataset(dataset_minimo())
    assert [c.id for c in casos] == ["TPD:tp1", "TPD:tp1#3"]
    assert [c.arquivo for c in casos] == ["middleware/header.go", "auth/token.go"]


def test_entrada_so_com_teste_nao_gera_caso():
    """tp2 só tem csrf_test.go e docs.md: não contribui com nenhum caso."""
    casos = construir_casos_tp_dataset(dataset_minimo())
    assert not any(c.id.startswith("TPD:tp2") for c in casos)


def test_filtro_de_teste_no_dataset_real(dataset_real):
    """Mede o dataset real: 66 alvos `.go` distintos, 9 deles `_test.go`."""
    com_teste = construir_casos_tp_dataset(dataset_real, so_go=False)
    so_go = [c for c in com_teste if c.arquivo.lower().endswith(".go")]
    sem_teste = construir_casos_tp_dataset(dataset_real)

    assert len(so_go) == 66
    assert len(so_go) - len(sem_teste) == 9
    assert len(sem_teste) == 57
    assert not any(c.arquivo.lower().endswith("_test.go") for c in sem_teste)


def test_alvo_repetido_na_mesma_entrada_gera_um_caso_so(dataset_real):
    """As entradas `cvefixes` listam uma location por FUNÇÃO alterada, então o
    mesmo arquivo se repete: 108 locations `.go` para 66 alvos distintos.
    Como a pipeline analisa o arquivo inteiro, a repetição só duplicaria
    evidência na matriz e gastaria chamada de LLM."""
    brutas = [loc["file"]
              for e in dataset_real if e["ground_truth"] == "true_positive"
              for loc in e["to_analyzer"].get("locations", [])
              if loc["file"].lower().endswith(".go")]
    assert len(brutas) == 108   # com repetição

    casos = construir_casos_tp_dataset(dataset_real, so_go=False)
    chaves = [(c.repo_name, c.commit, c.arquivo, c.cwe) for c in casos]
    assert len(chaves) == len(set(chaves))


# --- 2.3 num_locations ------------------------------------------------------

def test_num_locations_conta_antes_dos_filtros():
    """tp1 tem 4 locations e 2 descartes; os casos gerados registram 4."""
    casos = construir_casos_tp_dataset(dataset_minimo())
    assert {c.num_locations for c in casos} == {4}


def test_num_locations_nas_tres_trilhas(dataset_real):
    """A entrada de CVE-2025-27616 / CWE-290 tem 11 locations, uma delas
    `_test.go`: os casos sobreviventes ainda registram 11 (D2 do design)."""
    casos = construir_casos_tp_dataset(dataset_real)
    # São duas entradas CWE-290 (11 e 3 locations); a de 11 é a de CVE-2025-27616.
    cwe290 = [c for c in casos if c.cwe == "CWE-290" and c.num_locations == 11]
    assert cwe290, "a entrada de 11 locations deve estar presente no dataset"
    assert len(cwe290) < 11   # o filtro cortou locations, o contador não mudou

    # Trilha FP: entradas de location única registram 1.
    fp_unicos = [c for c in construir_casos_fp(dataset_real) if c.num_locations == 1]
    assert fp_unicos


# --- 2.4 Ligação ao runner --------------------------------------------------

def test_contagem_por_trilha_lista_as_quatro(dataset_real):
    casos = (construir_casos_fp(dataset_real)
             + construir_casos_tp_dataset(dataset_real))
    contagem = contar_por_trilha(casos)
    assert list(contagem) == ["FP", "TP_ouro", "TP_prata", "TP_dataset"]
    assert contagem["FP"] == 791
    assert contagem["TP_dataset"] == 57
    assert contagem["TP_ouro"] == 0   # trilha vazia continua listada
