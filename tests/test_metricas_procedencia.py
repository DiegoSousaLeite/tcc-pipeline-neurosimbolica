"""Métricas por procedência do candidato e grupo de controle do braço de triagem.

Os números destes testes são conferidos à mão no corpo de cada um: uma métrica
que só é validada contra a própria implementação não valida nada.
"""
import csv
import math

import pytest

from src.fase5_auditoria import (
    CABECALHO,
    classificar_acerto_llm,
    classificar_cobertura_semgrep,
)
from src.metricas import (
    MINIMO_CONTROLE,
    avisos,
    carregar,
    comparar_procedencias,
    contar,
    estratificar,
    exportar_latex,
)

GEMINI = "gemini-2.5-flash-lite"


def linha(id_, gabarito, veredito, procedencia, status="DETECTADO",
          modelo=GEMINI, prompt="especialista"):
    """Linha de CSV do braço de TRIAGEM.

    Difere da fixture de `test_metricas.py` num ponto: aqui um caso
    `NAO_DETECTADO` PODE ter classificação de acerto do LLM preenchida — é
    exatamente o caso injetado, que recebe veredito sem que o status simbólico
    mude.
    """
    detectado = status == "DETECTADO"
    return {
        "ID_Caso": id_, "Repositorio": "acme/servico", "CWE": "CWE-327",
        "Origem": "TP_ouro" if gabarito == "vulneravel" else "FP",
        "Modelo_LLM": modelo, "Tipo_Prompt": prompt,
        "Gabarito": gabarito, "Status_Semgrep": status,
        "Classificacao_Semgrep": classificar_cobertura_semgrep(gabarito,
                                                               detectado),
        "Veredito_LLM": veredito,
        "Classificacao_LLM": classificar_acerto_llm(gabarito, veredito),
        "Tempo_Execucao_s": "1.00", "Justificativa": "j",
        "Num_Locations": "1", "Ficha_CWE": "especifica",
        "Versao_Prompt": f"{prompt}:abcd1234", "Hash_Catalogo": "h1",
        "Tokens_Entrada": "1000", "Tokens_Saida": "50", "Custo_USD": "0.0001",
        "Motivo_Nao_Deteccao": "SEM_ALERTA" if not detectado else "N/A",
        "Regras_Nao_Casadas": "", "Procedencia": procedencia,
    }


def gravar(caminho, linhas):
    with open(caminho, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CABECALHO, extrasaction="ignore")
        w.writeheader()
        for ln in linhas:
            w.writerow(ln)


def _linhas_triagem():
    """Rodada de triagem conferível à mão.

    Procedência `alerta`  (o Semgrep detectou):  3 VP, 1 FN, 4 VN, 1 FP
    Procedência `gabarito` (injetados):          2 VP, 2 FN
    Conjunto completo:                           5 VP, 3 FN, 4 VN, 1 FP
    """
    linhas = []
    for i in range(3):
        linhas.append(linha(f"a-vp{i}", "vulneravel", "VP", "alerta"))
    linhas.append(linha("a-fn0", "vulneravel", "FP", "alerta"))
    for i in range(4):
        linhas.append(linha(f"a-vn{i}", "seguro", "FP", "alerta"))
    linhas.append(linha("a-fp0", "seguro", "VP", "alerta"))
    for i in range(2):
        linhas.append(linha(f"g-vp{i}", "vulneravel", "VP", "gabarito",
                            status="NAO_DETECTADO"))
    for i in range(2):
        linhas.append(linha(f"g-fn{i}", "vulneravel", "FP", "gabarito",
                            status="NAO_DETECTADO"))
    return linhas


@pytest.fixture
def rodada_triagem(tmp_path):
    d = tmp_path / "run"
    d.mkdir()
    gravar(d / f"{GEMINI}__especialista.csv", _linhas_triagem())
    return str(d)


# --- 2.3 Métricas do conjunto completo e por procedência --------------------

def test_conjunto_completo_bate_com_o_calculo_manual(rodada_triagem):
    (braco,) = carregar(rodada_triagem)
    m = contar(braco.linhas, "llm")
    assert (m["VP"], m["VN"], m["FP"], m["FN"]) == (5, 4, 1, 3)
    assert m["Total"] == 13
    assert m["Precisao"] == pytest.approx(5 / 6)
    assert m["Recall"] == pytest.approx(5 / 8)
    assert m["TFN"] == pytest.approx(3 / 8)
    assert m["TRA"] == pytest.approx(7 / 13)


def test_metricas_do_grupo_alerta_batem_com_o_calculo_manual(rodada_triagem):
    (braco,) = carregar(rodada_triagem)
    m = estratificar(braco.linhas, "procedencia")["alerta"]
    assert (m["VP"], m["VN"], m["FP"], m["FN"]) == (3, 4, 1, 1)
    assert m["Total"] == 9
    assert m["Precisao"] == pytest.approx(3 / 4)
    assert m["Recall"] == pytest.approx(3 / 4)


def test_metricas_do_grupo_gabarito_batem_com_o_calculo_manual(rodada_triagem):
    (braco,) = carregar(rodada_triagem)
    m = estratificar(braco.linhas, "procedencia")["gabarito"]
    assert (m["VP"], m["VN"], m["FP"], m["FN"]) == (2, 0, 0, 2)
    assert m["Total"] == 4
    assert m["Recall"] == pytest.approx(0.5)
    # Sem negativos no grupo injetado, a especificidade não existe.
    assert math.isnan(m["PropFPFiltrados"])


