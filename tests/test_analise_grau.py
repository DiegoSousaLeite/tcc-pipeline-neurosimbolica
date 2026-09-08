"""Testes da seção `grau` de `scripts/analise_rodada.py`.

A agregação é o ponto: pares e detecções SOMADOS por grupo, nunca a média das
taxas por CWE. Na Rodada 3 uma CWE tinha 3 pares e outra 124 — a média por CWE
deixaria a escala à mercê das caudas pequenas, e é exatamente o erro que estes
testes existem para impedir.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.analise_rodada import (  # noqa: E402
    TRILHA_FILTRADA,
    _agrega_por_grau,
    secao_grau,
)

GRAUS = {89: "alta", 918: "media", 400: "baixa", 22: "media", 79: "alta"}


def _linha(cwe, detectado, origem=TRILHA_FILTRADA):
    return {"ID_Caso": f"{cwe}:{detectado}:{id(object())}",
            "CWE": cwe,
            "Origem": origem,
            "Gabarito": "vulneravel",
            "Status_Semgrep": "DETECTADO" if detectado else "NAO_DETECTADO"}


def test_agrega_somas_e_nao_media_de_taxas():
    """Uma CWE de 2 pares com 100% e outra de 98 com ~0% não podem virar 50%."""
    linhas = ([_linha("CWE-89", True)] * 2            # 2 pares, 2 detecções
              + [_linha("CWE-79", True)]              # 98 pares, 1 detecção
              + [_linha("CWE-79", False)] * 97)
    agregado = _agrega_por_grau(linhas, GRAUS)

    cwes, pares, det = agregado["alta"]
    assert (cwes, pares, det) == (2, 100, 3)
    # 3/100 = 3%, e não a média de 100% e 1,02% (~50,5%).
    assert round(100 * det / pares, 2) == 3.0


def test_separa_os_tres_graus():
    linhas = [_linha("CWE-89", True), _linha("CWE-89", False),
              _linha("CWE-918", False), _linha("CWE-400", False)]
    agregado = _agrega_por_grau(linhas, GRAUS)

    assert agregado["alta"] == (1, 2, 1)
    assert agregado["media"] == (1, 1, 0)
    assert agregado["baixa"] == (1, 1, 0)


def test_ordem_e_decrescente_por_grau():
    assert list(_agrega_por_grau([], GRAUS)) == ["alta", "media", "baixa"]


def test_excluir_cwe_remove_a_contribuicao_dela():
    """Base da checagem de robustez: a separação depende de uma única CWE?"""
    linhas = [_linha("CWE-89", True), _linha("CWE-79", False)]
    com = _agrega_por_grau(linhas, GRAUS)
    sem = _agrega_por_grau(linhas, GRAUS, excluir=89)

    assert com["alta"] == (2, 2, 1)
    assert sem["alta"] == (1, 1, 0)


def test_cwe_sem_grau_fica_de_fora():
    """CWE inalcançável não tem grau: entrar como `baixa` misturaria 'há regra
    fraca' com 'não há regra alguma', que são estados diferentes."""
    linhas = [_linha("CWE-863", False), _linha("CWE-89", True)]
    agregado = _agrega_por_grau(linhas, GRAUS)
    assert sum(p for _, p, _ in agregado.values()) == 1


def test_cwe_ilegivel_nao_quebra():
    linhas = [_linha("sem identificador", False), _linha("CWE-89", True)]
    assert _agrega_por_grau(linhas, GRAUS)["alta"] == (1, 1, 1)


class _RodadaFalsa:
    def __init__(self, linhas):
        self.unicas = linhas
        self.args = None


def test_rodada_sem_a_trilha_filtrada_informa_em_vez_de_falhar(capsys):
    rodada = _RodadaFalsa([_linha("CWE-89", True, origem="FP")])
    secao_grau(rodada)
    saida = capsys.readouterr().out
    assert "indisponível" in saida


def test_rodada_vazia_informa_em_vez_de_falhar(capsys):
    secao_grau(_RodadaFalsa([]))
    assert "indisponível" in capsys.readouterr().out


@pytest.mark.parametrize("gabarito", ["seguro"])
def test_so_conta_casos_vulneraveis(gabarito, capsys):
    """A versão corrigida do par não mede cobertura: contá-la dobraria o
    denominador com casos que nunca deveriam disparar."""
    linha = _linha("CWE-89", False)
    linha["Gabarito"] = gabarito
    secao_grau(_RodadaFalsa([linha]))
    assert "indisponível" in capsys.readouterr().out
