"""Testes da comparação entre o braço de filtro e o de triagem (tarefa 5b.5).

Este script produz o número que a monografia vai chamar de "teto do desenho de
filtro puro". Um número desses errado não se manifesta como falha — se manifesta
como uma frase confiante e falsa no capítulo de resultados. Os valores aqui são
conferidos à mão no corpo de cada teste.
"""
import csv
import math

import pytest

from scripts.comparar_filtro_triagem import (
    comparar,
    controles_pareados,
    recall_do_componente,
    recall_do_sistema,
    tra_da_pilha,
)
from src.fase5_auditoria import (
    CABECALHO,
    classificar_acerto_llm,
    classificar_cobertura_semgrep,
)
from src.metricas import carregar

MODELO = "ollama:qwen2.5-coder:7b"


def linha(id_, gabarito, veredito, procedencia="alerta", status="DETECTADO",
          prompt="especialista"):
    detectado = status == "DETECTADO"
    return {
        "ID_Caso": id_, "Repositorio": "acme/s", "CWE": "CWE-327",
        "Origem": "TP_ouro" if gabarito == "vulneravel" else "FP",
        "Modelo_LLM": MODELO, "Tipo_Prompt": prompt,
        "Gabarito": gabarito, "Status_Semgrep": status,
        "Classificacao_Semgrep": classificar_cobertura_semgrep(gabarito,
                                                               detectado),
        "Veredito_LLM": veredito,
        "Classificacao_LLM": (classificar_acerto_llm(gabarito, veredito)
                              if veredito in ("VP", "FP") else "N/A"),
        "Tempo_Execucao_s": "1.00", "Justificativa": "j", "Num_Locations": "1",
        "Ficha_CWE": "especifica", "Versao_Prompt": f"{prompt}:1",
        "Hash_Catalogo": "h", "Tokens_Entrada": "1", "Tokens_Saida": "1",
        "Custo_USD": "0", "Motivo_Nao_Deteccao": "N/A" if detectado
        else "SEM_ALERTA", "Regras_Nao_Casadas": "",
        "Procedencia": procedencia,
    }


def gravar(pasta, linhas, cabecalho=CABECALHO, prompt="especialista"):
    pasta.mkdir(parents=True, exist_ok=True)
    caminho = pasta / f"{MODELO.replace(':', '-')}__{prompt}.csv"
    with open(caminho, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cabecalho, extrasaction="ignore")
        w.writeheader()
        for ln in linhas:
            w.writerow(ln)


# --- recall do sistema: os não-avaliados contam como perdidos ---------------

def test_recall_do_sistema_conta_o_que_nunca_chegou_ao_llm(tmp_path):
    """É o ponto do número: para quem usa a ferramenta, vulnerabilidade não
    reportada é não reportada, tenha o LLM opinado ou não."""
    linhas = [linha("v1", "vulneravel", "VP")]
    linhas += [linha(f"n{i}", "vulneravel", "N/A", procedencia="N/A",
                     status="NAO_DETECTADO") for i in range(9)]
    gravar(tmp_path / "r", linhas)
    (br,) = carregar(str(tmp_path / "r"))
    m = recall_do_sistema(br, universo=10)
    assert m["VP"] == 1
    assert m["recall"] == pytest.approx(0.10)


def test_recall_do_componente_olha_so_quem_recebeu_veredito(tmp_path):
    """Mesmo braço do teste acima: 1 de 1 avaliado, e não 1 de 10."""
    linhas = [linha("v1", "vulneravel", "VP")]
    linhas += [linha(f"n{i}", "vulneravel", "N/A", procedencia="N/A",
                     status="NAO_DETECTADO") for i in range(9)]
    gravar(tmp_path / "r", linhas)
    (br,) = carregar(str(tmp_path / "r"))
    m = recall_do_componente(br)
    assert (m["n"], m["VP"], m["FN"]) == (1, 1, 0)
    assert m["recall"] == pytest.approx(1.0)


# --- TRA: a armadilha da composição -----------------------------------------

def test_tra_ignora_os_injetados(tmp_path):
    """Injetado nunca foi alerta. Incluí-lo mudaria a TRA por composição, não
    por comportamento — que é o erro que este recorte existe para evitar."""
    # Pilha de alertas: 6 seguros descartados (VN), 4 mantidos (FP) -> TRA 0,60
    linhas = [linha(f"s{i}", "seguro", "FP") for i in range(6)]
    linhas += [linha(f"t{i}", "seguro", "VP") for i in range(4)]
    # 100 injetados, todos descartados. Se entrassem, a TRA iria a ~0,96.
    linhas += [linha(f"g{i}", "vulneravel", "FP", procedencia="gabarito",
                     status="NAO_DETECTADO") for i in range(100)]
    gravar(tmp_path / "r", linhas)
    (br,) = carregar(str(tmp_path / "r"))
    m = tra_da_pilha(br, so_alerta=True)
    assert m["total"] == 10
    assert m["tra"] == pytest.approx(0.60)


def test_tra_sem_filtro_usa_tudo(tmp_path):
    """É o caso das rodadas anteriores à coluna: lá toda linha veio de alerta,
    e filtrar por uma coluna inexistente zeraria a conta."""
    linhas = [linha(f"s{i}", "seguro", "FP") for i in range(6)]
    linhas += [linha(f"t{i}", "seguro", "VP") for i in range(4)]
    gravar(tmp_path / "r", linhas, cabecalho=CABECALHO[:-1])
    (br,) = carregar(str(tmp_path / "r"))
    assert tra_da_pilha(br, so_alerta=False)["tra"] == pytest.approx(0.60)
    # Com o filtro ligado, o mesmo CSV antigo daria zero — por isso a flag.
    assert tra_da_pilha(br, so_alerta=True)["total"] == 0


