"""Testes do runner da matriz 2x2 e da auditoria (tarefas 7.1 a 7.4)."""
import argparse
import csv
import json
import os

import pytest

import run_pipeline
from run_pipeline import (
    BRACO_PARTE1,
    Braco,
    Caso,
    carregar_processados,
    executar_matriz,
    gravar_manifesto,
    novo_run_id,
)
from src.catalogo import Catalogo
from src.fase5_auditoria import CABECALHO, COLUNAS_PARTE2, inicializar_relatorio
from src.provedores import RespostaLLM

GEMINI = "gemini-2.5-flash-lite"
GPT = "gpt-4o-mini"
MATRIZ = [Braco(GEMINI, "baseline"), Braco(GEMINI, "especialista"),
          Braco(GPT, "baseline"), Braco(GPT, "especialista")]

CONTEXTO = "Alerta Semgrep: regra-x\nMensagem: m\nLocalização: linha 1\ncode"


def caso(id_, cwe="CWE-327", gabarito="seguro", origem="FP", num_locations=1):
    return Caso(id=id_, origem=origem, repo_name="acme/servico",
                repo_dir="servico", repo_url="https://github.com/acme/servico",
                commit="a" * 40, arquivo=f"pkg/{id_}.go", cwe=cwe,
                cwe_name=f"Nome de {cwe}", description="desc",
                gabarito=gabarito, num_locations=num_locations)


class ProvedorFalso:
    """Devolve sempre o mesmo veredito e registra os prompts recebidos."""

    def __init__(self, modelo, veredito="FP"):
        self.modelo = modelo
        self.veredito = veredito
        self.prompts = []

    def avaliar(self, prompt):
        self.prompts.append(prompt)
        return RespostaLLM(veredito=self.veredito, justificativa="justificativa",
                           modelo=self.modelo, tokens_entrada=1000,
                           tokens_saida=50, custo_usd=0.000125)


@pytest.fixture
def simbolico_dublado(monkeypatch):
    """Fase 1/2 dubladas; `detectado` controla o que o Semgrep 'viu'."""
    estado = {"detectado": True, "chamadas": 0, "excecao": None}

    def _resolver(caso_, cache=None):
        estado["chamadas"] += 1
        if estado["excecao"]:
            raise estado["excecao"]
        if not estado["detectado"]:
            return "NAO_DETECTADO", None, ""
        return "DETECTADO", {"start": {"line": 1}}, CONTEXTO

    monkeypatch.setattr(run_pipeline, "resolver_simbolico", _resolver)
    return estado


@pytest.fixture
def catalogo():
    return Catalogo.carregar()


def _rodar(casos, bracos, tmp_path, catalogo, provedores=None, **kw):
    dir_rodada = tmp_path / "rodada"
    dir_rodada.mkdir(parents=True, exist_ok=True)
    provedores = provedores or {m: ProvedorFalso(m) for m in {b.modelo for b in bracos}}
    # `criar_provedor` é substituído para o teste nunca tocar a rede.
    original = run_pipeline.criar_provedor
    run_pipeline.criar_provedor = lambda modelo: provedores[modelo]
    try:
        chamadas = executar_matriz(casos, bracos, str(dir_rodada),
                                   catalogo=catalogo, **kw)
    finally:
        run_pipeline.criar_provedor = original
    return str(dir_rodada), provedores, chamadas


def _ler(dir_rodada, braco):
    with open(os.path.join(dir_rodada, f"{braco.rotulo}.csv"), encoding="utf-8") as f:
        return list(csv.DictReader(f))


# --- 7.1 Cabeçalho do CSV ---------------------------------------------------

def test_cabecalho_tem_as_colunas_novas():
    for col in ("Num_Locations", "Ficha_CWE", "Versao_Prompt", "Hash_Catalogo",
                "Tokens_Entrada", "Tokens_Saida", "Custo_USD"):
        assert col in CABECALHO
    assert CABECALHO[0] == "ID_Caso"   # checkpoint depende disso
    assert set(COLUNAS_PARTE2) == {
        "Num_Locations", "Ficha_CWE", "Versao_Prompt", "Hash_Catalogo",
        "Tokens_Entrada", "Tokens_Saida", "Custo_USD"}


