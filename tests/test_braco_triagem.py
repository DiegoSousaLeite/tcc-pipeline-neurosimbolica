"""Testes do braço de triagem: procedência, injeção e normalização.

A normalização é a guarda de integridade da change: se o candidato injetado
chegasse ao prompt com forma distinguível, o experimento mediria a pista e não o
julgamento — e nada no CSV denunciaria. Por isso os testes de `4.` comparam as
STRINGS DE PROMPT, e não só as estruturas.
"""
import csv
import json
import os

import pytest

import run_pipeline
from run_pipeline import (
    Braco,
    Caso,
    ResultadoSimbolico,
    executar_matriz,
    gravar_manifesto,
    montar_candidatura,
)
from src.catalogo import Catalogo
from src.fase1_semgrep import ALERTA_OUTRA_CWE, SEM_ALERTA
from src.fase2_middleware import (
    ALERTA,
    GABARITO,
    MODO_FILTRO,
    MODO_TRIAGEM,
    PROCEDENCIA_NA,
    ProcedenciaVazada,
    candidato_de_alerta,
    candidato_de_gabarito,
    extrair_e_hidratar_contexto,
)
from src.fase5_auditoria import CABECALHO
from src.prompts import TIPOS, montar_prompt
from src.provedores import RespostaLLM

GEMINI = "gemini-2.5-flash-lite"
BRACOS = [Braco(GEMINI, "baseline"), Braco(GEMINI, "especialista")]

# Duas funções, para que o recorte possa cair na certa ou na errada: é essa
# diferença que a linha do gabarito existe para acertar.
FONTE_GO = """package main

import "fmt"

func inofensiva(x int) int {
\tif x > 0 {
\t\treturn x * 2
\t}
\treturn 0
}

func vulneravel(nome string) {
\tfmt.Println("segredo: " + nome)
}
"""

LINHA_FUNC_VULNERAVEL = 12       # `func vulneravel(...)` em FONTE_GO
LINHA_ALERTA = 13                # corpo da mesma função


@pytest.fixture
def arquivo_go(tmp_path):
    destino = tmp_path / "handler.go"
    destino.write_text(FONTE_GO, encoding="utf-8")
    return str(destino)


def alerta(linha=LINHA_ALERTA, check_id="go.lang.security.audit.log-segredo"):
    return {"start": {"line": linha}, "check_id": check_id,
            "extra": {"message": "Possível vazamento de segredo em log."}}


def caso(id_="c1", cwe="CWE-532", gabarito="vulneravel", origem="TP_ouro",
         linha_gabarito=LINHA_FUNC_VULNERAVEL):
    return Caso(id=id_, origem=origem, repo_name="acme/servico",
                repo_dir="servico", repo_url="https://github.com/acme/servico",
                commit="a" * 40, arquivo="pkg/handler.go", cwe=cwe,
                cwe_name=f"Nome de {cwe}", description="desc",
                gabarito=gabarito, linha_gabarito=linha_gabarito)


class ProvedorFalso:
    def __init__(self, modelo, veredito="VP"):
        self.modelo = modelo
        self.veredito = veredito
        self.prompts = []

    def avaliar(self, prompt):
        self.prompts.append(prompt)
        return RespostaLLM(veredito=self.veredito, justificativa="j",
                           modelo=self.modelo, tokens_entrada=10,
                           tokens_saida=5, custo_usd=0.0)


@pytest.fixture
def catalogo():
    return Catalogo.carregar()


@pytest.fixture
def esteira(monkeypatch, arquivo_go):
    """Fases 1-2 dubladas e `obter_arquivo` apontando para o .go do tmp_path."""
    estado = {"status": "NAO_DETECTADO", "alerta": None, "motivo": SEM_ALERTA,
              "regras": [], "excecao": None}

    def _resolver(caso_, cache=None):
        if estado["excecao"]:
            raise estado["excecao"]
        contexto = ("" if estado["alerta"] is None
                    else extrair_e_hidratar_contexto(estado["alerta"],
                                                     arquivo_go))
        return ResultadoSimbolico(estado["status"], estado["alerta"], contexto,
                                  estado["motivo"], estado["regras"])

    monkeypatch.setattr(run_pipeline, "resolver_simbolico", _resolver)
    monkeypatch.setattr(run_pipeline, "obter_arquivo",
                        lambda *a, **k: arquivo_go)
    return estado


def _rodar(casos, tmp_path, catalogo, bracos=None, **kw):
    bracos = bracos or BRACOS
    dir_rodada = tmp_path / "rodada"
    dir_rodada.mkdir(parents=True, exist_ok=True)
    provedores = {m: ProvedorFalso(m) for m in {b.modelo for b in bracos}}
    original = run_pipeline.criar_provedor
    run_pipeline.criar_provedor = lambda modelo: provedores[modelo]
    try:
        executar_matriz(casos, bracos, str(dir_rodada), catalogo=catalogo, **kw)
    finally:
        run_pipeline.criar_provedor = original
    return str(dir_rodada), provedores


