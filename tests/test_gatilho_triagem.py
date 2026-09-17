"""Testes do gatilho da rodada de triagem.

O gatilho decide sozinho quando ocupar a máquina por horas. Os dois erros que
importam são simétricos e ambos caros: disparar cedo atropela a esteira alheia,
e nunca disparar deixa a rodada sem acontecer. É o que estes testes cobrem.
"""
import csv

import pytest

from scripts.gatilho_rodada_triagem import (
    RUN_ID,
    concorrentes,
    estado,
    portao_do_controle,
)
from src.fase5_auditoria import CABECALHO, classificar_acerto_llm

SEMGREP = (1001, r"C:\Python\Scripts\semgrep.exe --config p/default --sarif")
CORE = (1002, r"C:\Python\Lib\site-packages\semgrep\bin\semgrep-core.exe -json")
VERIFICAR = (1003, r"C:\Python\python.exe scripts/verificar_pro.py --etapa gabarito")
NAVEGADOR = (1004, r"C:\Program Files\Firefox\firefox.exe")
EDITOR = (1005, r"C:\Users\x\AppData\Local\Programs\Code\Code.exe")


# --- quem conta como concorrente -------------------------------------------

def test_semgrep_em_qualquer_forma_conta():
    achados = concorrentes([SEMGREP, CORE, NAVEGADOR])
    assert {pid for pid, _, _ in achados} == {1001, 1002}


def test_script_pesado_do_projeto_conta():
    assert [pid for pid, _, _ in concorrentes([VERIFICAR])] == [1003]


def test_processo_qualquer_nao_conta():
    assert concorrentes([NAVEGADOR, EDITOR]) == []


def test_a_propria_rodada_nao_conta_como_concorrente():
    """Senão o gatilho se veria ocupado pelo trabalho que ele mesmo disparou —
    e a segunda etapa nunca começaria."""
    nossa = (2001, f"python run_pipeline.py --tudo --run-id {RUN_ID}")
    assert concorrentes([nossa]) == []


def test_shell_hospedeiro_nao_conta():
    """Um shell do harness que sobreviva a um comando já terminado carrega a
    linha de comando dele; contá-lo deixaria o gatilho ocupado para sempre."""
    hospedeiro = (3001, r'bash.exe -c "source /c/Users/x/.claude/shell-snapshots/'
                        r'snap.sh; python scripts/verificar_pro.py"')
    assert concorrentes([hospedeiro]) == []


def test_o_proprio_gatilho_nao_conta():
    import os
    eu = (os.getpid(), "python scripts/gatilho_rodada_triagem.py")
    assert concorrentes([eu]) == []


# --- o que fazer quando não dá para enxergar --------------------------------

def test_falha_ao_ler_processos_e_indeterminado_e_nao_livre(monkeypatch):
    """Na dúvida, espera. Disparar porque a leitura falhou seria o pior caso."""
    import scripts.gatilho_rodada_triagem as g
    monkeypatch.setattr(g, "processos", lambda: None)
    livre, motivo = estado(8.0)
    assert livre is None
    assert "processos" in motivo


def test_ram_insuficiente_segura_o_gatilho(monkeypatch):
    import scripts.gatilho_rodada_triagem as g
    monkeypatch.setattr(g, "processos", lambda: [NAVEGADOR])
    monkeypatch.setattr(g, "ram_livre_gb", lambda: 2.0)
    livre, motivo = estado(8.0)
    assert livre is False
    assert "RAM livre" in motivo


def test_maquina_ociosa_com_ram_libera(monkeypatch):
    import scripts.gatilho_rodada_triagem as g
    monkeypatch.setattr(g, "processos", lambda: [NAVEGADOR, EDITOR])
    monkeypatch.setattr(g, "ram_livre_gb", lambda: 20.0)
    livre, _ = estado(8.0)
    assert livre is True


# --- o portão da tarefa 5.5 -------------------------------------------------

def _linha(id_, gabarito, veredito, procedencia, status="DETECTADO"):
    return {
        "ID_Caso": id_, "Repositorio": "acme/s", "CWE": "CWE-327",
        "Origem": "TP_ouro", "Modelo_LLM": "m", "Tipo_Prompt": "especialista",
        "Gabarito": gabarito, "Status_Semgrep": status,
        "Classificacao_Semgrep": "Semgrep VP (detectou vuln real)",
        "Veredito_LLM": veredito,
        "Classificacao_LLM": classificar_acerto_llm(gabarito, veredito),
        "Tempo_Execucao_s": "1.00", "Justificativa": "j", "Num_Locations": "1",
        "Ficha_CWE": "especifica", "Versao_Prompt": "e:1", "Hash_Catalogo": "h",
        "Tokens_Entrada": "1", "Tokens_Saida": "1", "Custo_USD": "0",
        "Motivo_Nao_Deteccao": "N/A", "Regras_Nao_Casadas": "",
        "Procedencia": procedencia,
    }