def test_colunas_novas_preenchidas_em_caso_detectado(tmp_path, catalogo,
                                                     simbolico_dublado):
    braco = Braco(GEMINI, "especialista")
    dir_rodada, _, _ = _rodar([caso("c1", num_locations=7)], [braco],
                              tmp_path, catalogo)
    linha = _ler(dir_rodada, braco)[0]
    assert linha["Num_Locations"] == "7"
    assert linha["Ficha_CWE"] == "especifica"
    assert linha["Versao_Prompt"].startswith("especialista:")
    assert linha["Hash_Catalogo"] == catalogo.sha256
    assert linha["Tokens_Entrada"] == "1000"
    assert linha["Tokens_Saida"] == "50"
    assert float(linha["Custo_USD"]) > 0


def test_ficha_fallback_e_registrada(tmp_path, catalogo, simbolico_dublado):
    braco = Braco(GEMINI, "especialista")
    dir_rodada, _, _ = _rodar([caso("c1", cwe="CWE-99999")], [braco],
                              tmp_path, catalogo)
    assert _ler(dir_rodada, braco)[0]["Ficha_CWE"] == "fallback"


def test_num_locations_preenchido_mesmo_sem_deteccao(tmp_path, catalogo,
                                                     simbolico_dublado):
    simbolico_dublado["detectado"] = False
    braco = Braco(GEMINI, "especialista")
    dir_rodada, _, _ = _rodar([caso("c1", num_locations=11)], [braco],
                              tmp_path, catalogo)
    linha = _ler(dir_rodada, braco)[0]
    assert linha["Num_Locations"] == "11"
    assert linha["Status_Semgrep"] == "NAO_DETECTADO"
    assert linha["Custo_USD"] == "0.00000000"


# --- 7.2 Checkpoint por chave composta -------------------------------------

def _gravar_csv(caminho, linhas, cabecalho=None):
    """Grava linhas de CSV; `DETECTADO` sem veredito explícito recebe `FP`.

    Um DETECTADO sem veredito significa 'o Semgrep disparou e ninguém triou'
    (é o que `--sem-llm` produz), e não conta como processado. Os testes que
    querem uma linha concluída precisam do veredito.
    """
    with open(caminho, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cabecalho or CABECALHO)
        w.writeheader()
        for linha in linhas:
            if linha.get("Status_Semgrep") == "DETECTADO":
                linha = {"Veredito_LLM": "FP", **linha}
            w.writerow(linha)


def test_checkpoint_indexa_pela_tripla(tmp_path):
    arq = tmp_path / "r.csv"
    _gravar_csv(arq, [
        {"ID_Caso": "c1", "Modelo_LLM": GEMINI, "Tipo_Prompt": "especialista",
         "Status_Semgrep": "DETECTADO"},
    ])
    p = carregar_processados([str(arq)])
    assert ("c1", GEMINI, "especialista") in p
    assert ("c1", GEMINI, "baseline") not in p
    assert ("c1", GPT, "especialista") not in p


def test_braco_novo_nao_e_pulado(tmp_path, catalogo, simbolico_dublado):
    """Sem a chave composta, o segundo braço sairia vazio — falha silenciosa."""
    arq = tmp_path / "antigo.csv"
    _gravar_csv(arq, [{"ID_Caso": "c1", "Modelo_LLM": GEMINI,
                       "Tipo_Prompt": "especialista",
                       "Status_Semgrep": "DETECTADO"}])
    processados = carregar_processados([str(arq)])

    novo = Braco(GPT, "baseline")
    pendentes = [b for b in MATRIZ
                 if ("c1", b.modelo, b.prompt) not in processados]
    assert novo in pendentes
    assert Braco(GEMINI, "especialista") not in pendentes
    assert len(pendentes) == 3