def test_tra_vazia_e_nan_e_nao_zero(tmp_path):
    gravar(tmp_path / "r", [linha("g0", "vulneravel", "FP",
                                  procedencia="gabarito",
                                  status="NAO_DETECTADO")])
    (br,) = carregar(str(tmp_path / "r"))
    assert math.isnan(tra_da_pilha(br, so_alerta=True)["tra"])


# --- controle pareado: o preço do D7 ----------------------------------------

def _duas_rodadas(tmp_path, vereditos_filtro, vereditos_triagem):
    f = tmp_path / "filtro"
    t = tmp_path / "triagem"
    gravar(f, [linha(f"c{i}", "vulneravel", v)
               for i, v in enumerate(vereditos_filtro)])
    gravar(t, [linha(f"c{i}", "vulneravel", v)
               for i, v in enumerate(vereditos_triagem)])
    return ({br.rotulo: br for br in carregar(str(f))},
            {br.rotulo: br for br in carregar(str(t))})


def test_controle_pareado_mede_a_queda_nos_mesmos_casos(tmp_path):
    """4 VP com contexto do alerta, 1 VP com contexto só de código."""
    f, t = _duas_rodadas(tmp_path,
                         ["VP", "VP", "VP", "VP", "FP"],
                         ["VP", "FP", "FP", "FP", "FP"])
    (d,) = controles_pareados(f, t).values()
    assert d["n"] == 5
    assert (d["vp_filtro"], d["vp_triagem"], d["delta"]) == (4, 1, -3)
    assert len(d["perdidos"]) == 3
    assert d["ganhos"] == []


def test_controle_pareado_registra_ganhos(tmp_path):
    f, t = _duas_rodadas(tmp_path, ["FP", "FP"], ["VP", "FP"])
    (d,) = controles_pareados(f, t).values()
    assert d["delta"] == 1
    assert len(d["ganhos"]) == 1


def test_controle_pareado_so_usa_casos_presentes_nos_dois(tmp_path):
    """Um caso que só existe numa das rodadas não é evidência sobre a
    diferença entre elas."""
    f = tmp_path / "filtro"
    t = tmp_path / "triagem"
    gravar(f, [linha("c0", "vulneravel", "VP"), linha("so_filtro",
                                                      "vulneravel", "VP")])
    gravar(t, [linha("c0", "vulneravel", "FP"), linha("so_triagem",
                                                      "vulneravel", "FP")])
    (d,) = controles_pareados({b.rotulo: b for b in carregar(str(f))},
                              {b.rotulo: b for b in carregar(str(t))}).values()
    assert d["n"] == 1


def test_controle_pareado_ignora_injetados(tmp_path):
    """Injetado não tem par no braço de filtro, por definição: lá ele nunca
    chegou ao LLM. Incluí-lo inventaria uma comparação."""
    f = tmp_path / "filtro"
    t = tmp_path / "triagem"
    gravar(f, [linha("c0", "vulneravel", "VP")])
    gravar(t, [linha("c0", "vulneravel", "VP"),
               linha("g0", "vulneravel", "VP", procedencia="gabarito",
                     status="NAO_DETECTADO")])
    (d,) = controles_pareados({b.rotulo: b for b in carregar(str(f))},
                              {b.rotulo: b for b in carregar(str(t))}).values()
    assert d["n"] == 1


def test_controle_pareado_ignora_sem_veredito(tmp_path):
    f, t = _duas_rodadas(tmp_path, ["VP", "N/A"], ["VP", "VP"])
    (d,) = controles_pareados(f, t).values()
    assert d["n"] == 1


# --- o teto, ponta a ponta ---------------------------------------------------

def test_teto_e_a_diferenca_dos_recalls_de_sistema(tmp_path):
    """População de 10 vulneráveis. No filtro só 2 chegam ao LLM e 1 acerta
    (recall de sistema 0,10). Na triagem os 10 chegam e 4 acertam (0,40).
    Teto = +0,30."""
    f = tmp_path / "filtro"
    t = tmp_path / "triagem"
    gravar(f, [linha("c0", "vulneravel", "VP"), linha("c1", "vulneravel", "FP")]
           + [linha(f"c{i}", "vulneravel", "N/A", procedencia="N/A",
                    status="NAO_DETECTADO") for i in range(2, 10)])
    gravar(t, [linha("c0", "vulneravel", "VP"), linha("c1", "vulneravel", "FP")]
           + [linha(f"c{i}", "vulneravel", "VP" if i < 5 else "FP",
                    procedencia="gabarito", status="NAO_DETECTADO")
              for i in range(2, 10)])
    r = comparar(str(f), str(t))
    assert r["universo_vulneravel"] == 10
    (b,) = r["bracos"]
    assert b["filtro"]["recall_sistema"]["recall"] == pytest.approx(0.10)
    assert b["triagem"]["recall_sistema"]["recall"] == pytest.approx(0.40)
    assert b["teto"] == pytest.approx(0.30)


def test_bracos_sem_par_ficam_de_fora_e_sao_avisados(tmp_path):
    f = tmp_path / "filtro"
    t = tmp_path / "triagem"
    gravar(f, [linha("c0", "vulneravel", "VP")], prompt="especialista")
    gravar(t, [linha("c0", "vulneravel", "VP", prompt="baseline")],
           prompt="baseline")
    r = comparar(str(f), str(t))
    assert r["bracos"] == []
    assert r["so_no_filtro"] and r["so_na_triagem"]
