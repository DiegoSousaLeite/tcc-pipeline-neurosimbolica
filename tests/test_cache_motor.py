"""O motor como terceiro eixo de invalidação do cache simbólico.

O modo de falha que estes testes existem para impedir é mudo: ligar o modo
entre-arquivos sem invalidar nada faria a rodada ser servida do disco com os
alertas do motor anterior, e o experimento reportaria como resultado do motor
novo aquilo que o antigo produziu — sem nada no CSV denunciando.
"""
import json

import pytest

from src.cache_simbolico import VERSAO_FORMATO, CacheSimbolico
from src.fase1_semgrep import MotorSimbolico

CE = MotorSimbolico(edicao="ce", versao="1.167.0", entre_arquivos=False)
PRO = MotorSimbolico(edicao="pro", versao="1.167.0", entre_arquivos=True)

CASO = ("dono/repo", "abc123def456789", "pkg/a.go", "CWE-22")


def _cache(tmp_path, motor):
    return CacheSimbolico(diretorio=str(tmp_path), motor=motor)


def _gravar(cache, status="DETECTADO", alerta=None):
    cache.gravar(*CASO, status_semgrep=status,
                 alerta=alerta if alerta is not None else {"check_id": "r1"},
                 contexto_hidratado="func f() {}")


# -- 3.1 payload ----------------------------------------------------------

def test_entrada_nova_tem_os_tres_eixos(tmp_path):
    c = _cache(tmp_path, CE)
    _gravar(c)
    payload = json.loads(open(c.caminho(*CASO), encoding="utf-8").read())
    assert payload["versao_ruleset"]
    assert payload["versao_pareamento"]
    assert payload["motor"] == CE.como_dict()
    assert payload["versao_formato"] == VERSAO_FORMATO


# -- 3.2 invalidação ------------------------------------------------------

def test_entrada_de_um_motor_e_ignorada_sob_o_outro(tmp_path):
    _gravar(_cache(tmp_path, CE))
    assert _cache(tmp_path, CE).ler(*CASO) is not None
    assert _cache(tmp_path, PRO).ler(*CASO) is None


def test_invalidacao_alcanca_nao_detectado(tmp_path):
    """É justamente no NAO_DETECTADO que o motor novo pode diferir."""
    c = _cache(tmp_path, CE)
    c.gravar(*CASO, status_semgrep="NAO_DETECTADO", alerta=None,
             contexto_hidratado="", motivo="SEM_ALERTA")
    assert _cache(tmp_path, CE).ler(*CASO) is not None
    assert _cache(tmp_path, PRO).ler(*CASO) is None


def test_entrada_pro_nao_e_servida_numa_rodada_ce(tmp_path):
    """A direção inversa também: Pro gravado não vaza para rodada CE."""
    _gravar(_cache(tmp_path, PRO))
    assert _cache(tmp_path, CE).ler(*CASO) is None


# -- 3.3 entrada legada (D3) ---------------------------------------------

def test_entrada_legada_vale_em_rodada_ce(tmp_path):
    """Gravada antes do campo existir: era CE, e continua correta para CE."""
    c = _cache(tmp_path, CE)
    _gravar(c)
    destino = c.caminho(*CASO)
    payload = json.loads(open(destino, encoding="utf-8").read())
    del payload["motor"]                       # simula entrada anterior
    open(destino, "w", encoding="utf-8").write(json.dumps(payload))

    assert _cache(tmp_path, CE).ler(*CASO) is not None


def test_entrada_legada_e_ignorada_com_modo_ligado(tmp_path):
    c = _cache(tmp_path, CE)
    _gravar(c)
    destino = c.caminho(*CASO)
    payload = json.loads(open(destino, encoding="utf-8").read())
    del payload["motor"]
    open(destino, "w", encoding="utf-8").write(json.dumps(payload))

    assert _cache(tmp_path, PRO).ler(*CASO) is None


def test_contraste_deliberado_com_a_regra_de_pareamento(tmp_path):
    """Ausência de motor é aceita; ausência de pareamento é recomputada."""
    c = _cache(tmp_path, CE)
    _gravar(c)
    destino = c.caminho(*CASO)
    payload = json.loads(open(destino, encoding="utf-8").read())
    del payload["motor"]
    del payload["versao_pareamento"]
    open(destino, "w", encoding="utf-8").write(json.dumps(payload))

    assert _cache(tmp_path, CE).ler(*CASO) is None


# -- 3.4 coexistência -----------------------------------------------------

def test_os_dois_motores_coexistem_sem_sobrescrever(tmp_path):
    ce, pro = _cache(tmp_path, CE), _cache(tmp_path, PRO)
    ce.gravar(*CASO, status_semgrep="NAO_DETECTADO", alerta=None,
              contexto_hidratado="", motivo="SEM_ALERTA")
    pro.gravar(*CASO, status_semgrep="DETECTADO",
               alerta={"check_id": "regra.pro"}, contexto_hidratado="ctx")

    assert ce.caminho(*CASO) != pro.caminho(*CASO)
    lido_ce = _cache(tmp_path, CE).ler(*CASO)
    lido_pro = _cache(tmp_path, PRO).ler(*CASO)
    assert lido_ce["status_semgrep"] == "NAO_DETECTADO"
    assert lido_pro["status_semgrep"] == "DETECTADO"
    assert lido_pro["alerta"]["check_id"] == "regra.pro"


def test_ordem_inversa_de_gravacao_da_o_mesmo_resultado(tmp_path):
    pro, ce = _cache(tmp_path, PRO), _cache(tmp_path, CE)
    pro.gravar(*CASO, status_semgrep="DETECTADO", alerta={"check_id": "p"},
               contexto_hidratado="ctx")
    ce.gravar(*CASO, status_semgrep="NAO_DETECTADO", alerta=None,
              contexto_hidratado="", motivo="SEM_ALERTA")
    assert _cache(tmp_path, PRO).ler(*CASO)["status_semgrep"] == "DETECTADO"
    assert _cache(tmp_path, CE).ler(*CASO)["status_semgrep"] == "NAO_DETECTADO"


# -- compatibilidade com o cache já em disco ------------------------------

def test_caminho_do_ce_e_o_mesmo_de_antes_da_mudanca(tmp_path):
    """~1.700 entradas já existem em disco sob este nome exato."""
    esperado = _cache(tmp_path, CE).caminho(*CASO)
    assert esperado.endswith("__CWE-22.json")
    assert "__pro" not in esperado


def test_caminho_do_pro_e_distinguivel(tmp_path):
    assert _cache(tmp_path, PRO).caminho(*CASO).endswith("__CWE-22__pro.json")


def test_cache_desativado_nao_le_nem_grava(tmp_path):
    c = CacheSimbolico(diretorio=str(tmp_path), motor=CE, ativo=False)
    _gravar(c)
    assert c.ler(*CASO) is None


@pytest.mark.parametrize("motor", [CE, PRO])
def test_entrada_corrompida_e_tratada_como_ausente(tmp_path, motor):
    c = _cache(tmp_path, motor)
    _gravar(c)
    open(c.caminho(*CASO), "w", encoding="utf-8").write("{ nao e json")
    assert c.ler(*CASO) is None