def test_csv_antigo_sem_colunas_novas_vira_braco_da_parte1(tmp_path):
    """Linhas da Parte 1 são atribuídas a (gemini-2.5-flash-lite, especialista)."""
    cabecalho_antigo = CABECALHO[:13]
    arq = tmp_path / "parte1.csv"
    _gravar_csv(arq, [{"ID_Caso": "c1", "Modelo_LLM": "", "Tipo_Prompt": "",
                       "Status_Semgrep": "DETECTADO"}],
                cabecalho=cabecalho_antigo)
    assert ("c1", *BRACO_PARTE1) in carregar_processados([str(arq)])


def test_csvs_antigo_e_novo_misturados(tmp_path):
    antigo = tmp_path / "parte1.csv"
    _gravar_csv(antigo, [{"ID_Caso": "velho", "Modelo_LLM": GEMINI,
                          "Tipo_Prompt": "especialista",
                          "Status_Semgrep": "NAO_DETECTADO"}],
                cabecalho=CABECALHO[:13])
    novo = tmp_path / "parte2.csv"
    _gravar_csv(novo, [{"ID_Caso": "novo", "Modelo_LLM": GPT,
                        "Tipo_Prompt": "baseline", "Status_Semgrep": "DETECTADO",
                        "Num_Locations": "3", "Custo_USD": "0.0001"}])
    p = carregar_processados([str(antigo), str(novo)])
    assert p == {("velho", GEMINI, "especialista"), ("novo", GPT, "baseline")}


def test_medicao_sem_llm_nao_bloqueia_o_braco_real(tmp_path):
    """`--sem-llm` grava DETECTADO com veredito N/A: o Semgrep disparou, mas
    ninguém triou. Contar isso como processado impediria para sempre de rodar
    o LLM sobre o conjunto medido."""
    arq = tmp_path / "cobertura.csv"
    _gravar_csv(arq, [
        {"ID_Caso": "det", "Modelo_LLM": GEMINI, "Tipo_Prompt": "especialista",
         "Status_Semgrep": "DETECTADO", "Veredito_LLM": "N/A"},
        {"ID_Caso": "nao", "Modelo_LLM": GEMINI, "Tipo_Prompt": "especialista",
         "Status_Semgrep": "NAO_DETECTADO", "Veredito_LLM": "N/A"},
    ])
    p = carregar_processados([str(arq)])
    # O NAO_DETECTADO está resolvido: o LLM nem devia ser consultado.
    assert ("nao", GEMINI, "especialista") in p
    # O DETECTADO sem veredito ainda precisa ser triado.
    assert ("det", GEMINI, "especialista") not in p


def test_detectado_com_veredito_valido_e_checkpointado(tmp_path):
    arq = tmp_path / "r.csv"
    _gravar_csv(arq, [
        {"ID_Caso": "vp", "Modelo_LLM": GEMINI, "Tipo_Prompt": "baseline",
         "Status_Semgrep": "DETECTADO", "Veredito_LLM": "VP"},
        {"ID_Caso": "fp", "Modelo_LLM": GEMINI, "Tipo_Prompt": "baseline",
         "Status_Semgrep": "DETECTADO", "Veredito_LLM": "FP"},
        {"ID_Caso": "err", "Modelo_LLM": GEMINI, "Tipo_Prompt": "baseline",
         "Status_Semgrep": "DETECTADO", "Veredito_LLM": "ERROR"},
    ])
    p = carregar_processados([str(arq)])
    assert ("vp", GEMINI, "baseline") in p
    assert ("fp", GEMINI, "baseline") in p
    assert ("err", GEMINI, "baseline") not in p


def test_erros_nao_sao_checkpointados(tmp_path):
    arq = tmp_path / "r.csv"
    _gravar_csv(arq, [
        {"ID_Caso": "erro", "Modelo_LLM": GEMINI, "Tipo_Prompt": "baseline",
         "Status_Semgrep": "API_ERROR"},
        {"ID_Caso": "fetch", "Modelo_LLM": GEMINI, "Tipo_Prompt": "baseline",
         "Status_Semgrep": "FETCH_FAIL"},
        {"ID_Caso": "ok", "Modelo_LLM": GEMINI, "Tipo_Prompt": "baseline",
         "Status_Semgrep": "DETECTADO"},
    ])
    p = carregar_processados([str(arq)])
    assert p == {("ok", GEMINI, "baseline")}