@pytest.fixture
def rodada_falsa(tmp_path, monkeypatch):
    """Escreve uma rodada em `<tmp>/results/<RUN_ID>/` e aponta o gatilho nela."""
    import scripts.gatilho_rodada_triagem as g
    monkeypatch.setattr(g, "BASE", str(tmp_path))

    def _escrever(linhas):
        d = tmp_path / "results" / RUN_ID
        d.mkdir(parents=True, exist_ok=True)
        with open(d / "m__especialista.csv", "w", newline="",
                  encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=CABECALHO, extrasaction="ignore")
            w.writeheader()
            for ln in linhas:
                w.writerow(ln)
    return _escrever


def test_portao_abre_quando_as_procedencias_concordam(rodada_falsa):
    # alerta: 8 VP / 2 FN = 0,80   |   gabarito: 7 VP / 3 FN = 0,70
    linhas = [_linha(f"a{i}", "vulneravel", "VP" if i < 8 else "FP", "alerta")
              for i in range(10)]
    linhas += [_linha(f"g{i}", "vulneravel", "VP" if i < 7 else "FP",
                      "gabarito", status="NAO_DETECTADO") for i in range(10)]
    rodada_falsa(linhas)
    passou, explicacao = portao_do_controle(0.25)
    assert passou, explicacao
    assert "dentro do limiar" in explicacao


def test_portao_fecha_quando_o_injetado_vai_muito_melhor(rodada_falsa):
    """O caso que a tarefa 5.5 existe para pegar: acerto sistematicamente maior
    nos injetados não vem do código, vem da montagem."""
    linhas = [_linha(f"a{i}", "vulneravel", "FP", "alerta") for i in range(10)]
    linhas += [_linha(f"g{i}", "vulneravel", "VP", "gabarito",
                      status="NAO_DETECTADO") for i in range(10)]
    rodada_falsa(linhas)
    passou, explicacao = portao_do_controle(0.25)
    assert not passou
    assert "acusa artefato" in explicacao


def test_portao_NAO_fecha_quando_o_injetado_vai_muito_pior(rodada_falsa, caplog):
    """O portão é direcional. Injetado indo PIOR não é o artefato que a 5.5
    barra — é consistente com o Semgrep detectar as vulnerabilidades mais
    fáceis. Bloquear aqui gastaria o portão na direção errada; o que se faz é
    avisar alto."""
    linhas = [_linha(f"a{i}", "vulneravel", "VP", "alerta") for i in range(10)]
    linhas += [_linha(f"g{i}", "vulneravel", "FP", "gabarito",
                      status="NAO_DETECTADO") for i in range(10)]
    rodada_falsa(linhas)
    import logging
    with caplog.at_level(logging.WARNING):
        passou, explicacao = portao_do_controle(0.25)
    assert passou, explicacao
    assert "MUITO MENOS nos injetados" in caplog.text


def test_portao_fecha_com_controle_vazio(rodada_falsa):
    """Sem controle não há o que concluir — e seguir seria gastar as horas que
    a tarefa manda não gastar."""
    rodada_falsa([_linha(f"g{i}", "vulneravel", "VP", "gabarito",
                         status="NAO_DETECTADO") for i in range(10)])
    passou, explicacao = portao_do_controle(0.25)
    assert not passou
    assert "VAZIO" in explicacao


def test_portao_fecha_sem_injetados(rodada_falsa):
    rodada_falsa([_linha(f"a{i}", "vulneravel", "VP", "alerta")
                  for i in range(10)])
    passou, explicacao = portao_do_controle(0.25)
    assert not passou
    assert "nenhum candidato injetado" in explicacao


def test_portao_usa_o_pior_braco(rodada_falsa, tmp_path):
    """Um braço limpo não absolve o outro: basta um acusar para o portão fechar."""
    d = tmp_path / "results" / RUN_ID
    d.mkdir(parents=True, exist_ok=True)
    bom = [_linha(f"a{i}", "vulneravel", "VP", "alerta") for i in range(10)]
    bom += [_linha(f"g{i}", "vulneravel", "VP", "gabarito",
                   status="NAO_DETECTADO") for i in range(10)]
    ruim = [_linha(f"a{i}", "vulneravel", "FP", "alerta") for i in range(10)]
    ruim += [_linha(f"g{i}", "vulneravel", "VP", "gabarito",
                    status="NAO_DETECTADO") for i in range(10)]
    for nome, linhas in (("m__baseline.csv", ruim),
                         ("m__especialista.csv", bom)):
        for ln in linhas:
            ln["Tipo_Prompt"] = nome.split("__")[1].removesuffix(".csv")
        with open(d / nome, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=CABECALHO, extrasaction="ignore")
            w.writeheader()
            for ln in linhas:
                w.writerow(ln)
    passou, _ = portao_do_controle(0.25)
    assert not passou
