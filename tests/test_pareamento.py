"""Testes da regra de pareamento da Fase 1 (tarefas 1.1 a 1.6).

A Fase 1 tem uma única decisão: dado o arquivo-alvo e a CWE do gabarito, dizer
QUAL alerta do Semgrep é o alerta daquele caso. Se ela erra, nada a jusante
percebe — o LLM responde corretamente sobre o alerta que viu e a auditoria conta
o acerto como erro. Por isso os testes são sobre SARIF sintético: o que importa
é a decisão, não o motor.
"""
import json
import subprocess

import pytest

from src import fase1_semgrep
from src.fase1_semgrep import (
    ALERTA_OUTRA_CWE,
    MOTIVO_NA,
    SEM_ALERTA,
    ResultadoFase1,
    _cwe_nas_tags,
)

MD5 = "go.lang.security.audit.crypto.use-of-md5"
EXEC = "go.lang.security.audit.dangerous-exec-command"
RAND = "go.lang.security.audit.crypto.math-random-used"


def _sarif(*alertas):
    """SARIF sintético. Cada alerta é `(ruleId, tags, linha)`."""
    regras, vistos, results = [], set(), []
    for rule_id, tags, linha in alertas:
        if rule_id not in vistos:
            vistos.add(rule_id)
            regras.append({"id": rule_id, "properties": {"tags": list(tags)}})
        results.append({
            "ruleId": rule_id,
            "message": {"text": f"mensagem de {rule_id}"},
            "locations": [{"physicalLocation": {"region": {"startLine": linha}}}],
        })
    return {"runs": [{"tool": {"driver": {"rules": regras}}, "results": results}]}


@pytest.fixture
def rodar(tmp_path, monkeypatch):
    """Executa a Fase 1 com o Semgrep substituído por um SARIF fixo."""
    alvo = tmp_path / "servico.go"
    alvo.write_text("package main\n", encoding="utf-8")

    def _rodar(sarif, cwe, returncode=1, stdout=None, stderr=b""):
        bruto = (json.dumps(sarif).encode("utf-8") if stdout is None
                 else stdout)

        def _run(cmd, **kw):
            return subprocess.CompletedProcess(cmd, returncode, bruto, stderr)

        monkeypatch.setattr(subprocess, "run", _run)
        return fase1_semgrep.executar_semgrep(str(alvo), cwe)

    return _rodar


# --- 1.1 Casamento por identificador completo -------------------------------

def test_casamento_exige_o_identificador_inteiro():
    assert _cwe_nas_tags(["CWE-77: Command Injection"], "CWE-77")
    assert not _cwe_nas_tags(["CWE-770: Allocation of Resources"], "CWE-77")


@pytest.mark.parametrize("gabarito,tag", [
    ("CWE-20", "CWE-200: Exposure of Sensitive Information"),
    ("CWE-20", "CWE-209: Generation of Error Message"),
    ("CWE-77", "CWE-770: Allocation of Resources Without Limits"),
    ("CWE-79", "CWE-798: Use of Hard-coded Credentials"),
])
def test_prefixo_de_cwe_nao_e_casamento(gabarito, tag, rodar):
    """Os quatro pares em que um identificador é prefixo de outro existem na
    população. Sob casamento textual o caso emparelharia à regra errada, e o
    resultado seria indistinguível de um emparelhamento legítimo no CSV."""
    assert not _cwe_nas_tags([tag], gabarito)
    r = rodar(_sarif((MD5, [tag], 10)), gabarito)
    assert r.alerta is None
    assert r.motivo == ALERTA_OUTRA_CWE


def test_zeros_a_esquerda_sao_a_mesma_cwe():
    assert _cwe_nas_tags(["CWE-077: Command Injection"], "CWE-77")


def test_tag_sem_cwe_nao_casa():
    assert not _cwe_nas_tags(["security", "owasp", ""], "CWE-77")


# --- 1.2 / 1.4 Emparelhamento e motivo --------------------------------------

def test_alerta_com_a_cwe_do_gabarito_emparelha(rodar):
    r = rodar(_sarif((MD5, ["CWE-327: Broken Crypto"], 42)), "CWE-327")
    assert r.alerta["check_id"] == MD5
    assert r.alerta["start"]["line"] == 42
    assert r.motivo == MOTIVO_NA
    assert r.regras_nao_casadas == []


def test_alerta_unico_de_outra_cwe_nao_emparelha(rodar):
    """O fallback antigo aceitava este alerta só por ser o único do arquivo —
    e era assim que um alerta sem relação com a fraqueza rotulada chegava ao
    LLM para ser pontuado contra o gabarito errado."""
    r = rodar(_sarif((RAND, ["CWE-338: Weak PRNG"], 7)), "CWE-327")
    assert r.alerta is None
    assert r.motivo == ALERTA_OUTRA_CWE
    assert r.regras_nao_casadas == [RAND]


def test_varios_alertas_e_um_casa(rodar):
    r = rodar(_sarif((RAND, ["CWE-338: Weak PRNG"], 3),
                     (MD5, ["CWE-327: Broken Crypto"], 42),
                     (EXEC, ["CWE-78: OS Command Injection"], 90)), "CWE-327")
    assert r.alerta["check_id"] == MD5
    assert r.motivo == MOTIVO_NA
    assert r.regras_nao_casadas == []


def test_varios_alertas_e_nenhum_casa(rodar):
    r = rodar(_sarif((RAND, ["CWE-338: Weak PRNG"], 3),
                     (EXEC, ["CWE-78: OS Command Injection"], 90)), "CWE-327")
    assert r.alerta is None
    assert r.motivo == ALERTA_OUTRA_CWE
    assert r.regras_nao_casadas == sorted([RAND, EXEC])


