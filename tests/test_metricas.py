"""Testes das métricas comparativas (tarefas 8.1 a 8.6)."""
import csv
import math
import os

import pytest

from src.fase5_auditoria import (
    CABECALHO,
    classificar_acerto_llm,
    classificar_cobertura_semgrep,
)
from src.metricas import (
    MINIMO_VULNERAVEIS,
    MOTIVO_INDISPONIVEL,
    _binomial_bicaudal,
    _qui_quadrado_yates,
    avisos,
    carregar,
    contar,
    contar_motivos,
    contar_status,
    estratificar,
    exportar_latex,
    mcnemar,
    tabela_bracos,
    vulneraveis_avaliadas,
)

GEMINI = "gemini-2.5-flash-lite"
GPT = "gpt-4o-mini"


def linha(id_, gabarito, veredito, modelo=GEMINI, prompt="especialista",
          status="DETECTADO", origem="FP", num_locations="1",
          ficha="especifica", hash_cat="h1", cwe="CWE-327", custo="0.0001",
          motivo=None, regras=""):
    """Uma linha de CSV coerente: as classificações vêm das funções reais."""
    detectado = status == "DETECTADO"
    if motivo is None:
        motivo = "SEM_ALERTA" if status == "NAO_DETECTADO" else "N/A"
    return {
        "ID_Caso": id_, "Repositorio": "acme/servico", "CWE": cwe,
        "Origem": origem, "Modelo_LLM": modelo, "Tipo_Prompt": prompt,
        "Gabarito": gabarito, "Status_Semgrep": status,
        "Classificacao_Semgrep": (classificar_cobertura_semgrep(gabarito, detectado)
                                  if status in ("DETECTADO", "NAO_DETECTADO")
                                  else "N/A (Falha de Esteira)"),
        "Veredito_LLM": veredito,
        "Classificacao_LLM": (classificar_acerto_llm(gabarito, veredito)
                              if status == "DETECTADO" else "N/A"),
        "Tempo_Execucao_s": "1.00", "Justificativa": "j",
        "Num_Locations": num_locations, "Ficha_CWE": ficha,
        "Versao_Prompt": f"{prompt}:abcd1234", "Hash_Catalogo": hash_cat,
        "Tokens_Entrada": "1000", "Tokens_Saida": "50", "Custo_USD": custo,
        "Motivo_Nao_Deteccao": motivo, "Regras_Nao_Casadas": regras,
    }


def gravar(caminho, linhas, cabecalho=None):
    with open(caminho, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cabecalho or CABECALHO,
                           extrasaction="ignore")
        w.writeheader()
        for ln in linhas:
            w.writerow(ln)


@pytest.fixture
def rodada(tmp_path):
    """Rodada com dois braços sobre a mesma população de 6 casos."""
    d = tmp_path / "run"
    d.mkdir()
    # gemini/especialista: acerta 4, erra 2
    gravar(d / f"{GEMINI}__especialista.csv", [
        linha("c1", "seguro", "FP"),                      # VN acerto
        linha("c2", "seguro", "FP"),                      # VN acerto
        linha("c3", "seguro", "VP"),                      # FP erro
        linha("c4", "vulneravel", "VP", origem="TP_dataset"),   # VP acerto
        linha("c5", "vulneravel", "FP", origem="TP_dataset"),   # FN erro
        linha("c6", "seguro", "N/A", status="NAO_DETECTADO"),
    ])
    # gpt/especialista: acerta 3
    gravar(d / f"{GPT}__especialista.csv", [
        linha("c1", "seguro", "FP", modelo=GPT),
        linha("c2", "seguro", "VP", modelo=GPT),          # discorda: só A acerta
        linha("c3", "seguro", "FP", modelo=GPT),          # discorda: só B acerta
        linha("c4", "vulneravel", "VP", modelo=GPT, origem="TP_dataset"),
        linha("c5", "vulneravel", "FP", modelo=GPT, origem="TP_dataset"),
        linha("c6", "seguro", "N/A", modelo=GPT, status="NAO_DETECTADO"),
    ])
    return d


# --- 8.1 Consolidação e compatibilidade -------------------------------------

def test_carrega_rodada_inteira(rodada):
    bracos = carregar(str(rodada))
    assert len(bracos) == 2
    assert {b.modelo for b in bracos} == {GEMINI, GPT}
    assert all(len(b.linhas) == 6 for b in bracos)


def test_carrega_csv_avulso(rodada):
    bracos = carregar(str(rodada / f"{GEMINI}__especialista.csv"))
    assert len(bracos) == 1
    assert bracos[0].modelo == GEMINI