def _ler(dir_rodada, braco):
    caminho = os.path.join(dir_rodada, f"{braco.rotulo}.csv")
    with open(caminho, encoding="utf-8") as f:
        return list(csv.DictReader(f))


# --- 2.1 Procedência na estrutura do candidato ------------------------------

def test_candidato_de_alerta_sai_com_procedencia_alerta():
    assert candidato_de_alerta(alerta()).procedencia == ALERTA


def test_candidato_de_gabarito_sai_com_procedencia_gabarito():
    assert candidato_de_gabarito(LINHA_FUNC_VULNERAVEL).procedencia == GABARITO


def test_sem_linha_nao_ha_candidato_de_gabarito():
    """Inventar uma localização seria fabricar evidência (D6)."""
    assert candidato_de_gabarito(None) is None
    assert candidato_de_gabarito(0) is None


# --- 2.2 Procedência no CSV -------------------------------------------------

def test_coluna_de_procedencia_existe_e_vai_para_o_fim():
    assert CABECALHO[-1] == "Procedencia"


def test_caso_detectado_no_modo_filtro_sai_com_procedencia_alerta(
        tmp_path, catalogo, esteira):
    esteira.update(status="DETECTADO", alerta=alerta())
    dir_rodada, _ = _rodar([caso()], tmp_path, catalogo)
    for braco in BRACOS:
        (linha,) = _ler(dir_rodada, braco)
        assert linha["Procedencia"] == ALERTA


def test_nao_deteccao_no_modo_filtro_sai_sem_procedencia(
        tmp_path, catalogo, esteira):
    dir_rodada, _ = _rodar([caso()], tmp_path, catalogo)
    for braco in BRACOS:
        (linha,) = _ler(dir_rodada, braco)
        assert linha["Procedencia"] == PROCEDENCIA_NA


def test_sem_llm_preserva_a_procedencia_do_alerta(tmp_path, catalogo, esteira):
    """A procedência descreve como o CANDIDATO foi montado, e isso aconteceu
    mesmo quando o LLM não é consultado."""
    esteira.update(status="DETECTADO", alerta=alerta())
    dir_rodada, provedores = _rodar([caso()], tmp_path, catalogo, sem_llm=True)
    for braco in BRACOS:
        (linha,) = _ler(dir_rodada, braco)
        assert linha["Procedencia"] == ALERTA
        assert linha["Veredito_LLM"] == "N/A"


# --- 3.1 O eixo de montagem -------------------------------------------------

def test_invocacao_padrao_nao_monta_candidato_de_gabarito(esteira):
    """Sem selecionar o modo, o LLM continua filtro puro do Semgrep."""
    candidatura = montar_candidatura(caso(), ResultadoSimbolico(
        "NAO_DETECTADO", None, "", SEM_ALERTA, []))
    assert candidatura.candidato is None
    assert candidatura.procedencia == PROCEDENCIA_NA


def test_modo_de_montagem_consta_do_manifesto(tmp_path, catalogo):
    destino = gravar_manifesto(
        str(tmp_path), "run-1", BRACOS, {"TP_ouro": 1}, 1,
        __import__("datetime").datetime.now(__import__("datetime").timezone.utc),
        __import__("datetime").datetime.now(__import__("datetime").timezone.utc),
        catalogo, False, True, "cmd", None, modo=MODO_TRIAGEM)
    with open(destino, encoding="utf-8") as f:
        manifesto = json.load(f)
    assert manifesto["modo"]["montagem"] == MODO_TRIAGEM


def test_manifesto_registra_filtro_por_padrao(tmp_path, catalogo):
    import datetime as dt
    agora = dt.datetime.now(dt.timezone.utc)
    destino = gravar_manifesto(str(tmp_path), "run-2", BRACOS, {"FP": 1}, 1,
                               agora, agora, catalogo, False, True, "cmd", None)
    with open(destino, encoding="utf-8") as f:
        assert json.load(f)["modo"]["montagem"] == MODO_FILTRO


def test_modo_da_rodada_le_o_manifesto(tmp_path, catalogo):
    """A guarda contra retomar uma rodada com o modo trocado."""
    import datetime as dt

    from run_pipeline import modo_da_rodada
    agora = dt.datetime.now(dt.timezone.utc)
    assert modo_da_rodada(str(tmp_path)) is None          # rodada nova
    gravar_manifesto(str(tmp_path), "r", BRACOS, {"TP_ouro": 1}, 1, agora,
                     agora, catalogo, False, True, "cmd", None,
                     modo=MODO_TRIAGEM)
    assert modo_da_rodada(str(tmp_path)) == MODO_TRIAGEM


