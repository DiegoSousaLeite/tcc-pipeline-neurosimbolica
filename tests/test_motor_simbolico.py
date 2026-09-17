"""Identidade declarada do motor simbólico e a flag do modo entre-arquivos.

O que estes testes protegem é um modo de falha SILENCIOSO: dois motores
produzem SARIF diferente sobre o mesmo arquivo, e um resultado sem identidade
não sabe dizer qual deles o gerou. Nada no CSV denunciaria a troca.
"""
import json
import os

import pytest

from src import fase1_semgrep as f1


@pytest.fixture(autouse=True)
def _limpa_memoria():
    """A identidade é memoizada por processo; um teste não pode vazar no outro."""
    f1._MOTOR_CACHE.clear()
    yield
    f1._MOTOR_CACHE.clear()


# -- 2.1 identidade -------------------------------------------------------

def test_identidade_nao_invoca_semgrep_mais_de_uma_vez(monkeypatch):
    """Descobrir a versão custa uma invocação; a Fase 1 roda centenas de casos."""
    chamadas = []
    monkeypatch.setattr(f1, "_versao_semgrep",
                        lambda: chamadas.append(1) or "1.167.0")
    monkeypatch.setattr(f1, "_binario_pro_presente", lambda: False)

    for _ in range(50):
        f1.motor_corrente()

    assert len(chamadas) == 1


def test_identidade_declara_edicao_versao_e_modo(monkeypatch):
    monkeypatch.setattr(f1, "_versao_semgrep", lambda: "1.167.0")
    monkeypatch.setattr(f1, "_binario_pro_presente", lambda: True)

    ce = f1.motor_corrente(entre_arquivos=False)
    assert (ce.edicao, ce.versao, ce.entre_arquivos) == ("ce", "1.167.0", False)

    f1._MOTOR_CACHE.clear()
    pro = f1.motor_corrente(entre_arquivos=True)
    assert (pro.edicao, pro.versao, pro.entre_arquivos) == ("pro", "1.167.0", True)


def test_identidade_e_serializavel(monkeypatch):
    """Vai para o cache e para o manifesto: precisa sobreviver a json.dumps."""
    monkeypatch.setattr(f1, "_versao_semgrep", lambda: "1.167.0")
    monkeypatch.setattr(f1, "_binario_pro_presente", lambda: False)
    d = f1.motor_corrente().como_dict()
    assert json.loads(json.dumps(d)) == d
    assert set(d) == {"edicao", "versao", "entre_arquivos",
                      "binario_pro_disponivel"}


def test_identidade_registra_presenca_do_binario_pro(monkeypatch):
    """Medido: instalar o binário mudou o comportamento do CE nesta máquina."""
    monkeypatch.setattr(f1, "_versao_semgrep", lambda: "1.167.0")
    monkeypatch.setattr(f1, "_binario_pro_presente", lambda: True)
    assert f1.motor_corrente().binario_pro_disponivel is True

    f1._MOTOR_CACHE.clear()
    monkeypatch.setattr(f1, "_binario_pro_presente", lambda: False)
    assert f1.motor_corrente().binario_pro_disponivel is False


# -- 2.2 invocação --------------------------------------------------------

def test_invocacao_padrao_e_identica_a_de_antes_da_mudanca():
    """As Rodadas 1–3 mediram ESTA linha. Um argumento a mais as invalidaria."""
    esperado = [f1.SEMGREP, "--config", f1.SEMGREP_CONFIG, "--sarif",
                "--quiet", "/tmp/alvo.go"]
    assert f1.montar_comando("/tmp/alvo.go") == esperado
    assert f1.montar_comando("/tmp/alvo.go", entre_arquivos=False) == esperado


def test_modo_entre_arquivos_acrescenta_pro_e_nada_mais():
    padrao = f1.montar_comando("/tmp/alvo.go")
    ligado = f1.montar_comando("/tmp/alvo.go", entre_arquivos=True)
    assert [a for a in ligado if a != "--pro"] == padrao
    assert ligado.count("--pro") == 1


def test_modo_desligado_por_padrao():
    """Comparabilidade só se perde quando alguém decidir perdê-la."""
    assert "--pro" not in f1.montar_comando("/tmp/alvo.go")


# -- 2.3 falha cedo sem viabilidade --------------------------------------

def _grava_registro(tmp_path, classificacao, nome="viabilidade_pro_20260915.json"):
    destino = tmp_path / nome
    destino.write_text(json.dumps({"classificacao": classificacao,
                                   "data": "2026-09-15T23:04:28+00:00"}),
                       encoding="utf-8")
    return destino


def test_sem_registro_algum_levanta_erro_explicito(tmp_path):
    with pytest.raises(f1.ModoIndisponivelError) as e:
        f1.exigir_viabilidade(str(tmp_path))
    assert "verificar_pro.py" in str(e.value)


def test_registro_inconclusivo_nao_autoriza(tmp_path):
    """Resultado ambíguo NÃO é sucesso: não autoriza, igual a indisponível."""
    _grava_registro(tmp_path, "inconclusivo")
    with pytest.raises(f1.ModoIndisponivelError):
        f1.exigir_viabilidade(str(tmp_path))


def test_registro_indisponivel_nao_autoriza(tmp_path):
    _grava_registro(tmp_path, "indisponivel")
    with pytest.raises(f1.ModoIndisponivelError):
        f1.exigir_viabilidade(str(tmp_path))


def test_registro_viavel_autoriza(tmp_path):
    caminho = _grava_registro(tmp_path, "viavel")
    obtido, dados = f1.exigir_viabilidade(str(tmp_path))
    assert obtido == str(caminho)
    assert dados["classificacao"] == "viavel"


def test_registro_mais_recente_prevalece(tmp_path):
    """Verificação nova manda sobre antiga — o nome carrega a data."""
    _grava_registro(tmp_path, "viavel", "viabilidade_pro_20260101.json")
    _grava_registro(tmp_path, "indisponivel", "viabilidade_pro_20260915.json")
    with pytest.raises(f1.ModoIndisponivelError):
        f1.exigir_viabilidade(str(tmp_path))


def test_registro_corrompido_e_ignorado_nao_derruba(tmp_path):
    (tmp_path / "viabilidade_pro_20260916.json").write_text("{lixo",
                                                            encoding="utf-8")
    _grava_registro(tmp_path, "viavel", "viabilidade_pro_20260915.json")
    caminho, _ = f1.exigir_viabilidade(str(tmp_path))
    assert caminho.endswith("viabilidade_pro_20260915.json")


def test_diretorio_inexistente_levanta_em_vez_de_autorizar(tmp_path):
    ausente = os.path.join(str(tmp_path), "nao-existe")
    with pytest.raises(f1.ModoIndisponivelError):
        f1.exigir_viabilidade(ausente)


# -- entrada legada (D3) --------------------------------------------------

def test_payload_sem_identidade_e_lido_como_ce():
    """O oposto da regra de pareamento, e deliberadamente (ver D3)."""
    motor = f1.motor_de_payload({"status_semgrep": "NAO_DETECTADO"})
    assert motor.edicao == "ce"
    assert motor.entre_arquivos is False


def test_payload_com_identidade_e_lido_como_gravado():
    motor = f1.motor_de_payload({"motor": {
        "edicao": "pro", "versao": "1.167.0", "entre_arquivos": True,
        "binario_pro_disponivel": True}})
    assert (motor.edicao, motor.entre_arquivos) == ("pro", True)
