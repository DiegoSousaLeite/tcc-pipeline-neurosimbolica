"""Mais de um ruleset por execução: invocação, identidade e deduplicação.

O que estes testes protegem é a soma sem subtração. Trocar de ruleset já foi
avaliado e recusado — o `p/golang` perdia 97 casos que o `p/default` detectava —,
então a única forma de acrescentar cobertura é somar rulesets. Somar, porém,
cria três modos de falha novos: a rodada composta ser servida do cache da
unitária, a ordem da configuração invalidar cache à toa, e o número de alertas
por arquivo passar a depender de quantos rulesets cobrem o mesmo padrão.
"""
import pytest

from src import fase1_semgrep as f1

LOCAL = "regras/go"


# -- 2.1 configuração -----------------------------------------------------

def test_configuracao_padrao_continua_unitaria():
    """Ligar o segundo ruleset é decisão explícita, nunca o padrão."""
    assert f1._configs_de("p/default") == ("p/default",)


def test_configuracao_aceita_mais_de_um_ruleset():
    assert f1._configs_de("p/default,regras/go") == ("p/default", "regras/go")


def test_espacos_e_entradas_vazias_sao_descartados():
    """`"p/default,"` é typo, não ruleset anônimo."""
    assert f1._configs_de(" p/default , , regras/go ") == ("p/default",
                                                           "regras/go")


def test_configuracao_vazia_nao_vira_padrao_por_omissao():
    assert f1._configs_de("") == ()
    assert f1._configs_de("   ") == ()


# -- 2.2 invocação --------------------------------------------------------

def test_configuracao_padrao_monta_a_linha_de_comando_de_hoje():
    """As Rodadas 1–3 mediram ESTA linha. Um argumento a mais as invalidaria."""
    assert f1.montar_comando("/tmp/alvo.go", configs=("p/default",)) == [
        f1.SEMGREP, "--config", "p/default", "--sarif", "--quiet",
        "/tmp/alvo.go",
    ]


def test_dois_rulesets_viram_dois_config_na_ordem_configurada():
    cmd = f1.montar_comando("/tmp/alvo.go", configs=("p/default", LOCAL))
    assert cmd.count("--config") == 2
    assert cmd[:5] == [f1.SEMGREP, "--config", "p/default", "--config", LOCAL]
    assert cmd[-1] == "/tmp/alvo.go"


def test_modo_entre_arquivos_soma_aos_dois_config():
    """Os dois eixos são independentes: conjunto de rulesets e motor."""
    cmd = f1.montar_comando("/tmp/alvo.go", entre_arquivos=True,
                            configs=("p/default", LOCAL))
    assert cmd.count("--config") == 2
    assert cmd.count("--pro") == 1


# -- 2.3 configuração vazia é erro ---------------------------------------

def test_configuracao_vazia_levanta_erro_explicito():
    with pytest.raises(f1.ConfiguracaoVaziaError) as e:
        f1.montar_comando("/tmp/alvo.go", configs=())
    assert "SEMGREP_CONFIG" in str(e.value)


def test_configuracao_vazia_nao_invoca_o_motor(monkeypatch, tmp_path):
    """Zero alertas e população inteira "não detectada" é o modo de falha a evitar."""
    alvo = tmp_path / "alvo.go"
    alvo.write_text("package main\n", encoding="utf-8")

    def _proibido(*a, **k):
        raise AssertionError("o motor não pode ser invocado sem regras")

    monkeypatch.setattr(f1.subprocess, "run", _proibido)
    with pytest.raises(f1.ConfiguracaoVaziaError):
        f1.executar_semgrep(str(alvo), "CWE-327", configs=())


# -- 2.4 identidade do conjunto ------------------------------------------

def test_mesmo_conjunto_mesma_identidade():
    assert (f1.identidade_conjunto(("p/default", LOCAL))
            == f1.identidade_conjunto(("p/default", LOCAL)))


def test_ordem_nao_altera_a_identidade():
    """A ordem não altera a união dos achados; invalidar cache por ela seria à toa."""
    assert (f1.identidade_conjunto(("p/default", LOCAL))
            == f1.identidade_conjunto((LOCAL, "p/default")))