def test_manifesto_sem_o_campo_conta_como_filtro(tmp_path):
    """Manifesto anterior a esta change é, por construção, de rodada de filtro."""
    from run_pipeline import modo_da_rodada
    (tmp_path / "manifesto.json").write_text(
        json.dumps({"modo": {"sem_llm": False}}), encoding="utf-8")
    assert modo_da_rodada(str(tmp_path)) == MODO_FILTRO


# --- 3.2 Injeção do positivo não detectado ----------------------------------

def test_vulneravel_nao_detectado_produz_candidato_na_triagem(esteira):
    simbolico = ResultadoSimbolico("NAO_DETECTADO", None, "", SEM_ALERTA, [])
    candidatura = montar_candidatura(caso(), simbolico, MODO_TRIAGEM)
    assert candidatura.procedencia == GABARITO
    assert candidatura.contexto


def test_o_mesmo_caso_nao_produz_candidato_no_filtro(esteira):
    simbolico = ResultadoSimbolico("NAO_DETECTADO", None, "", SEM_ALERTA, [])
    assert montar_candidatura(caso(), simbolico, MODO_FILTRO).candidato is None


def test_injetado_chega_ao_llm_e_recebe_veredito(tmp_path, catalogo, esteira):
    dir_rodada, provedores = _rodar([caso()], tmp_path, catalogo,
                                    modo=MODO_TRIAGEM)
    assert len(provedores[GEMINI].prompts) == len(BRACOS)
    for braco in BRACOS:
        (linha,) = _ler(dir_rodada, braco)
        assert linha["Veredito_LLM"] == "VP"
        assert linha["Procedencia"] == GABARITO


def test_recorte_do_injetado_cai_na_funcao_do_gabarito(arquivo_go):
    """Sem a linha do gabarito o recorte cairia na PRIMEIRA função do arquivo."""
    contexto = extrair_e_hidratar_contexto(
        candidato_de_gabarito(LINHA_FUNC_VULNERAVEL), arquivo_go,
        modo=MODO_TRIAGEM)
    assert "func vulneravel" in contexto
    assert "func inofensiva" not in contexto


# --- 3.3 O status simbólico não é sobrescrito -------------------------------

def test_injetado_sai_do_csv_como_nao_detectado(tmp_path, catalogo, esteira):
    esteira.update(motivo=ALERTA_OUTRA_CWE, regras=["regra.a", "regra.b"])
    dir_rodada, _ = _rodar([caso()], tmp_path, catalogo, modo=MODO_TRIAGEM)
    for braco in BRACOS:
        (linha,) = _ler(dir_rodada, braco)
        assert linha["Status_Semgrep"] == "NAO_DETECTADO"
        assert linha["Motivo_Nao_Deteccao"] == ALERTA_OUTRA_CWE
        assert linha["Regras_Nao_Casadas"] == "regra.a;regra.b"
        # A cobertura simbólica continua contando o caso como ponto cego.
        assert "Semgrep FN" in linha["Classificacao_Semgrep"]
        # E o acerto do LLM é medido do mesmo jeito que em qualquer outro caso.
        assert linha["Classificacao_LLM"] == "Verdadeiro Positivo (Acerto)"


# --- 3.4 O que nunca é injetado ---------------------------------------------

def test_negativo_nunca_e_injetado(esteira):
    """O negativo existe porque o Semgrep o emitiu; injetá-lo não faria sentido."""
    simbolico = ResultadoSimbolico("NAO_DETECTADO", None, "", SEM_ALERTA, [])
    seguro = caso(gabarito="seguro", origem="FP",
                  linha_gabarito=LINHA_FUNC_VULNERAVEL)
    assert montar_candidatura(seguro, simbolico, MODO_TRIAGEM).candidato is None


def test_falha_de_esteira_nunca_vira_candidato(esteira):
    """Sem garantia de que o arquivo-alvo foi resolvido, não há o que julgar."""
    simbolico = ResultadoSimbolico("FETCH_FAIL", None, "", SEM_ALERTA, [])
    assert montar_candidatura(caso(), simbolico, MODO_TRIAGEM).candidato is None


def test_falha_de_esteira_na_rodada_nao_produz_chamada(tmp_path, catalogo,
                                                       esteira):
    from src.fonte import FetchError
    esteira["excecao"] = FetchError("sem rede")
    dir_rodada, provedores = _rodar([caso()], tmp_path, catalogo,
                                    modo=MODO_TRIAGEM)
    assert provedores[GEMINI].prompts == []
    for braco in BRACOS:
        (linha,) = _ler(dir_rodada, braco)
        assert linha["Status_Semgrep"] == "FETCH_FAIL"
        assert linha["Procedencia"] == PROCEDENCIA_NA


# --- 3.5 Precedência do emparelhamento sobre a injeção ----------------------