def test_csv_da_parte1_continua_legivel(tmp_path):
    """Sem as colunas novas e com rótulos em inglês: as métricas saem, e as
    colunas ausentes viram 'indisponível', não erro."""
    p = tmp_path / "parte1.csv"
    antigo = CABECALHO[:13]
    linhas = [
        {**linha("c1", "seguro", "FP"),
         "Classificacao_LLM": "True Negative (Acerto)"},
        {**linha("c2", "seguro", "VP"),
         "Classificacao_LLM": "False Positive (Ruído Mantido)"},
        {**linha("c3", "vulneravel", "VP"),
         "Classificacao_LLM": "True Positive (Acerto)"},
        {**linha("c4", "vulneravel", "FP"),
         "Classificacao_LLM": "False Negative (Falha Crítica)"},
    ]
    gravar(p, linhas, cabecalho=antigo)

    braco = carregar(str(p))[0]
    m = contar(braco.linhas, "llm")
    assert (m["VP"], m["VN"], m["FP"], m["FN"]) == (1, 1, 1, 1)
    assert braco.custo_total() == 0.0        # coluna ausente, não erro
    estratos = estratificar(braco.linhas, "num_locations")
    assert "indisponível" in estratos


def test_metricas_batem_com_o_calculo_manual(rodada):
    braco = next(b for b in carregar(str(rodada)) if b.modelo == GEMINI)
    m = contar(braco.linhas, "llm")
    assert (m["VP"], m["VN"], m["FP"], m["FN"]) == (1, 2, 1, 1)
    assert m["Precisao"] == pytest.approx(0.5)      # 1/(1+1)
    assert m["Recall"] == pytest.approx(0.5)        # 1/(1+1)
    assert m["F1"] == pytest.approx(0.5)
    assert m["TFN"] == pytest.approx(0.5)
    assert m["TRA"] == pytest.approx(3 / 5)         # (VN+FN)/total


def test_matriz_simbolica_e_separada_da_neural(rodada):
    braco = next(b for b in carregar(str(rodada)) if b.modelo == GEMINI)
    sg = contar(braco.linhas, "semgrep")
    llm = contar(braco.linhas, "llm")
    # O NAO_DETECTADO entra só na cobertura simbólica.
    assert sg["Total"] == 6 and llm["Total"] == 5
    assert sg["VN"] == 1     # c6: seguro e não detectado


def test_nao_deteccao_discriminada_por_motivo(tmp_path):
    p = tmp_path / "r.csv"
    gravar(p, [
        linha("c1", "seguro", "N/A", status="NAO_DETECTADO",
              motivo="SEM_ALERTA"),
        linha("c2", "vulneravel", "N/A", status="NAO_DETECTADO",
              motivo="ALERTA_OUTRA_CWE", regras="regra-a;regra-b"),
        linha("c3", "vulneravel", "N/A", status="NAO_DETECTADO",
              motivo="ALERTA_OUTRA_CWE", regras="regra-c"),
        linha("c4", "seguro", "FP"),
    ])
    assert contar_motivos(carregar(str(p))[0].linhas) == {
        "SEM_ALERTA": 1, "ALERTA_OUTRA_CWE": 2}


def test_soma_dos_motivos_e_o_total_de_nao_detectado(rodada):
    """A discriminação não pode mover a matriz de cobertura: ela apenas explica
    a mesma célula."""
    unicas = {}
    for br in carregar(str(rodada)):
        for ln in br.linhas:
            unicas.setdefault(ln["ID_Caso"], ln)
    linhas = list(unicas.values())
    assert sum(contar_motivos(linhas).values()) == \
        contar_status(linhas)["NAO_DETECTADO"]


def test_motivo_conta_cada_caso_uma_vez_so(rodada):
    """Pela mesma razão que a matriz de cobertura não é por braço: o Semgrep
    roda uma vez por caso, não uma por braço."""
    todas = [ln for br in carregar(str(rodada)) for ln in br.linhas]
    assert contar_motivos(todas) == {"SEM_ALERTA": 2}      # c6 nos dois braços
    unicas = list({ln["ID_Caso"]: ln for ln in todas}.values())
    assert contar_motivos(unicas) == {"SEM_ALERTA": 1}


def test_csv_sem_a_coluna_de_motivo_nao_derruba_a_leitura(tmp_path):
    """CSVs anteriores à coluna: o motivo sai como indisponível e as demais
    métricas são calculadas normalmente."""
    p = tmp_path / "legado.csv"
    antigo = CABECALHO[:13]
    gravar(p, [
        linha("c1", "seguro", "N/A", status="NAO_DETECTADO"),
        linha("c2", "vulneravel", "N/A", status="NAO_DETECTADO"),
        linha("c3", "seguro", "FP"),
    ], cabecalho=antigo)

    braco = carregar(str(p))[0]
    assert contar_motivos(braco.linhas) == {MOTIVO_INDISPONIVEL: 2}
    assert contar(braco.linhas, "semgrep")["Total"] == 3