def test_csv_ilegivel_nao_derruba_o_checkpoint(tmp_path):
    assert carregar_processados([str(tmp_path / "nao-existe.csv")]) == set()


def test_checkpoint_padrao_ve_so_a_rodada_corrente(tmp_path, monkeypatch):
    """Uma rodada nova começa do zero. Se as linhas da Parte 1 contassem, o
    braço (gemini, especialista) viria com menos casos que os outros três e o
    McNemar pareado perderia a base."""
    rodada = tmp_path / "results" / "run-atual"
    rodada.mkdir(parents=True)
    _gravar_csv(rodada / f"{GEMINI}__baseline.csv",
                [{"ID_Caso": "corrente", "Modelo_LLM": GEMINI,
                  "Tipo_Prompt": "baseline", "Status_Semgrep": "NAO_DETECTADO"}])
    legado = tmp_path / "legacy" / "resultados_parte1"
    legado.mkdir(parents=True)
    _gravar_csv(legado / "resultados_tcc.csv",
                [{"ID_Caso": "antigo", "Modelo_LLM": GEMINI,
                  "Tipo_Prompt": "especialista",
                  "Status_Semgrep": "NAO_DETECTADO"}])

    monkeypatch.setattr(run_pipeline, "BASE", str(tmp_path))
    monkeypatch.setattr(run_pipeline, "RESULTS_DIR", str(tmp_path / "results"))
    monkeypatch.setattr(run_pipeline, "LEGADO_PARTE1", str(legado))

    so_corrente = carregar_processados(None, str(rodada), False)
    assert so_corrente == {("corrente", GEMINI, "baseline")}

    com_anteriores = carregar_processados(None, str(rodada), True)
    assert ("antigo", GEMINI, "especialista") in com_anteriores
    assert ("corrente", GEMINI, "baseline") in com_anteriores


# --- 7.3 Laço da matriz -----------------------------------------------------

def test_quatro_bracos_cobrem_o_mesmo_conjunto_de_ids(tmp_path, catalogo,
                                                      simbolico_dublado):
    casos = [caso("c1"), caso("c2", gabarito="vulneravel"), caso("c3")]
    dir_rodada, _, chamadas = _rodar(casos, MATRIZ, tmp_path, catalogo)

    ids_por_braco = {b: {linha["ID_Caso"] for linha in _ler(dir_rodada, b)}
                     for b in MATRIZ}
    assert all(ids == {"c1", "c2", "c3"} for ids in ids_por_braco.values())
    assert chamadas == 12          # 3 casos x 4 braços


def test_fases_1_e_2_rodam_uma_vez_por_caso(tmp_path, catalogo,
                                            simbolico_dublado):
    """O ganho de tempo da matriz depende disto, e a validade interna também:
    um contexto por caso, não um por braço."""
    _rodar([caso("c1"), caso("c2")], MATRIZ, tmp_path, catalogo)
    assert simbolico_dublado["chamadas"] == 2


def test_contexto_identico_em_todos_os_bracos(tmp_path, catalogo,
                                              simbolico_dublado):
    _, provedores, _ = _rodar([caso("c1")], MATRIZ, tmp_path, catalogo)
    for prov in provedores.values():
        for prompt in prov.prompts:
            assert CONTEXTO in prompt


def test_nao_detectado_nunca_chama_llm_em_braco_algum(tmp_path, catalogo,
                                                      simbolico_dublado):
    """O LLM é filtro puro do Semgrep: sem alerta, não há o que triar."""
    simbolico_dublado["detectado"] = False
    dir_rodada, provedores, chamadas = _rodar([caso("c1"), caso("c2")],
                                              MATRIZ, tmp_path, catalogo)
    assert chamadas == 0
    assert all(not p.prompts for p in provedores.values())
    for b in MATRIZ:
        linhas = _ler(dir_rodada, b)
        assert len(linhas) == 2
        assert all(x["Status_Semgrep"] == "NAO_DETECTADO" for x in linhas)
        assert all(x["Veredito_LLM"] == "N/A" for x in linhas)