def test_as_duas_procedencias_somam_o_conjunto_completo(rodada_triagem):
    (braco,) = carregar(rodada_triagem)
    por_proc = estratificar(braco.linhas, "procedencia")
    completo = contar(braco.linhas, "llm")
    for cel in ("VP", "VN", "FP", "FN", "Total"):
        assert por_proc["alerta"][cel] + por_proc["gabarito"][cel] == completo[cel]


def test_csv_sem_a_coluna_de_procedencia_nao_derruba_a_leitura(tmp_path):
    """Os CSVs das Rodadas 1-3 não têm a coluna; são todos do braço de filtro."""
    d = tmp_path / "antigo"
    d.mkdir()
    antigo = [ln for ln in _linhas_triagem() if ln["Procedencia"] == "alerta"]
    caminho = d / f"{GEMINI}__especialista.csv"
    with open(caminho, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CABECALHO[:-1], extrasaction="ignore")
        w.writeheader()
        for ln in antigo:
            w.writerow(ln)
    (braco,) = carregar(str(d))
    assert set(estratificar(braco.linhas, "procedencia")) == {"indisponível"}


# --- 5.1 A comparação entre procedências é reportada -----------------------

def test_comparacao_so_conta_vulneraveis(rodada_triagem):
    """Os negativos nunca são injetados; incluí-los inflaria o controle."""
    (braco,) = carregar(rodada_triagem)
    comp = comparar_procedencias(braco.linhas)
    assert comp["alerta"]["n"] == 4      # 3 VP + 1 FN, e não os 9 do braço
    assert comp["gabarito"]["n"] == 4


def test_comparacao_traz_o_acerto_lado_a_lado(rodada_triagem):
    (braco,) = carregar(rodada_triagem)
    comp = comparar_procedencias(braco.linhas)
    assert comp["alerta"]["acerto"] == pytest.approx(0.75)
    assert comp["gabarito"]["acerto"] == pytest.approx(0.50)


def test_comparacao_aparece_na_saida(rodada_triagem, capsys):
    from src.metricas import relatorio
    relatorio(rodada_triagem)
    saida = capsys.readouterr().out
    assert "Grupo de controle" in saida
    assert "gabarito" in saida


def test_comparacao_vai_para_o_arquivo_de_metricas(rodada_triagem):
    bracos = carregar(rodada_triagem)
    caminhos = exportar_latex(bracos, [], rodada_triagem)
    (tex,) = [c for c in caminhos if c.endswith("tabela_procedencias.tex")]
    with open(tex, encoding="utf-8") as f:
        conteudo = f.read()
    assert "alerta" in conteudo and "gabarito" in conteudo


def test_rodada_de_filtro_nao_emite_a_comparacao(tmp_path, capsys):
    """Uma procedência só não é comparação nenhuma."""
    from src.metricas import relatorio
    d = tmp_path / "filtro"
    d.mkdir()
    gravar(d / f"{GEMINI}__especialista.csv",
           [ln for ln in _linhas_triagem() if ln["Procedencia"] == "alerta"])
    relatorio(str(d))
    assert "Grupo de controle" not in capsys.readouterr().out


# --- 5.2 Controle pequeno é declarado como tal -----------------------------

def _braco_com_controle(tmp_path, n_alerta):
    d = tmp_path / f"run{n_alerta}"
    d.mkdir()
    linhas = [linha(f"a{i}", "vulneravel", "VP", "alerta")
              for i in range(n_alerta)]
    linhas += [linha(f"g{i}", "vulneravel", "VP", "gabarito",
                     status="NAO_DETECTADO") for i in range(40)]
    gravar(d / f"{GEMINI}__especialista.csv", linhas)
    return carregar(str(d))


def test_controle_de_19_casos_emite_o_aviso(tmp_path):
    """19 é o número real da Rodada 3: os positivos que o Semgrep achou."""
    bracos = _braco_com_controle(tmp_path, 19)
    texto = " ".join(avisos(bracos))
    assert "CONTROLE PEQUENO" in texto
    assert "19" in texto
    assert str(MINIMO_CONTROLE) in texto


def test_rodada_de_triagem_avisa_que_a_tra_agregada_engana(tmp_path):
    """A TRA da tabela de braços divide pelos casos avaliados. Numa rodada de
    triagem isso inclui injetados, que nunca foram alerta — o número muda por
    composição e não por comportamento, e citá-lo seria erro."""
    bracos = _braco_com_controle(tmp_path, 19)
    texto = " ".join(avisos(bracos))
    assert "TRA CONTAMINADA POR COMPOSIÇÃO" in texto
    assert "procedência" in texto


def test_rodada_de_filtro_nao_avisa_sobre_tra(tmp_path):
    d = tmp_path / "filtro"
    d.mkdir()
    gravar(d / f"{GEMINI}__especialista.csv",
           [linha(f"a{i}", "vulneravel", "VP", "alerta") for i in range(5)])
    assert not any("TRA CONTAMINADA" in a for a in avisos(carregar(str(d))))


def test_controle_grande_nao_emite_o_aviso(tmp_path):
    bracos = _braco_com_controle(tmp_path, MINIMO_CONTROLE)
    assert not any("CONTROLE PEQUENO" in a for a in avisos(bracos))


def test_rodada_de_filtro_nao_emite_aviso_de_controle(tmp_path):
    """Sem grupo injetado não há injeção a controlar."""
    d = tmp_path / "filtro"
    d.mkdir()
    gravar(d / f"{GEMINI}__especialista.csv",
           [linha(f"a{i}", "vulneravel", "VP", "alerta") for i in range(5)])
    bracos = carregar(str(d))
    assert not any("CONTROLE PEQUENO" in a for a in avisos(bracos))