# --- 8.2 Tabela lado a lado -------------------------------------------------

def test_uma_linha_por_braco(rodada):
    cabecalho, linhas = tabela_bracos(carregar(str(rodada)))
    assert len(linhas) == 2
    assert cabecalho[:2] == ["Modelo", "Prompt"]
    assert "Custo USD" in cabecalho
    assert {ln[0] for ln in linhas} == {GEMINI, GPT}


def test_custo_total_por_braco(rodada):
    braco = next(b for b in carregar(str(rodada)) if b.modelo == GEMINI)
    assert braco.custo_total() == pytest.approx(0.0006)   # 6 linhas x 0.0001
    assert braco.tokens() == (6000, 300)


# --- 8.3 Estratificação -----------------------------------------------------

def test_estratifica_por_trilha(rodada):
    braco = next(b for b in carregar(str(rodada)) if b.modelo == GEMINI)
    e = estratificar(braco.linhas, "trilha")
    assert set(e) == {"FP", "TP_dataset"}
    assert e["TP_dataset"]["Total"] == 2


def test_estratifica_por_num_locations(tmp_path):
    p = tmp_path / "r.csv"
    gravar(p, [
        linha("c1", "seguro", "FP", num_locations="1"),
        linha("c2", "seguro", "FP", num_locations="4"),
        linha("c3", "seguro", "VP", num_locations="11"),
    ])
    e = estratificar(carregar(str(p))[0].linhas, "num_locations")
    assert set(e) == {"1 (location única)", "2-6", "7+"}


def test_estratifica_por_ficha_cwe(tmp_path):
    p = tmp_path / "r.csv"
    gravar(p, [
        linha("c1", "seguro", "FP", ficha="especifica"),
        linha("c2", "seguro", "VP", ficha="fallback"),
    ])
    e = estratificar(carregar(str(p))[0].linhas, "ficha_cwe")
    assert set(e) == {"especifica", "fallback"}


# --- 8.4 McNemar ------------------------------------------------------------

def test_binomial_exato_contra_valores_canonicos():
    # n=10, k<=2 caudas: 2 * (1+10+45)/1024
    assert _binomial_bicaudal(8, 2) == pytest.approx(2 * 56 / 1024)
    assert _binomial_bicaudal(0, 0) == 1.0
    assert _binomial_bicaudal(5, 5) == pytest.approx(1.0)
    assert _binomial_bicaudal(1, 0) == pytest.approx(1.0)   # 2*(1+1)/2 = 2 -> 1
    assert _binomial_bicaudal(10, 0) == pytest.approx(2 / 1024)


def test_qui_quadrado_yates_exemplo_canonico():
    """Exemplo clássico de McNemar: b=12, c=5.
    chi2 = (|12-5|-1)^2 / 17 = 36/17 = 2.1176; p ~= 0.1456."""
    x, p = _qui_quadrado_yates(12, 5)
    assert x == pytest.approx(36 / 17)
    assert p == pytest.approx(0.14556, abs=1e-4)


def test_qui_quadrado_yates_segundo_exemplo():
    # b=30, c=10: chi2 = (20-1)^2/40 = 9.025; p ~= 0.002663
    x, p = _qui_quadrado_yates(30, 10)
    assert x == pytest.approx(9.025)
    assert p == pytest.approx(0.002663, abs=1e-5)


def test_escolha_do_teste_pelo_volume_de_discordancias():
    assert _qui_quadrado_yates(0, 0) == (0.0, 1.0)
    # Abaixo de 25 discordâncias o relatório usa o exato; acima, o qui-quadrado.
    from src.metricas import LIMIAR_EXATO
    assert LIMIAR_EXATO == 25


def test_mcnemar_so_conta_amostras_pareadas_com_veredito_valido(rodada):
    a, b = carregar(str(rodada))       # ordenados: gemini, gpt
    r = mcnemar(a, b)
    # c6 é NAO_DETECTADO nos dois: fica fora.
    assert r["n_pareado"] == 5
    assert r["so_a_acerta"] + r["so_b_acerta"] == r["discordancias"] == 2
    assert r["ambos_acertam"] + r["ambos_erram"] + r["discordancias"] == 5
    assert r["teste"] == "binomial exato"
    assert 0 <= r["p_valor"] <= 1