def test_subconjunto_tem_identidade_distinta():
    """Sem isto, a rodada composta seria servida do cache da unitária."""
    assert (f1.identidade_conjunto(("p/default",))
            != f1.identidade_conjunto(("p/default", LOCAL)))


def test_identidade_do_conjunto_unitario_e_o_nome_do_ruleset():
    """É o que mantém válidas as ~1.700 entradas gravadas antes desta mudança."""
    assert f1.identidade_conjunto(("p/default",)) == "p/default"


def test_identidade_de_conjunto_vazio_e_erro():
    with pytest.raises(f1.ConfiguracaoVaziaError):
        f1.identidade_conjunto(())


# -- 2.10 procedência -----------------------------------------------------

def test_ruleset_do_registry_e_de_terceiros():
    for config in ("p/default", "r/go.lang.security", "https://semgrep.dev/c/p/gosec"):
        assert f1.procedencia(config) == f1.PROCEDENCIA_TERCEIROS


def test_ruleset_local_e_proprio():
    """Medir com regra nossa levanta objeção que ruleset publicado não levanta."""
    assert f1.procedencia(LOCAL) == f1.PROCEDENCIA_PROPRIA
    assert f1.procedencia("./regras/go") == f1.PROCEDENCIA_PROPRIA


def test_rulesets_configurados_declaram_procedencia():
    assert f1.rulesets_configurados(("p/default", LOCAL)) == [
        {"config": "p/default", "procedencia": f1.PROCEDENCIA_TERCEIROS},
        {"config": LOCAL, "procedencia": f1.PROCEDENCIA_PROPRIA},
    ]


# -- 2.9 deduplicação -----------------------------------------------------

def _achado(rule_id, linha=10, coluna=1, arquivo="alvo.go"):
    return {
        "ruleId": rule_id,
        "locations": [{"physicalLocation": {
            "artifactLocation": {"uri": arquivo},
            "region": {"startLine": linha, "startColumn": coluna},
        }}],
        "message": {"text": "achado"},
    }


REGRAS = {
    "default.path": ["CWE-22: Path Traversal"],
    "local.path": ["CWE-22: Path Traversal"],
    "outra.cwe": ["CWE-918: SSRF"],
}


def test_achados_equivalentes_sao_deduplicados():
    """Mesmo arquivo, mesma posição, mesma CWE — de rulesets diferentes."""
    achados = [_achado("default.path"), _achado("local.path")]
    assert len(f1.deduplicar(achados, REGRAS)) == 1


def test_mesma_posicao_com_cwes_diferentes_nao_e_duplicata():
    """Descrevem fraquezas distintas no mesmo ponto do código."""
    achados = [_achado("default.path"), _achado("outra.cwe")]
    assert len(f1.deduplicar(achados, REGRAS)) == 2


def test_mesma_cwe_em_posicoes_diferentes_nao_e_duplicata():
    achados = [_achado("default.path", linha=10), _achado("local.path", linha=42)]
    assert len(f1.deduplicar(achados, REGRAS)) == 2


def test_deduplicacao_e_deterministica():
    """O sobrevivente é o primeiro em `(arquivo, linha, coluna, check_id)`."""
    a, b = _achado("default.path"), _achado("local.path")
    assert f1.deduplicar([a, b], REGRAS) == f1.deduplicar([b, a], REGRAS)
    assert f1.deduplicar([b, a], REGRAS)[0]["ruleId"] == "default.path"


def test_deduplicacao_nao_rebaixa_status():
    """Se algum equivalente casava com o gabarito, o sobrevivente casa."""
    preservados = f1.deduplicar([_achado("local.path"), _achado("default.path")],
                                REGRAS)
    tags = REGRAS[preservados[0]["ruleId"]]
    assert f1._cwe_nas_tags(tags, "CWE-22")


# -- 2.5 união dos catálogos, cache por ruleset ---------------------------

