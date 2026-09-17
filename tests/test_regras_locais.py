"""Carregamento e validação do ruleset local (`src/regras_locais.py`).

O contraste com `src/ruleset.py` é o ponto destes testes. Lá, metadado ausente
degrada para o comportamento conservador e a execução segue: o registry é de
terceiros e derrubar a rodada por um campo que eles não preencheram seria
recusar a ferramenta inteira. Aqui, ausência é defeito nosso — e descobri-lo
depois de a rodada varrer a população custa horas, com a regra *funcionando*.
"""
import pytest
import yaml

from src import regras_locais as rl

COMPLETA = {
    "id": "regra-completa",
    "languages": ["go"],
    "severity": "WARNING",
    "message": "exemplo",
    "pattern": "os.ReadFile($X)",
    "metadata": {
        "cwe": ["CWE-22: Improper Limitation of a Pathname"],
        "subcategory": ["vuln"],
        "proveniencia": "definicao",
    },
}


def _gravar(tmp_path, *regras, nome="regras.yaml"):
    (tmp_path / nome).write_text(yaml.safe_dump({"rules": list(regras)}),
                                 encoding="utf-8")
    return str(tmp_path)


def _sem(campo, valor=None):
    """Cópia da regra completa com um metadado ausente ou trocado."""
    import copy

    regra = copy.deepcopy(COMPLETA)
    if valor is None:
        regra["metadata"].pop(campo, None)
    else:
        regra["metadata"][campo] = valor
    return regra


# -- 4.1 a regra completa carrega ----------------------------------------

def test_regra_completa_carrega(tmp_path):
    regras = rl.carregar(_gravar(tmp_path, COMPLETA))
    assert regras["regra-completa"].proveniencia == rl.DEFINICAO
    assert regras["regra-completa"].subcategorias == ("vuln",)


def test_diretorio_inexistente_nao_derruba(tmp_path):
    """Ruleset local é opcional: sem ele a pipeline roda como sempre rodou."""
    assert rl.carregar(str(tmp_path / "nao-existe")) == {}


# -- 4.2 proveniência ----------------------------------------------------

def test_proveniencia_ausente_derruba_nomeando_a_regra(tmp_path):
    with pytest.raises(rl.RegraLocalInvalidaError) as e:
        rl.carregar(_gravar(tmp_path, _sem("proveniencia")))
    assert "regra-completa" in str(e.value)
    assert "proveniencia" in str(e.value)


def test_proveniencia_desconhecida_derruba(tmp_path):
    """Vocabulário fora do definido não é tratado como um dos válidos."""
    with pytest.raises(rl.RegraLocalInvalidaError) as e:
        rl.carregar(_gravar(tmp_path, _sem("proveniencia", "definitiva")))
    assert "regra-completa" in str(e.value)
    assert "definitiva" in str(e.value)


def test_os_dois_protocolos_sao_aceitos(tmp_path):
    regras = rl.carregar(_gravar(
        tmp_path,
        _sem("proveniencia", rl.DEFINICAO),
        dict(_sem("proveniencia", rl.DESENVOLVIMENTO), id="outra"),
    ))
    assert {r.proveniencia for r in regras.values()} == {rl.DEFINICAO,
                                                        rl.DESENVOLVIMENTO}


# -- 4.3 metadata.cwe ----------------------------------------------------

def test_cwe_ausente_derruba_nomeando_a_regra(tmp_path):
    """Sem ela a regra dispara e o alerta não emparelha: ALERTA_OUTRA_CWE."""
    with pytest.raises(rl.RegraLocalInvalidaError) as e:
        rl.carregar(_gravar(tmp_path, _sem("cwe")))
    assert "regra-completa" in str(e.value)
    assert "metadata.cwe" in str(e.value)


def test_cwe_em_formato_nao_casavel_derruba(tmp_path):
    """O casamento é por identificador completo — o mesmo da Fase 1."""
    with pytest.raises(rl.RegraLocalInvalidaError) as e:
        rl.carregar(_gravar(tmp_path, _sem("cwe", ["travessia de caminho"])))
    assert "regra-completa" in str(e.value)


def test_cwe_como_string_unica_e_aceita(tmp_path):
    """As duas formas ocorrem no registry, e a nossa não precisa divergir."""
    regras = rl.carregar(_gravar(tmp_path, _sem("cwe", "CWE-22: Path Traversal")))
    assert regras["regra-completa"].cwes == ("CWE-22: Path Traversal",)


# -- 4.4 metadata.subcategory --------------------------------------------

def test_subcategoria_ausente_derruba(tmp_path):
    """Ausência NÃO é tratada como auditoria, ao contrário do ruleset alheio."""
    with pytest.raises(rl.RegraLocalInvalidaError) as e:
        rl.carregar(_gravar(tmp_path, _sem("subcategory")))
    assert "regra-completa" in str(e.value)
    assert "subcategory" in str(e.value)


# -- 4.5 manifesto -------------------------------------------------------

def test_manifesto_registra_regra_proveniencia_e_commit(tmp_path):
    dados = rl.para_manifesto(_gravar(tmp_path, COMPLETA), commit="abc1234")
    assert dados["commit"] == "abc1234"
    assert dados["regras"] == [{
        "id": "regra-completa",
        "arquivo": "regras.yaml",
        "cwe": ["CWE-22: Improper Limitation of a Pathname"],
        "proveniencia": "definicao",
        "subcategory": ["vuln"],
    }]


def test_proveniencias_carregadas(tmp_path):
    """É este conjunto que decide se o número agregado pode ser emitido."""
    diretorio = _gravar(
        tmp_path, COMPLETA,
        dict(_sem("proveniencia", rl.DESENVOLVIMENTO), id="outra"))
    assert rl.proveniencias(diretorio) == {rl.DEFINICAO, rl.DESENVOLVIMENTO}


# -- o ruleset real, já versionado ---------------------------------------

def test_ruleset_versionado_cumpre_o_protocolo():
    """Vale para as regras de `regras/go/` como estão no repositório."""
    regras = rl.carregar()
    assert regras, "nenhuma regra local encontrada"
    for regra in regras.values():
        assert regra.proveniencia in rl.PROVENIENCIAS
        assert regra.cwes and regra.subcategorias