def test_sem_llm_nao_chama_llm(tmp_path, catalogo, simbolico_dublado):
    dir_rodada, provedores, chamadas = _rodar(
        [caso("c1")], MATRIZ, tmp_path, catalogo, sem_llm=True)
    assert chamadas == 0
    for b in MATRIZ:
        linha = _ler(dir_rodada, b)[0]
        assert linha["Status_Semgrep"] == "DETECTADO"
        assert linha["Veredito_LLM"] == "N/A"


def test_selecao_de_braco_unico_nao_afeta_os_demais(tmp_path, catalogo,
                                                    simbolico_dublado):
    unico = Braco(GPT, "baseline")
    dir_rodada, _, _ = _rodar([caso("c1")], [unico], tmp_path, catalogo)
    assert os.listdir(dir_rodada) == [f"{unico.rotulo}.csv"]


def test_falha_de_esteira_registrada_em_todos_os_bracos(tmp_path, catalogo,
                                                        simbolico_dublado):
    from src.fonte import FetchError
    simbolico_dublado["excecao"] = FetchError("sem rede")
    dir_rodada, _, chamadas = _rodar([caso("c1")], MATRIZ, tmp_path, catalogo)
    assert chamadas == 0
    for b in MATRIZ:
        linha = _ler(dir_rodada, b)[0]
        assert linha["Status_Semgrep"] == "FETCH_FAIL"
        assert linha["Classificacao_LLM"] == "N/A (Falha de Esteira)"


def test_prompts_diferem_entre_os_bracos_de_prompt(tmp_path, catalogo,
                                                   simbolico_dublado):
    prov = ProvedorFalso(GEMINI)
    _rodar([caso("c1")], [Braco(GEMINI, "baseline"), Braco(GEMINI, "especialista")],
           tmp_path, catalogo, provedores={GEMINI: prov})
    baseline, especialista = prov.prompts
    assert baseline != especialista
    assert "CAMADA" in especialista and "CAMADA" not in baseline
    assert len(especialista) > len(baseline)


def test_um_provedor_por_modelo(tmp_path, catalogo, simbolico_dublado):
    """Os dois braços de prompt do mesmo modelo compartilham o provedor: o
    intervalo mínimo entre chamadas é por provedor, e instanciar de novo
    zeraria o throttle."""
    prov = ProvedorFalso(GEMINI)
    _rodar([caso("c1")], [Braco(GEMINI, "baseline"), Braco(GEMINI, "especialista")],
           tmp_path, catalogo, provedores={GEMINI: prov})
    assert len(prov.prompts) == 2


# --- 7.4 run_id e manifesto -------------------------------------------------

def test_run_id_ordenavel_e_rastreavel():
    rid = novo_run_id()
    assert rid[8] == "T" and "Z-" in rid
    assert len(rid.split("-")) >= 2


def test_manifesto_completo(tmp_path, catalogo):
    from datetime import datetime, timezone
    dir_rodada = tmp_path / "rodada"
    dir_rodada.mkdir()
    inicio = datetime.now(timezone.utc)
    destino = gravar_manifesto(
        str(dir_rodada), "20260729T120000Z-abc1234", MATRIZ,
        {"FP": 791, "TP_dataset": 57}, 848, inicio,
        datetime.now(timezone.utc), catalogo, False, True,
        "run_pipeline.py --tudo --matriz")

    m = json.load(open(destino, encoding="utf-8"))
    assert m["run_id"] == "20260729T120000Z-abc1234"
    assert m["commit"]
    assert m["semgrep"]["versao"] and m["semgrep"]["ruleset"]
    assert m["catalogo_cwe"]["sha256"] == catalogo.sha256
    assert len(m["catalogo_cwe"]["cwes_especificas"]) == 15
    assert set(m["prompts"]) == {"baseline", "especialista"}
    assert len(m["bracos"]) == 4
    assert m["precos"]["data_consulta"]
    assert GEMINI in m["precos"]["precos"]
    assert m["populacao"]["total"] == 848
    assert m["populacao"]["por_trilha"]["FP"] == 791
    assert m["inicio_utc"] and m["fim_utc"] and m["duracao_s"] >= 0
    assert m["modo"] == {"sem_llm": False, "cache_simbolico_ativo": True}