CATALOGO_PADRAO = {
    "rules": [
        {"id": "go.md5", "languages": ["go"],
         "metadata": {"cwe": ["CWE-327: Broken Crypto"], "subcategory": "vuln"}},
        {"id": "go.ssrf", "languages": ["go"], "mode": "taint",
         "metadata": {"cwe": ["CWE-918: SSRF"], "subcategory": "vuln"}},
    ]
}
CATALOGO_LOCAL = {
    "rules": [
        {"id": "local.path", "languages": ["go"],
         "metadata": {"cwe": ["CWE-22: Path Traversal"], "subcategory": "vuln"}},
        # Mesma CWE da regra de taint acima, mas sintática: é ela que eleva o
        # grau de CWE-918 quando os dois rulesets estão configurados.
        {"id": "local.ssrf", "languages": ["go"],
         "metadata": {"cwe": ["CWE-918: SSRF"], "subcategory": "vuln"}},
    ]
}


@pytest.fixture
def dois_rulesets(tmp_path, monkeypatch):
    """Dois catálogos em disco, endereçados pelo nome do ruleset."""
    import json

    from src import ruleset

    caminhos = {}
    for nome, dados in (("p/default", CATALOGO_PADRAO), (LOCAL, CATALOGO_LOCAL)):
        destino = tmp_path / f"_regras_{nome.replace('/', '_')}.json"
        destino.write_text(json.dumps(dados), encoding="utf-8")
        caminhos[nome] = str(destino)

    monkeypatch.setattr(ruleset, "caminho_cache", lambda c: caminhos[c])
    monkeypatch.setattr(ruleset, "_obter_ruleset",
                        lambda url: pytest.fail(f"buscou {url} no registry"))
    ruleset._MEMORIA.clear()
    yield ruleset
    ruleset._MEMORIA.clear()


def test_acrescentar_ruleset_nao_rebusca_o_catalogo_do_outro(dois_rulesets):
    """O cache de catálogo é por ruleset; eles mudam de forma independente."""
    primeiro = dois_rulesets.carregar_regras(config="p/default")
    dois_rulesets.carregar_regras(config=LOCAL)
    # Mesmo objeto: veio da memória, sem reler o JSON do disco.
    assert dois_rulesets.carregar_regras(config="p/default") is primeiro


def test_conjunto_alcancavel_com_dois_contem_o_conjunto_com_um(dois_rulesets):
    """Acrescentar ruleset só amplia — nenhuma CWE deixa de ser alcançável."""
    um = dois_rulesets.cwes_alcancaveis("go", configs=("p/default",))
    dois = dois_rulesets.cwes_alcancaveis("go", configs=("p/default", LOCAL))
    assert set(um) <= set(dois)
    assert 22 in dois and 22 not in um


def test_cwe_ausente_de_todos_os_rulesets_nao_e_alcancavel(dois_rulesets):
    assert not dois_rulesets.cwe_alcancavel("CWE-79", "go",
                                            configs=("p/default", LOCAL))


# -- 2.6 grau considera a melhor regra de qualquer ruleset ----------------

def test_regra_de_outro_ruleset_eleva_o_grau(dois_rulesets):
    """CWE-918: taint no `p/default`, sintática de vulnerabilidade no local."""
    from src.ruleset import GRAU_ALTA, GRAU_MEDIA

    assert dois_rulesets.grau_alcancabilidade(
        "CWE-918", "go", configs=("p/default",)) == GRAU_MEDIA
    assert dois_rulesets.grau_alcancabilidade(
        "CWE-918", "go", configs=("p/default", LOCAL)) == GRAU_ALTA


def test_grau_nao_cai_ao_acrescentar_ruleset(dois_rulesets):
    from src.ruleset import ORDEM_GRAUS

    um = dois_rulesets.graus_alcancabilidade("go", configs=("p/default",))
    dois = dois_rulesets.graus_alcancabilidade("go", configs=("p/default", LOCAL))
    for cwe, grau in um.items():
        assert ORDEM_GRAUS.index(dois[cwe]) >= ORDEM_GRAUS.index(grau)