def test_arquivo_sem_alerta_algum(rodar):
    r = rodar(_sarif(), "CWE-327")
    assert r == ResultadoFase1(None, SEM_ALERTA, [])


def test_regra_sem_tag_de_cwe_nao_emparelha(rodar):
    """Ausência de tag não é evidência de que o alerta seja o do caso, mesmo
    quando ele é o único do arquivo."""
    r = rodar(_sarif((MD5, ["security", "audit"], 42)), "CWE-327")
    assert r.alerta is None
    assert r.motivo == ALERTA_OUTRA_CWE
    assert r.regras_nao_casadas == [MD5]


def test_regras_nao_casadas_deduplicadas_e_alfabeticas(rodar):
    """Alfabética e não por ordem de aparição: o campo existe para comparar
    CSVs de rodadas diferentes linha a linha."""
    r = rodar(_sarif((RAND, ["CWE-338: Weak PRNG"], 30),
                     (EXEC, ["CWE-78: OS Command Injection"], 5),
                     (RAND, ["CWE-338: Weak PRNG"], 60)), "CWE-327")
    assert r.regras_nao_casadas == sorted([EXEC, RAND])
    assert len(r.regras_nao_casadas) == 2


def test_sem_alerta_nao_lista_regras(rodar):
    """Campo vazio em `SEM_ALERTA` não pode ser confundido com falta de
    informação sobre um caso `ALERTA_OUTRA_CWE`."""
    assert rodar(_sarif(), "CWE-327").regras_nao_casadas == []


# --- 1.3 Escolha determinística ---------------------------------------------

def test_ordem_do_sarif_nao_muda_o_alerta_escolhido(rodar):
    """A ordem de saída do Semgrep é estável na prática, mas é detalhe interno
    da ferramenta. A escolha é por `(linha, check_id)`."""
    alertas = [(MD5, ["CWE-327: Broken Crypto"], 90),
               (EXEC, ["CWE-327: Broken Crypto"], 12),
               (RAND, ["CWE-338: Weak PRNG"], 1)]
    escolhidos = set()
    for i in range(len(alertas)):
        embaralhado = alertas[i:] + alertas[:i]
        r = rodar(_sarif(*embaralhado), "CWE-327")
        escolhidos.add((r.alerta["check_id"], r.alerta["start"]["line"]))
    assert escolhidos == {(EXEC, 12)}      # menor linha entre os que casam


def test_desempate_por_check_id_na_mesma_linha(rodar):
    alertas = [(MD5, ["CWE-327: Broken Crypto"], 42),
               (EXEC, ["CWE-327: Broken Crypto"], 42)]
    primeiro = rodar(_sarif(*alertas), "CWE-327").alerta["check_id"]
    segundo = rodar(_sarif(*reversed(alertas)), "CWE-327").alerta["check_id"]
    assert primeiro == segundo == min(MD5, EXEC)


# --- 1.4 Contrato do retorno ------------------------------------------------

def test_retorno_e_tupla_nomeada(rodar):
    r = rodar(_sarif((MD5, ["CWE-327: Broken Crypto"], 42)), "CWE-327")
    assert isinstance(r, ResultadoFase1)
    assert r[0] is r.alerta and r[1] == r.motivo and r[2] == r.regras_nao_casadas


def test_erro_de_esteira_continua_subindo(rodar):
    """rc inesperado sem alerta algum é falha de esteira, não NAO_DETECTADO:
    confundir os dois contaminaria a matriz de cobertura com um FN falso."""
    with pytest.raises(fase1_semgrep.SemgrepError):
        rodar(_sarif(), "CWE-327", returncode=2)


# --- Saída inválida é falha de esteira, não silêncio do motor ---------------
#
# A distinção importa porque `SEM_ALERTA` é gravado no cache e vira ponto cego
# PERMANENTE do Semgrep, enquanto a falha de esteira não é cacheada e o caso é
# recomputado. Um `settings.yml` corrompido por queda de energia fez o Semgrep
# sair com rc=1 e stdout vazio, e 200 casos viraram não-detecção falsa.

@pytest.mark.parametrize("stdout,rotulo", [
    (b"", "stdout vazio"),
    (b"   \n", "stdout em branco"),
    (b"Traceback (most recent call last):\n  File ...", "traceback em vez de JSON"),
    (b"{}", "JSON sem 'runs'"),
    (b'{"erro": "settings ilegivel"}', "JSON de erro sem 'runs'"),
])
def test_saida_invalida_nao_vira_sem_alerta(rodar, stdout, rotulo):
    with pytest.raises(fase1_semgrep.SemgrepError):
        rodar(None, "CWE-327", returncode=1, stdout=stdout)


def test_sarif_vazio_legitimo_continua_sendo_sem_alerta(rodar):
    """O contraponto: SARIF bem formado com zero achados é silêncio de verdade
    do motor, e tem que continuar sendo `SEM_ALERTA`."""
    r = rodar(_sarif(), "CWE-327", returncode=0)
    assert r == ResultadoFase1(None, SEM_ALERTA, [])


def test_mensagem_do_erro_carrega_o_stderr(rodar):
    """Sem o stderr na mensagem, diagnosticar o settings.yml corrompido exigiria
    reproduzir a falha à mão."""
    with pytest.raises(fase1_semgrep.SemgrepError, match="settings.yml"):
        rodar(None, "CWE-327", stdout=b"",
              stderr=b"Bad settings format; settings.yml will be overriden")


def test_arquivo_inexistente(tmp_path):
    with pytest.raises(fase1_semgrep.SemgrepFileNotFoundError):
        fase1_semgrep.executar_semgrep(str(tmp_path / "nao-existe.go"), "CWE-327")