def test_rodadas_nao_se_sobrescrevem(tmp_path, catalogo, simbolico_dublado):
    d1, _, _ = _rodar([caso("c1")], [Braco(GEMINI, "baseline")],
                      tmp_path / "a", catalogo)
    d2, _, _ = _rodar([caso("c1")], [Braco(GEMINI, "baseline")],
                      tmp_path / "b", catalogo)
    assert d1 != d2
    assert os.path.exists(os.path.join(d1, f"{GEMINI}__baseline.csv"))
    assert os.path.exists(os.path.join(d2, f"{GEMINI}__baseline.csv"))


def test_retomar_a_rodada_apenda_em_vez_de_apagar(tmp_path, catalogo,
                                                  simbolico_dublado):
    """`--run-id` de uma rodada em andamento não pode truncar o CSV já gravado."""
    braco = Braco(GEMINI, "baseline")
    dir_rodada = tmp_path / "rodada"
    dir_rodada.mkdir(parents=True)

    prov = {GEMINI: ProvedorFalso(GEMINI)}
    original = run_pipeline.criar_provedor
    run_pipeline.criar_provedor = lambda modelo: prov[modelo]
    try:
        executar_matriz([caso("c1")], [braco], str(dir_rodada), catalogo=catalogo)
        executar_matriz([caso("c2")], [braco], str(dir_rodada), catalogo=catalogo)
    finally:
        run_pipeline.criar_provedor = original

    linhas = _ler(str(dir_rodada), braco)
    assert [x["ID_Caso"] for x in linhas] == ["c1", "c2"]


def test_nenhum_csv_novo_na_raiz_do_repositorio(tmp_path, catalogo,
                                                simbolico_dublado):
    antes = set(os.listdir(run_pipeline.BASE))
    _rodar([caso("c1")], MATRIZ, tmp_path, catalogo)
    novos = set(os.listdir(run_pipeline.BASE)) - antes
    assert not [n for n in novos if n.endswith(".csv")]


# --- Rótulo de braço saneado e sondagem do braço local ---------------------

OLLAMA = "ollama:qwen2.5-coder:7b"


def _args(modelo, prompt="baseline", matriz=False):
    return argparse.Namespace(matriz=matriz, modelo=modelo, prompt=[prompt])


def test_rotulo_ja_valido_fica_identico():
    """Renomear os CSVs dos braços comerciais quebraria a retomada de rodada e
    a leitura do que já foi gravado."""
    assert Braco(GEMINI, "especialista").rotulo == f"{GEMINI}__especialista"
    assert Braco(GPT, "baseline").rotulo == f"{GPT}__baseline"


def test_rotulo_de_modelo_local_e_saneado():
    """Dois-pontos é caractere reservado no Windows: sem isto a rodada morre ao
    abrir o CSV, antes do primeiro caso."""
    assert Braco(OLLAMA, "baseline").rotulo == "ollama-qwen2.5-coder-7b__baseline"
    assert ":" not in Braco(OLLAMA, "especialista").rotulo


def test_modelo_cru_continua_nos_dados(tmp_path, catalogo, simbolico_dublado):
    braco = Braco(OLLAMA, "baseline")
    dir_rodada, _, _ = _rodar([caso("c1")], [braco], tmp_path, catalogo)
    assert os.listdir(dir_rodada) == ["ollama-qwen2.5-coder-7b__baseline.csv"]
    assert _ler(dir_rodada, braco)[0]["Modelo_LLM"] == OLLAMA


def test_colisao_de_rotulo_e_desambiguada(tmp_path, catalogo, simbolico_dublado):
    """Sobrescrever silenciosamente o CSV de um braço com o de outro seria falha
    de integridade dos dados, não inconveniência de nomenclatura."""
    gemeos = ["ollama:qwen2.5-coder:7b", "ollama:qwen2.5-coder/7b"]
    bracos = run_pipeline.definir_bracos(_args(gemeos))
    assert len({b.rotulo for b in bracos}) == 2

    dir_rodada, _, _ = _rodar([caso("c1")], bracos, tmp_path, catalogo)
    assert len(os.listdir(dir_rodada)) == 2