def test_mcnemar_ignora_caso_com_erro_em_um_dos_bracos(tmp_path):
    d = tmp_path / "run"
    d.mkdir()
    gravar(d / "a__especialista.csv", [
        linha("c1", "seguro", "FP", modelo="a"),
        linha("c2", "seguro", "FP", modelo="a"),
    ])
    gravar(d / "b__especialista.csv", [
        linha("c1", "seguro", "VP", modelo="b"),
        linha("c2", "seguro", "ERROR", modelo="b", status="API_ERROR"),
    ])
    r = mcnemar(*carregar(str(d)))
    assert r["n_pareado"] == 1


def test_mcnemar_sem_amostras_pareadas(tmp_path):
    d = tmp_path / "run"
    d.mkdir()
    gravar(d / "a__especialista.csv", [linha("x1", "seguro", "FP", modelo="a")])
    gravar(d / "b__especialista.csv", [linha("y1", "seguro", "FP", modelo="b")])
    r = mcnemar(*carregar(str(d)))
    assert r["n_pareado"] == 0
    assert r["p_valor"] == 1.0


# --- 8.5 Avisos -------------------------------------------------------------

def test_avisa_poder_estatistico_limitado(rodada):
    msgs = avisos(carregar(str(rodada)))
    assert any("PODER ESTATÍSTICO LIMITADO" in m for m in msgs)


def test_nao_avisa_poder_quando_ha_amostras_suficientes(tmp_path):
    p = tmp_path / "r.csv"
    gravar(p, [linha(f"c{i}", "vulneravel", "VP")
               for i in range(MINIMO_VULNERAVEIS + 5)])
    assert not any("PODER" in m for m in avisos(carregar(str(p))))


def test_conta_vulneraveis_avaliadas(rodada):
    braco = next(b for b in carregar(str(rodada)) if b.modelo == GEMINI)
    assert vulneraveis_avaliadas(braco.linhas) == 2   # c4 (VP) e c5 (FN)


def test_avisa_divergencia_de_hash_de_catalogo(tmp_path):
    d = tmp_path / "run"
    d.mkdir()
    gravar(d / "a__especialista.csv", [linha("c1", "seguro", "FP", modelo="a",
                                             hash_cat="hashA")])
    gravar(d / "b__especialista.csv", [linha("c1", "seguro", "FP", modelo="b",
                                             hash_cat="hashB")])
    msgs = avisos(carregar(str(d)))
    assert any("DIVERGÊNCIA DE CATÁLOGO" in m for m in msgs)


def test_nao_avisa_divergencia_com_hash_unico(rodada):
    assert not any("DIVERGÊNCIA" in m for m in avisos(carregar(str(rodada))))


# --- 8.6 Export LaTeX -------------------------------------------------------

def test_exporta_os_dois_tex(rodada):
    bracos = carregar(str(rodada))
    comparacoes = [mcnemar(bracos[0], bracos[1])]
    caminhos = exportar_latex(bracos, comparacoes, str(rodada))
    assert [os.path.basename(c) for c in caminhos] == ["tabela_bracos.tex",
                                                       "tabela_mcnemar.tex"]
    for c in caminhos:
        texto = open(c, encoding="utf-8").read()
        assert texto.count("\\begin{tabular}") == 1
        assert texto.count("\\end{tabular}") == 1
        # Underscore de nome de modelo/braço tem que estar escapado, senão o
        # LaTeX quebra em modo texto.
        assert "_" not in texto.replace("\\_", "")


def test_tex_tem_uma_linha_por_braco(rodada):
    bracos = carregar(str(rodada))
    exportar_latex(bracos, [], str(rodada))
    texto = open(rodada / "tabela_bracos.tex", encoding="utf-8").read()
    corpo = texto.split("\\hline")[2]
    assert corpo.count("\\\\") == 2


def test_numeros_nao_viram_nan_no_tex(tmp_path):
    p = tmp_path / "r.csv"
    gravar(p, [linha("c1", "seguro", "FP")])
    exportar_latex(carregar(str(p)), [], str(tmp_path))
    texto = open(tmp_path / "tabela_bracos.tex", encoding="utf-8").read()
    assert "nan" not in texto.lower()
    assert "N/A" in texto     # métricas indefinidas saem como N/A explícito


def test_relatorio_completo_roda_sem_erro(rodada, capsys):
    from src.metricas import relatorio
    relatorio(str(rodada), por_cwe=True, com_mcnemar=True, com_estratos=True,
              latex=True)
    saida = capsys.readouterr().out
    assert "Comparação entre braços" in saida
    assert "McNemar" in saida
    assert "Estratificação" in saida
    assert "Cobertura do Semgrep" in saida
    assert not math.isnan(0)   # sanidade