def test_detectado_na_triagem_vem_do_alerta(tmp_path, catalogo, esteira):
    """São estes 19 casos que formam o grupo de controle; injetar por cima
    deles destruiria o único controle disponível (D3)."""
    esteira.update(status="DETECTADO", alerta=alerta())
    dir_rodada, _ = _rodar([caso()], tmp_path, catalogo, modo=MODO_TRIAGEM)
    for braco in BRACOS:
        (linha,) = _ler(dir_rodada, braco)
        assert linha["Procedencia"] == ALERTA
        assert linha["Status_Semgrep"] == "DETECTADO"


def test_nenhum_candidato_de_gabarito_para_caso_detectado(esteira):
    simbolico = ResultadoSimbolico("DETECTADO", alerta(), "ctx")
    candidatura = montar_candidatura(caso(), simbolico, MODO_TRIAGEM)
    assert candidatura.candidato.procedencia == ALERTA
    assert candidatura.candidato.linha == LINHA_ALERTA


# --- 4.1 Mesma estrutura ----------------------------------------------------

def test_as_duas_procedencias_tem_o_mesmo_conjunto_de_chaves():
    de_alerta = candidato_de_alerta(alerta()).campos()
    de_gabarito = candidato_de_gabarito(LINHA_FUNC_VULNERAVEL).campos()
    assert set(de_alerta) == set(de_gabarito)


def test_campos_ausentes_sao_preenchidos_e_nao_omitidos():
    campos = candidato_de_gabarito(LINHA_FUNC_VULNERAVEL).campos()
    assert campos["check_id"] and campos["mensagem"]


# --- 4.2 Os prompts são indistinguíveis -------------------------------------

def _prompt_de(candidato, arquivo_go, tipo):
    contexto = extrair_e_hidratar_contexto(candidato, arquivo_go,
                                           modo=MODO_TRIAGEM)
    return montar_prompt(tipo, contexto=contexto, cwe_id="CWE-532",
                         cwe_name="Nome de CWE-532", description="desc")


@pytest.mark.parametrize("tipo", TIPOS)
def test_prompt_nao_revela_a_procedencia(arquivo_go, tipo):
    """Mesmo arquivo, mesma CWE, mesma função: os dois prompts são iguais.

    Se alguma coisa da montagem vazar — identificador de regra, mensagem do
    motor, a linha exata apontada — este teste falha, e é para falhar.
    """
    do_alerta = _prompt_de(candidato_de_alerta(alerta()), arquivo_go, tipo)
    do_gabarito = _prompt_de(candidato_de_gabarito(LINHA_FUNC_VULNERAVEL),
                             arquivo_go, tipo)
    assert do_alerta == do_gabarito


@pytest.mark.parametrize("tipo", TIPOS)
def test_prompt_de_triagem_nao_carrega_campos_do_motor(arquivo_go, tipo):
    """Nem por caminho indireto: nome de regra, mensagem ou linha apontada."""
    prompt = _prompt_de(candidato_de_alerta(alerta()), arquivo_go, tipo)
    assert "go.lang.security.audit" not in prompt
    assert "Alerta Semgrep" not in prompt
    assert "vazamento de segredo" not in prompt
    assert f"Localização: linha {LINHA_ALERTA}" not in prompt


def test_modo_filtro_recusa_candidato_de_gabarito(arquivo_go):
    """A guarda que torna o vazamento impossível por construção, não por
    disciplina: no modo filtro o cabeçalho do alerta denunciaria a procedência."""
    with pytest.raises(ProcedenciaVazada):
        extrair_e_hidratar_contexto(
            candidato_de_gabarito(LINHA_FUNC_VULNERAVEL), arquivo_go,
            modo=MODO_FILTRO)


def test_modo_filtro_continua_byte_a_byte_o_de_antes(arquivo_go):
    """O braço de filtro não muda: é o que mantém as Rodadas 1-3 reproduzíveis."""
    contexto = extrair_e_hidratar_contexto(alerta(), arquivo_go)
    assert contexto.startswith(
        "Alerta Semgrep: go.lang.security.audit.log-segredo\n"
        "Mensagem: Possível vazamento de segredo em log.\n"
        f"Localização: linha {LINHA_ALERTA}\n"
        "\n--- CÓDIGO FONTE RELEVANTE ---\n"
        "\n[Arquivo: handler.go | ")


# --- 5.2 O controle pequeno é declarado como tal ----------------------------

def test_a_procedencia_nao_entra_no_contexto_de_triagem(arquivo_go):
    for candidato in (candidato_de_alerta(alerta()),
                      candidato_de_gabarito(LINHA_FUNC_VULNERAVEL)):
        contexto = extrair_e_hidratar_contexto(candidato, arquivo_go,
                                               modo=MODO_TRIAGEM)
        assert ALERTA not in contexto and GABARITO not in contexto