def test_identificador_repetido_entre_rulesets_nao_descarta_regra(tmp_path,
                                                                  monkeypatch):
    """`p/gosec` e `p/default` compartilham 22 regras de mesmo `id`.

    Fundir os catálogos por chave descartaria uma das versões — e se a
    descartada fosse a de grau mais alto, a CWE seria rebaixada por um detalhe
    de nomenclatura.
    """
    import json

    from src import ruleset
    from src.ruleset import GRAU_ALTA

    catalogos = {
        "a": {"rules": [{"id": "mesmo.id", "languages": ["go"], "mode": "taint",
                         "metadata": {"cwe": ["CWE-22: Path"],
                                      "subcategory": "vuln"}}]},
        "b": {"rules": [{"id": "mesmo.id", "languages": ["go"],
                         "metadata": {"cwe": ["CWE-22: Path"],
                                      "subcategory": "vuln"}}]},
    }
    caminhos = {}
    for nome, dados in catalogos.items():
        destino = tmp_path / f"_regras_{nome}.json"
        destino.write_text(json.dumps(dados), encoding="utf-8")
        caminhos[nome] = str(destino)
    monkeypatch.setattr(ruleset, "caminho_cache", lambda c: caminhos[c])
    ruleset._MEMORIA.clear()

    assert ruleset.grau_alcancabilidade("CWE-22", "go",
                                        configs=("a", "b")) == GRAU_ALTA
    ruleset._MEMORIA.clear()


# -- 2.7 / 2.8 eixo de conjunto no cache simbólico ------------------------

CHAVE = ("acme/servico", "a" * 40, "pkg/cripto/cripto.go", "CWE-327")


def _cache(diretorio, configs):
    from src.cache_simbolico import CacheSimbolico

    return CacheSimbolico(diretorio=diretorio,
                          versao_ruleset=f1.identidade_conjunto(configs))


def test_entrada_de_conjunto_unitario_e_ignorada_sob_conjunto_composto(tmp_path):
    """Sem isto, a rodada composta seria servida com os alertas da unitária."""
    dir_cache = str(tmp_path / "cache_simbolico")
    _cache(dir_cache, ("p/default",)).gravar(*CHAVE, "NAO_DETECTADO")

    composto = _cache(dir_cache, ("p/default", LOCAL))
    assert composto.ler(*CHAVE) is None
    # A entrada não é apagada: continua sendo evidência do que aquele conjunto
    # produziu.
    import os
    assert os.path.exists(composto.caminho(*CHAVE))


def test_ordem_dos_rulesets_nao_invalida(tmp_path):
    """A ordem não altera a união dos achados."""
    dir_cache = str(tmp_path / "cache_simbolico")
    _cache(dir_cache, ("p/default", LOCAL)).gravar(*CHAVE, "NAO_DETECTADO")
    assert _cache(dir_cache, (LOCAL, "p/default")).ler(*CHAVE) is not None


def test_entrada_legada_de_ruleset_unico_e_lida_como_conjunto_unitario(tmp_path):
    """As ~1.700 entradas em disco foram gravadas com o nome do ruleset."""
    from src.cache_simbolico import CacheSimbolico

    dir_cache = str(tmp_path / "cache_simbolico")
    legado = CacheSimbolico(diretorio=dir_cache, versao_ruleset="p/default")
    legado.gravar(*CHAVE, "NAO_DETECTADO")

    assert _cache(dir_cache, ("p/default",)).ler(*CHAVE) is not None


def test_identidade_do_motor_continua_sendo_eixo_separado(tmp_path):
    """Os dois eixos são independentes e ambos precisam invalidar."""
    from src.cache_simbolico import CacheSimbolico
    from src.fase1_semgrep import MotorSimbolico

    dir_cache = str(tmp_path / "cache_simbolico")
    identidade = f1.identidade_conjunto(("p/default",))
    ce = MotorSimbolico(edicao="ce", versao="1.167.0", entre_arquivos=False)
    pro = MotorSimbolico(edicao="pro", versao="1.167.0", entre_arquivos=True)

    CacheSimbolico(diretorio=dir_cache, versao_ruleset=identidade,
                   motor=ce).gravar(*CHAVE, "NAO_DETECTADO")
    assert CacheSimbolico(diretorio=dir_cache, versao_ruleset=identidade,
                          motor=pro).ler(*CHAVE) is None
    assert CacheSimbolico(diretorio=dir_cache, versao_ruleset=identidade,
                          motor=ce).ler(*CHAVE) is not None