def test_sem_colisao_nao_ha_sufixo():
    bracos = run_pipeline.definir_bracos(_args([GEMINI, GPT]))
    assert all(b.sufixo == "" for b in bracos)
    assert {b.rotulo for b in bracos} == {f"{GEMINI}__baseline", f"{GPT}__baseline"}


def test_rodada_so_comercial_nao_sonda(monkeypatch):
    """A pipeline sem braço local continua rodando em máquina sem Ollama."""
    def _explode(modelo):
        raise AssertionError(f"não deveria instanciar provedor: {modelo}")

    monkeypatch.setattr(run_pipeline, "criar_provedor", _explode)
    assert run_pipeline.sondar_modelos_locais(MATRIZ) == {}
    assert run_pipeline.modelos_locais(MATRIZ) == []


def test_sondagem_roda_uma_vez_por_modelo_local(monkeypatch):
    sondados = []

    class ProvedorLocalFalso:
        def __init__(self, modelo):
            self.modelo = modelo

        def sondar(self):
            sondados.append(self.modelo)
            return {"tag": "qwen2.5-coder:7b", "digest": "abc"}

    monkeypatch.setattr(run_pipeline, "criar_provedor", ProvedorLocalFalso)
    bracos = [Braco(OLLAMA, "baseline"), Braco(OLLAMA, "especialista"),
              Braco(GEMINI, "baseline")]
    assert set(run_pipeline.sondar_modelos_locais(bracos)) == {OLLAMA}
    assert sondados == [OLLAMA]


def test_manifesto_registra_a_identidade_do_modelo_local(tmp_path, catalogo):
    from datetime import datetime, timezone
    dir_rodada = tmp_path / "rodada"
    dir_rodada.mkdir()
    agora = datetime.now(timezone.utc)
    sondagem = {OLLAMA: {"tag": "qwen2.5-coder:7b", "versao_ollama": "0.32.5",
                         "digest": "dae161e27b0e", "quantizacao": "Q4_K_M",
                         "parametros": "7.6B", "janela_maxima_declarada": 32768,
                         "num_ctx": 8192, "num_predict": 512, "semente": 42,
                         "processador": "100% GPU"}}
    destino = gravar_manifesto(
        str(dir_rodada), "20260730T120000Z-abc1234",
        [Braco(OLLAMA, "baseline"), Braco(GEMINI, "baseline")],
        {"FP": 791}, 791, agora, agora, catalogo, False, True,
        "run_pipeline.py --tudo --modelo " + OLLAMA, sondagem)

    m = json.load(open(destino, encoding="utf-8"))
    local = m["modelos_locais"][OLLAMA]
    assert local["digest"] == "dae161e27b0e"
    assert local["quantizacao"] == "Q4_K_M"
    assert local["num_ctx"] == 8192
    assert local["semente"] == 42
    assert local["processador"] == "100% GPU"
    # Custo zero por execução local, e não "esqueceram de tabelar o preço".
    assert m["precos"]["modelos_locais_sem_custo"] == [OLLAMA]
    assert m["precos"]["modelos_sem_preco"] == []
    assert m["bracos"][0]["csv"] == "ollama-qwen2.5-coder-7b__baseline.csv"
    assert m["bracos"][0]["modelo"] == OLLAMA


def test_manifesto_sem_braco_local_tem_bloco_vazio(tmp_path, catalogo):
    from datetime import datetime, timezone
    dir_rodada = tmp_path / "rodada"
    dir_rodada.mkdir()
    agora = datetime.now(timezone.utc)
    destino = gravar_manifesto(str(dir_rodada), "r", MATRIZ, {"FP": 1}, 1,
                               agora, agora, catalogo, False, True, "cmd")
    m = json.load(open(destino, encoding="utf-8"))
    assert m["modelos_locais"] == {}
    assert m["precos"]["modelos_locais_sem_custo"] == []


def test_inicializar_relatorio_grava_o_cabecalho(tmp_path):
    p = tmp_path / "x.csv"
    inicializar_relatorio(str(p))
    with open(p, encoding="utf-8") as f:
        assert next(csv.reader(f)) == CABECALHO
