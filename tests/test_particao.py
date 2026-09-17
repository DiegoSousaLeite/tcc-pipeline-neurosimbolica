"""Partição de desenvolvimento e de avaliação (`scripts/particionar_avaliacao.py`).

O que estes testes protegem não é um comportamento de software: é a validade de
um número. Regra escrita olhando os casos em que ela vai ser medida descreve
arquivos que já vimos, e nada no artefato final denunciaria. A esteira precisa
impedir — a disciplina não basta.
"""
import importlib.util
import os

import pytest

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_spec = importlib.util.spec_from_file_location(
    "particionar_avaliacao", os.path.join(BASE, "scripts",
                                          "particionar_avaliacao.py"))
particionar_avaliacao = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(particionar_avaliacao)

pa = particionar_avaliacao
ALVO = ["CWE-22", "CWE-918"]


class _Caso:
    def __init__(self, id, cwe, repo_name):
        self.id, self.cwe, self.repo_name = id, cwe, repo_name


def _populacao():
    """Duas CWEs, com um repositório de cabeça em cada uma."""
    casos = []
    for cwe, n_repos in (("CWE-22", 6), ("CWE-918", 5)):
        for i in range(n_repos):
            for j in range(5 if i == 0 else 1):
                for versao in ("vuln", "fix"):
                    casos.append(_Caso(f"TPA:r{i}:{cwe}:f{j}:{versao}",
                                       cwe, f"org/repo{i}"))
    return casos


def test_particao_e_deterministica():
    """Derivada do identificador, sem semente: não há o que ajustar."""
    casos = _populacao()
    assert pa.particionar(casos, ALVO) == pa.particionar(casos, ALVO)


def test_ordem_da_populacao_nao_altera_a_particao():
    """Acrescentar um par no fim do pool não pode remexer os já particionados."""
    casos = _populacao()
    assert pa.particionar(casos, ALVO) == pa.particionar(list(reversed(casos)),
                                                         ALVO)


def test_particao_e_estratificada_por_cwe():
    """Uma CWE inteira de um lado tornaria o número da avaliação inútil para ela."""
    casos = _populacao()
    resumo = pa.resumo(casos, pa.particionar(casos, ALVO))
    for cwe in ALVO:
        assert resumo[cwe].get(pa.DESENVOLVIMENTO, 0) > 0
        assert resumo[cwe].get(pa.AVALIACAO, 0) > 0


def test_grupo_cwe_repositorio_nao_atravessa_as_particoes():
    """Pares da mesma CWE no mesmo repositório compartilham idioma (D7)."""
    casos = _populacao()
    particao = pa.particionar(casos, ALVO)
    lados = {}
    for caso in casos:
        lados.setdefault(pa.chave_grupo(caso), set()).add(particao[caso.id])
    assert all(len(v) == 1 for v in lados.values())


def test_vulneravel_e_corrigido_caem_na_mesma_particao():
    """São o mesmo arquivo em dois commits; separá-los mostraria a correção."""
    casos = _populacao()
    particao = pa.particionar(casos, ALVO)
    lados = {}
    for caso in casos:
        lados.setdefault(caso.id.rsplit(":", 1)[0], set()).add(particao[caso.id])
    assert all(len(v) == 1 for v in lados.values())


def test_cwe_fora_do_alvo_nao_e_particionada():
    casos = _populacao() + [_Caso("TPA:x:CWE-400:f:vuln", "CWE-400", "org/x")]
    assert "TPA:x:CWE-400:f:vuln" not in pa.particionar(casos, ALVO)


def test_reparticionar_e_recusado(tmp_path):
    """Reparticionar depois de escrever regra anula a separação."""
    casos = _populacao()
    particao = pa.particionar(casos, ALVO)
    destino = str(tmp_path / "particao.json")
    pa.gravar(destino, particao, casos, ALVO)

    with pytest.raises(pa.ParticaoJaExisteError) as e:
        pa.gravar(destino, particao, casos, ALVO)
    assert "já existe" in str(e.value)


def test_particao_gravada_declara_protocolo_e_resumo(tmp_path):
    """Quem abrir o arquivo meses depois precisa saber sob qual regra foi feito."""
    import json

    casos = _populacao()
    destino = str(tmp_path / "particao.json")
    pa.gravar(destino, pa.particionar(casos, ALVO), casos, ALVO)
    with open(destino, encoding="utf-8") as f:
        payload = json.load(f)
    assert payload["versao_protocolo"] == pa.VERSAO_PROTOCOLO
    assert payload["cwes_alvo"] == sorted(ALVO)
    assert set(payload["resumo"]) == set(ALVO)


# -- a partição real, já gravada -----------------------------------------

@pytest.fixture
def particao_real():
    payload = pa.carregar_particao()
    if payload is None:
        pytest.skip("partição ainda não derivada")
    return payload


def test_particao_real_tem_as_duas_cwes_nas_duas_particoes(particao_real):
    for cwe in ALVO:
        lados = particao_real["resumo"][cwe]
        assert lados[pa.DESENVOLVIMENTO] > 0
        assert lados[pa.AVALIACAO] > 0


def test_particao_real_e_grande_o_bastante_para_medir(particao_real):
    """O projeto adota 30 como limiar; abaixo dele o denominador não serve."""
    for cwe in ALVO:
        assert particao_real["resumo"][cwe][pa.AVALIACAO] >= 30
