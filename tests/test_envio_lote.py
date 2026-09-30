"""Testes do modo de envio em lote (change `envio-em-lote-comercial`).

Nenhum teste toca a rede. O fornecedor é dublado por `ServidorFalso`, que guarda
os lotes submetidos entre "execuções" — é o que permite simular uma queda entre
a submissão e a recuperação sem gastar nada.
"""
import csv
import json
import os
import random
import sys

import pytest

import run_pipeline
from run_pipeline import (
    MODO_LOTE,
    MODO_SINCRONO,
    Braco,
    ResultadoSimbolico,
    carregar_processados,
    executar_matriz,
    gravar_manifesto,
    modo_envio_da_rodada,
    rodadas_com_lote_em_aberto,
)
from src.catalogo import Catalogo
from src.envio_lote import NOME_ARQUIVO, RegistroLote
from src.fase1_semgrep import SEM_ALERTA
from src.fase5_auditoria import STATUS_LOTE_EXPIRADO, registrar_resultado
from src.provedores import (
    ERROR,
    EXPIRADO,
    FP,
    MODELO_OLLAMA_PADRAO,
    VP,
    LoteNaoSuportado,
    ProvedorGemini,
    ProvedorGeminiLote,
    RespostaLLM,
    criar_provedor_lote,
)
from src.provedores.gemini_lote import (
    TOKENS_ENFILEIRADOS_TIER1,
    limites_do_modelo,
    normalizar_estado,
    respostas_inline,
)
from src.provedores.lote import (
    CONCLUIDO,
    LOTE_EXPIRADO,
    NAO_ENCONTRADO,
    PENDENTE,
    ErroLote,
    LimitesLote,
    chave_lote,
    correlacionar,
    ler_chave,
    particionar,
)
from tests.test_matriz import CONTEXTO, ProvedorFalso, caso
from tests.test_provedores import JSON_FP, JSON_VP, SessaoFalsa, resposta_gemini

GEMINI = "gemini-2.5-flash-lite"
BRACOS = [Braco(GEMINI, "baseline"), Braco(GEMINI, "especialista")]
RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RODADA_4 = os.path.join(RAIZ, "results", "rodada-4-triagem")


@pytest.fixture
def catalogo():
    return Catalogo.carregar()


@pytest.fixture
def simbolico_dublado(monkeypatch):
    """Fases 1-2 dubladas, como em `test_matriz`: `detectado` decide o status."""
    estado = {"detectado": True, "chamadas": 0}

    def _resolver(caso_, cache=None):
        estado["chamadas"] += 1
        if not estado["detectado"]:
            return ResultadoSimbolico("NAO_DETECTADO", None, "", SEM_ALERTA, [])
        return ResultadoSimbolico("DETECTADO", {"start": {"line": 1}}, CONTEXTO)

    monkeypatch.setattr(run_pipeline, "resolver_simbolico", _resolver)
    return estado


# ---------------------------------------------------------------------------
# Dublê do fornecedor
# ---------------------------------------------------------------------------

class ServidorFalso:
    """O lado do fornecedor: sobrevive entre 'execuções' do runner."""

    def __init__(self):
        self.lotes = {}

    def novo(self, rotulo, prompts):
        id_lote = f"batches/falso-{len(self.lotes)}"
        self.lotes[id_lote] = {"rotulo": rotulo, "prompts": dict(prompts),
                               "consultas": 0}
        return id_lote


class ProvedorLoteFalso:
    """`ProvedorLote` dublado. Responde por caso, e devolve fora de ordem."""

    nome = "gemini"
    desconto = 0.5
    cobra_expirada = False

    def __init__(self, modelo, servidor, vereditos=None, limites=None,
                 estado_final=CONCLUIDO, orfas=(), consultas_ate_fim=2,
                 ao_submeter=None, ao_consultar=None, semente=7):
        self.modelo = modelo
        self.servidor = servidor
        self.vereditos = vereditos or {}
        self.limites = limites or LimitesLote(tokens_enfileirados=10**9,
                                              bytes_por_lote=10**9)
        self.estado_final = estado_final
        self.orfas = list(orfas)
        self.consultas_ate_fim = consultas_ate_fim
        self.ao_submeter = ao_submeter
        self.ao_consultar = ao_consultar
        self.aleatorio = random.Random(semente)
        self.submissoes = []

    def medir(self, chave, prompt):
        return len(prompt) // 3 + 1, len(prompt) + len(chave) + 60

    def submeter(self, prompts, rotulo):
        if self.ao_submeter:
            self.ao_submeter(rotulo)
        id_lote = self.servidor.novo(rotulo, prompts)
        self.submissoes.append(id_lote)
        return id_lote

    def estado(self, id_lote):
        lote = self.servidor.lotes.get(id_lote)
        if lote is None:
            return NAO_ENCONTRADO
        lote["consultas"] += 1
        if self.ao_consultar:
            self.ao_consultar(lote)
        return (self.estado_final if lote["consultas"] >= self.consultas_ate_fim
                else PENDENTE)

    def localizar(self, rotulo):
        for id_lote, lote in self.servidor.lotes.items():
            if lote["rotulo"] == rotulo:
                return id_lote
        return None

    def recuperar(self, id_lote):
        lote = self.servidor.lotes[id_lote]
        if self.estado_final == LOTE_EXPIRADO:
            return {}
        chaves = list(lote["prompts"]) + self.orfas
        self.aleatorio.shuffle(chaves)          # a ordem NÃO é a da submissão
        saida = {}
        for chave in chaves:
            caso_id = ler_chave(chave)[0]
            v = self.vereditos.get(caso_id, FP)
            saida[chave] = RespostaLLM(
                veredito=v, justificativa=f"sobre {caso_id}", modelo=self.modelo,
                tokens_entrada=1000, tokens_saida=50, custo_usd=0.00012)
        return saida


def _rodar_lote(casos, bracos, dir_rodada, catalogo, provedores, **kw):
    os.makedirs(dir_rodada, exist_ok=True)
    original = run_pipeline.criar_provedor_lote
    run_pipeline.criar_provedor_lote = lambda modelo: provedores[modelo]
    try:
        return executar_matriz(casos, bracos, str(dir_rodada), catalogo=catalogo,
                               modo_envio=MODO_LOTE, run_id="rodada-teste",
                               dormir=lambda s: None, **kw)
    finally:
        run_pipeline.criar_provedor_lote = original


def _linhas(dir_rodada, braco):
    with open(os.path.join(dir_rodada, f"{braco.rotulo}.csv"),
              encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _registro(dir_rodada):
    return RegistroLote.carregar(os.path.join(dir_rodada, NOME_ARQUIVO))


# ---------------------------------------------------------------------------
# 1.1 A chave de correlação
# ---------------------------------------------------------------------------

def test_chave_e_a_tripla_do_checkpoint_e_volta_intacta():
    chave = chave_lote("TPA:prest:CWE-89:ReturningByRequest:159caf80:vuln",
                       GEMINI, "especialista")
    assert chave == ("TPA:prest:CWE-89:ReturningByRequest:159caf80:vuln"
                     "|gemini-2.5-flash-lite|especialista")
    assert len(chave) == 84
    assert ler_chave(chave) == ("TPA:prest:CWE-89:ReturningByRequest:159caf80:vuln",
                                GEMINI, "especialista")


def test_chave_recusa_componente_com_separador_ou_vazio():
    with pytest.raises(ValueError):
        chave_lote("a|b", GEMINI, "baseline")
    with pytest.raises(ValueError):
        chave_lote("", GEMINI, "baseline")
    with pytest.raises(ValueError):
        ler_chave("só-duas|partes")


# ---------------------------------------------------------------------------
# 1.2 Limites declarados pelo provedor e partição demonstrada
# ---------------------------------------------------------------------------

def test_limites_vem_do_provedor_por_modelo(monkeypatch):
    monkeypatch.delenv("GEMINI_LOTE_TOKENS_ENFILEIRADOS", raising=False)
    assert limites_do_modelo("gemini-2.5-flash-lite").tokens_enfileirados == 10_000_000
    assert limites_do_modelo("gemini-2.5-flash").tokens_enfileirados == 3_000_000
    assert ProvedorGeminiLote(api_key="k").limites.tokens_enfileirados == \
        TOKENS_ENFILEIRADOS_TIER1[GEMINI]
    # O tier é da conta, não do código.
    monkeypatch.setenv("GEMINI_LOTE_TOKENS_ENFILEIRADOS", "400000000")
    assert limites_do_modelo(GEMINI).tokens_enfileirados == 400_000_000


def _requisicoes_rodada_4():
    """(chave, tokens de entrada) das chamadas faturáveis da Rodada 4.

    Os CSVs em disco são os da REEXECUÇÃO de 2026-09-24 (3.175 chamadas,
    3.195.553 tokens de entrada), não os da execução original que
    `docs/ESCOLHA-MODELO-COMERCIAL.md` recontou (3.172 / 3.199.085). Os testes
    afirmam a propriedade — mais que 3.000.000 e menos que 10.000.000 —, que
    vale para as duas.
    """
    if not os.path.isdir(RODADA_4):
        pytest.skip("results/rodada-4-triagem/ ausente (results/ não é versionado)")
    reqs = []
    for nome in sorted(os.listdir(RODADA_4)):
        if not nome.endswith(".csv"):
            continue
        with open(os.path.join(RODADA_4, nome), encoding="utf-8") as f:
            for r in csv.DictReader(f):
                t_in = int(r.get("Tokens_Entrada") or 0)
                t_out = int(r.get("Tokens_Saida") or 0)
                if t_in or t_out:
                    reqs.append((chave_lote(r["ID_Caso"], r["Modelo_LLM"],
                                            r["Tipo_Prompt"]), t_in))
    return reqs


def test_particao_da_rodada_4_demonstrada():
    """A rodada de dois braços (~3,2 M tokens): 1 lote no Flash-Lite, 2 no Flash.

    Os tokens são os MEDIDOS de cada chamada (e não a estimativa por
    caracteres), para que o cálculo seja o do documento de escolha de modelo.
    """
    reqs = _requisicoes_rodada_4()
    assert len(reqs) > 3000
    assert 3_000_000 < sum(t for _, t in reqs) < 10_000_000
    tokens = dict(reqs)

    def medir(chave, _):
        return tokens[chave], 100

    itens = [(k, "") for k, _ in reqs]
    lite = particionar(itens, LimitesLote(10_000_000, 10**12), medir)
    flash = particionar(itens, LimitesLote(3_000_000, 10**12), medir)
    assert len(lite) == 1
    assert len(flash) == 2
    for particoes, teto in ((lite, 10_000_000), (flash, 3_000_000)):
        assert all(sum(tokens[k] for k, _ in p) <= teto * 0.9 for p in particoes)
        assert [k for p in particoes for k, _ in p] == [k for k, _ in itens]


# ---------------------------------------------------------------------------
# 1.3 Formato do fornecedor, como fixture
# ---------------------------------------------------------------------------

# A resposta concluída como a referência REST a descreve (ver a docstring de
# `src/provedores/gemini_lote.py`), com uma requisição que falhou no fornecedor.
OPERACAO_CONCLUIDA = {
    "name": "batches/abc123",
    "done": True,
    "metadata": {"@type": "type.googleapis.com/google.ai.generativelanguage."
                          "v1main.GenerateContentBatch",
                 "displayName": "rodada-p0-deadbeef",
                 "state": "BATCH_STATE_SUCCEEDED"},
    "response": {"@type": "type.googleapis.com/google.ai.generativelanguage."
                          "v1main.GenerateContentBatchOutput",
                 "inlinedResponses": {"inlinedResponses": [
                     {"metadata": {"key": f"c2|{GEMINI}|baseline"},
                      "response": resposta_gemini(JSON_FP, 900, 40)._dados},
                     {"metadata": {"key": f"c1|{GEMINI}|baseline"},
                      "response": resposta_gemini(JSON_VP, 1200, 80)._dados},
                     {"metadata": {"key": f"c3|{GEMINI}|baseline"},
                      "error": {"code": 400, "message": "Invalid argument"}},
                 ]}},
}


def test_corpo_de_submissao_segue_o_formato_documentado():
    p = ProvedorGeminiLote(api_key="k")
    corpo = p.corpo_submissao({f"c1|{GEMINI}|baseline": "prompt 1"}, "rotulo-x")
    lote = corpo["batch"]
    assert lote["display_name"] == "rotulo-x"
    req = lote["input_config"]["requests"]["requests"][0]
    assert req["metadata"] == {"key": f"c1|{GEMINI}|baseline"}
    # O corpo da requisição é o MESMO do síncrono.
    assert req["request"] == ProvedorGemini(api_key="k")._payload("prompt 1")


def test_estado_aceita_os_dois_vocabularios_do_fornecedor():
    assert normalizar_estado({"metadata": {"state": "JOB_STATE_RUNNING"}}) == PENDENTE
    assert normalizar_estado({"metadata": {"state": "BATCH_STATE_SUCCEEDED"}}) == CONCLUIDO
    assert normalizar_estado({"metadata": {"state": "JOB_STATE_EXPIRED"}}) == LOTE_EXPIRADO
    assert normalizar_estado({"metadata": {"state": "BATCH_STATE_FAILED"}}) == "FALHOU"
    assert normalizar_estado({"done": True, "error": {"code": 1}}) == "CANCELADO"


def test_recuperar_le_a_resposta_documentada_por_chave():
    class Sessao:
        def get(self, url, headers=None, params=None, timeout=None):
            class R:
                status_code = 200
                headers = {}
                text = ""

                def json(self_):
                    return OPERACAO_CONCLUIDA
            return R()

    p = ProvedorGeminiLote(api_key="k", sessao=Sessao())
    r = p.recuperar("batches/abc123")
    assert r[f"c1|{GEMINI}|baseline"].veredito == VP
    assert r[f"c1|{GEMINI}|baseline"].tokens_entrada == 1200
    assert r[f"c2|{GEMINI}|baseline"].veredito == FP
    assert r[f"c3|{GEMINI}|baseline"].veredito == ERROR
    assert "Invalid argument" in r[f"c3|{GEMINI}|baseline"].justificativa


def test_resposta_em_arquivo_e_recusada_em_vez_de_lida_errado():
    with pytest.raises(ErroLote):
        respostas_inline({"response": {"responsesFile": "files/x"}})


# ---------------------------------------------------------------------------
# 2.1 O protocolo não tocou no síncrono
# ---------------------------------------------------------------------------

def test_provedor_de_lote_nao_herda_o_avaliar_sincrono():
    p = ProvedorGeminiLote(api_key="k")
    for metodo in ("medir", "submeter", "estado", "localizar", "recuperar"):
        assert callable(getattr(p, metodo))
    assert not hasattr(p, "avaliar")


def test_submeter_nao_repete_sozinho():
    """Uma submissão cujo retorno se perdeu pode ter criado o lote: repetir
    pagaria duas vezes. Quem resolve é a retomada, pelo rótulo."""
    class Sessao:
        chamadas = 0

        def post(self, *a, **k):
            Sessao.chamadas += 1
            import requests
            raise requests.ConnectionError("caiu")

    p = ProvedorGeminiLote(api_key="k", sessao=Sessao())
    with pytest.raises(Exception):
        p.submeter({f"c1|{GEMINI}|baseline": "x"}, "r")
    assert Sessao.chamadas == 1


# ---------------------------------------------------------------------------
# 2.2 EXPIRADO é desfecho próprio
# ---------------------------------------------------------------------------

def test_expirado_nao_vira_error_nem_fp_e_nao_soma_custo():
    chaves = [f"c1|{GEMINI}|baseline", f"c2|{GEMINI}|baseline"]
    respostas, orfas = correlacionar(chaves, {}, LOTE_EXPIRADO, GEMINI)
    assert orfas == []
    for r in respostas.values():
        assert r.veredito == EXPIRADO
        assert r.veredito not in (ERROR, FP)
        assert r.custo_usd == 0.0


def test_expirado_cobrado_pelo_fornecedor_nao_e_zerado_se_ele_cobra():
    k = f"c1|{GEMINI}|baseline"
    cobrada = RespostaLLM(veredito=EXPIRADO, justificativa="x", modelo=GEMINI,
                          custo_usd=0.5)
    zerada, _ = correlacionar([k], {k: cobrada}, CONCLUIDO, GEMINI,
                              cobra_expirada=False)
    mantida, _ = correlacionar([k], {k: cobrada}, CONCLUIDO, GEMINI,
                               cobra_expirada=True)
    assert zerada[k].custo_usd == 0.0
    assert mantida[k].custo_usd == 0.5


def test_ausente_de_lote_concluido_e_error_e_nao_expirado():
    k = f"c1|{GEMINI}|baseline"
    respostas, _ = correlacionar([k], {}, CONCLUIDO, GEMINI)
    assert respostas[k].veredito == ERROR


def test_csv_distingue_expirado_de_erro(tmp_path):
    p = str(tmp_path / "x.csv")
    run_pipeline.inicializar_relatorio(p)
    registrar_resultado(p, "c1", "r", "CWE-1", "FP", "seguro",
                        status_semgrep=STATUS_LOTE_EXPIRADO, tempo_exec=0.1,
                        resposta_llm={"verdict": EXPIRADO, "reasoning": "x"},
                        erro_msg="expirou")
    linha = list(csv.DictReader(open(p, encoding="utf-8")))[0]
    assert linha["Status_Semgrep"] == "LOTE_EXPIRADO"
    assert linha["Veredito_LLM"] == "EXPIRADO"
    assert "Erro de Inferência" not in linha["Classificacao_LLM"]
    # Não é checkpointado: a requisição não foi resolvida.
    assert carregar_processados([p]) == set()


def test_lote_expirado_grava_expirado_no_runner(tmp_path, catalogo,
                                                simbolico_dublado):
    servidor = ServidorFalso()
    prov = ProvedorLoteFalso(GEMINI, servidor, estado_final=LOTE_EXPIRADO)
    dir_rodada = tmp_path / "r"
    _rodar_lote([caso("c1"), caso("c2")], BRACOS, dir_rodada, catalogo,
                {GEMINI: prov})
    for braco in BRACOS:
        linhas = _linhas(dir_rodada, braco)
        assert [ln["Veredito_LLM"] for ln in linhas] == [EXPIRADO, EXPIRADO]
        assert {ln["Status_Semgrep"] for ln in linhas} == {"LOTE_EXPIRADO"}
        assert all(float(ln["Custo_USD"]) == 0 for ln in linhas)
    assert _registro(dir_rodada).particoes[0]["n_expirado"] == 4


# ---------------------------------------------------------------------------
# 2.3 Paridade de validação entre os modos
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("texto", [
    JSON_VP, JSON_FP,
    '{"verdict": "TALVEZ", "reasoning": "x"}',   # fora do domínio -> ERROR
    "isto não é JSON",
    '```json\n{"verdict": "vp", "reasoning": "cercado"}\n```',
])
def test_mesma_resposta_bruta_mesmo_resultado_nos_dois_modos(texto):
    bruta = resposta_gemini(texto, t_in=1234, t_out=56)

    sinc = ProvedorGemini(api_key="k", sessao=SessaoFalsa(bruta),
                          intervalo_minimo_s=0).avaliar("prompt")
    lote = ProvedorGeminiLote(api_key="k").converter(
        {"metadata": {"key": "x"}, "response": bruta._dados})

    assert lote == sinc                     # veredito, tokens, custo, tudo
    assert lote.custo_usd > 0


# ---------------------------------------------------------------------------
# 2.4 Recusa precoce do provedor sem lote
# ---------------------------------------------------------------------------

def test_ollama_sem_lote_e_recusado_nomeando_o_provedor():
    with pytest.raises(LoteNaoSuportado, match="ollama"):
        criar_provedor_lote(MODELO_OLLAMA_PADRAO)
    # Gemini e OpenAI têm lote.
    assert criar_provedor_lote(GEMINI, api_key="k").nome == "gemini"
    assert criar_provedor_lote("gpt-6-luna", api_key="k").nome == "openai"


def test_ollama_em_lote_falha_antes_da_fase_1_e_do_prompt(tmp_path, catalogo,
                                                          simbolico_dublado,
                                                          monkeypatch):
    def _explode(*a, **k):
        raise AssertionError("prompt montado antes da recusa")
    monkeypatch.setattr(run_pipeline, "montar", _explode)
    with pytest.raises(LoteNaoSuportado, match="ollama"):
        executar_matriz([caso("c1")], [Braco(MODELO_OLLAMA_PADRAO, "baseline")],
                        str(tmp_path), catalogo=catalogo, modo_envio=MODO_LOTE)
    assert simbolico_dublado["chamadas"] == 0


def test_cli_recusa_lote_para_ollama_antes_de_ler_o_dataset(monkeypatch, capsys):
    def _explode(*a, **k):
        raise AssertionError("dataset lido antes da recusa")
    monkeypatch.setattr(run_pipeline, "construir_casos_fp", _explode)
    monkeypatch.setattr(sys, "argv", ["run_pipeline.py", "--amostra", "1",
                                      "--modelo", MODELO_OLLAMA_PADRAO,
                                      "--modo-envio", "lote"])
    with pytest.raises(SystemExit) as e:
        run_pipeline.main()
    assert e.value.code == 2
    assert "ollama" in capsys.readouterr().err


# ---------------------------------------------------------------------------
# 3.1 / 3.2 Correlação
# ---------------------------------------------------------------------------

def test_respostas_fora_de_ordem_caem_na_linha_certa(tmp_path, catalogo,
                                                     simbolico_dublado):
    casos = [caso(f"c{i}") for i in range(12)]
    vereditos = {f"c{i}": (VP if i % 3 == 0 else FP) for i in range(12)}
    servidor = ServidorFalso()
    prov = ProvedorLoteFalso(GEMINI, servidor, vereditos=vereditos)
    dir_rodada = tmp_path / "r"
    _rodar_lote(casos, BRACOS, dir_rodada, catalogo, {GEMINI: prov})
    for braco in BRACOS:
        linhas = _linhas(dir_rodada, braco)
        assert len(linhas) == 12
        for ln in linhas:
            assert ln["Veredito_LLM"] == vereditos[ln["ID_Caso"]]
            assert ln["Justificativa"] == f"sobre {ln['ID_Caso']}"
        # A gravação segue a ordem da população, não a da resposta.
        assert [ln["ID_Caso"] for ln in linhas] == [c.id for c in casos]


def test_resposta_orfa_nao_e_gravada_e_vai_para_o_log(tmp_path, catalogo,
                                                      simbolico_dublado, caplog):
    orfa = f"intruso|{GEMINI}|baseline"
    prov = ProvedorLoteFalso(GEMINI, ServidorFalso(), orfas=[orfa])
    dir_rodada = tmp_path / "r"
    _rodar_lote([caso("c1")], BRACOS, dir_rodada, catalogo, {GEMINI: prov})
    for braco in BRACOS:
        assert [ln["ID_Caso"] for ln in _linhas(dir_rodada, braco)] == ["c1"]
    assert "ANOMALIA" in caplog.text and orfa in caplog.text
    assert _registro(dir_rodada).particoes[0]["n_orfas"] == 1


# ---------------------------------------------------------------------------
# 3.3 / 3.4 Persistência antes da submissão e retomada sem novo gasto
# ---------------------------------------------------------------------------

def test_registro_esta_em_disco_quando_a_submissao_parte(tmp_path, catalogo,
                                                         simbolico_dublado):
    dir_rodada = tmp_path / "r"
    vistos = []

    def _no_instante_da_submissao(rotulo):
        caminho = os.path.join(dir_rodada, NOME_ARQUIVO)
        assert os.path.exists(caminho), "lote.json ausente na submissão"
        part = json.load(open(caminho, encoding="utf-8"))["particoes"][0]
        assert part["rotulo"] == rotulo
        assert part["estado"] == "SUBMETENDO"
        assert len(part["chaves"]) == 2
        vistos.append(rotulo)

    prov = ProvedorLoteFalso(GEMINI, ServidorFalso(),
                             ao_submeter=_no_instante_da_submissao)
    _rodar_lote([caso("c1")], BRACOS, dir_rodada, catalogo, {GEMINI: prov})
    assert len(vistos) == 1
    part = _registro(dir_rodada).particoes[0]
    assert part["id_lote"] == "batches/falso-0" and part["estado"] == "RECUPERADA"


class Queda(BaseException):
    """Simula o processo morto (BaseException, como o KeyboardInterrupt)."""


def test_queda_entre_submissao_e_recuperacao_retoma_sem_ressubmeter(
        tmp_path, catalogo, simbolico_dublado):
    servidor = ServidorFalso()
    dir_rodada = tmp_path / "r"
    casos = [caso("c1"), caso("c2")]

    def _cair(lote):
        raise Queda()
    primeira = ProvedorLoteFalso(GEMINI, servidor, ao_consultar=_cair)
    with pytest.raises(Queda):
        _rodar_lote(casos, BRACOS, dir_rodada, catalogo, {GEMINI: primeira})
    assert len(servidor.lotes) == 1
    assert all(len(_linhas(dir_rodada, b)) == 0 for b in BRACOS)

    segunda = ProvedorLoteFalso(GEMINI, servidor, vereditos={"c1": VP})
    _rodar_lote(casos, BRACOS, dir_rodada, catalogo, {GEMINI: segunda})
    assert segunda.submissoes == []              # nada foi pago de novo
    assert len(servidor.lotes) == 1
    for braco in BRACOS:
        assert [(ln["ID_Caso"], ln["Veredito_LLM"])
                for ln in _linhas(dir_rodada, braco)] == [("c1", VP), ("c2", FP)]

    # Terceira execução: tudo gravado, nada a fazer.
    terceira = ProvedorLoteFalso(GEMINI, servidor)
    _rodar_lote(casos, BRACOS, dir_rodada, catalogo, {GEMINI: terceira})
    assert terceira.submissoes == []
    assert all(len(_linhas(dir_rodada, b)) == 2 for b in BRACOS)


def test_queda_com_lote_criado_e_identificador_perdido_localiza_pelo_rotulo(
        tmp_path, catalogo, simbolico_dublado):
    """A janela que gravar o rótulo ANTES cobre: o fornecedor criou o lote e o
    processo morreu antes de o identificador chegar ao disco."""
    servidor = ServidorFalso()
    dir_rodada = tmp_path / "r"

    class Cai(ProvedorLoteFalso):
        def submeter(self, prompts, rotulo):
            self.servidor.novo(rotulo, prompts)   # o lote EXISTE no fornecedor
            raise Queda()

    with pytest.raises(Queda):
        _rodar_lote([caso("c1")], BRACOS, dir_rodada, catalogo,
                    {GEMINI: Cai(GEMINI, servidor)})
    part = _registro(dir_rodada).particoes[0]
    assert part["estado"] == "SUBMETENDO" and part["id_lote"] is None

    retomada = ProvedorLoteFalso(GEMINI, servidor)
    _rodar_lote([caso("c1")], BRACOS, dir_rodada, catalogo, {GEMINI: retomada})
    assert retomada.submissoes == []
    assert len(servidor.lotes) == 1
    assert _registro(dir_rodada).particoes[0]["id_lote"] == "batches/falso-0"


def test_rotulo_sem_lote_no_fornecedor_e_submetido(tmp_path, catalogo,
                                                   simbolico_dublado):
    """O lado oposto da janela: o rótulo foi gravado e a submissão nunca saiu."""
    servidor = ServidorFalso()
    dir_rodada = tmp_path / "r"

    class CaiAntes(ProvedorLoteFalso):
        def submeter(self, prompts, rotulo):
            raise Queda()

    with pytest.raises(Queda):
        _rodar_lote([caso("c1")], BRACOS, dir_rodada, catalogo,
                    {GEMINI: CaiAntes(GEMINI, servidor)})
    retomada = ProvedorLoteFalso(GEMINI, servidor)
    _rodar_lote([caso("c1")], BRACOS, dir_rodada, catalogo, {GEMINI: retomada})
    assert len(retomada.submissoes) == 1


def test_expirados_nao_sao_reenviados_automaticamente(tmp_path, catalogo,
                                                      simbolico_dublado):
    servidor = ServidorFalso()
    dir_rodada = tmp_path / "r"
    _rodar_lote([caso("c1")], BRACOS, dir_rodada, catalogo,
                {GEMINI: ProvedorLoteFalso(GEMINI, servidor,
                                           estado_final=LOTE_EXPIRADO)})
    de_novo = ProvedorLoteFalso(GEMINI, servidor)
    _rodar_lote([caso("c1")], BRACOS, dir_rodada, catalogo, {GEMINI: de_novo})
    assert de_novo.submissoes == []
    # E nenhuma linha duplicada.
    assert all(len(_linhas(dir_rodada, b)) == 1 for b in BRACOS)


def test_lote_que_sumiu_do_fornecedor_para_sem_ressubmeter(tmp_path, catalogo,
                                                           simbolico_dublado):
    servidor = ServidorFalso()
    dir_rodada = tmp_path / "r"

    def _cair(lote):
        raise Queda()
    with pytest.raises(Queda):
        _rodar_lote([caso("c1")], BRACOS, dir_rodada, catalogo,
                    {GEMINI: ProvedorLoteFalso(GEMINI, servidor,
                                               ao_consultar=_cair)})
    servidor.lotes.clear()                       # retenção vencida
    prov = ProvedorLoteFalso(GEMINI, servidor)
    with pytest.raises(ErroLote, match="não existe"):
        _rodar_lote([caso("c1")], BRACOS, dir_rodada, catalogo, {GEMINI: prov})
    assert prov.submissoes == []


def test_rodada_com_lote_em_aberto_e_detectada(tmp_path):
    for run_id, estado in (("a", "RECUPERADA"), ("b", "SUBMETIDA")):
        d = tmp_path / run_id
        d.mkdir()
        (d / NOME_ARQUIVO).write_text(json.dumps(
            {"particoes": [{"estado": estado}]}), encoding="utf-8")
    assert rodadas_com_lote_em_aberto(str(tmp_path)) == ["b"]


# ---------------------------------------------------------------------------
# 3.5 Partição não altera a população
# ---------------------------------------------------------------------------

def _requisicoes_sincronas(casos, bracos, dir_rodada, catalogo):
    """O que o modo síncrono pergunta: (chave, prompt) de cada chamada."""
    feitas = []

    class Registrador(ProvedorFalso):
        def avaliar(self, prompt):
            feitas.append(prompt)
            return super().avaliar(prompt)

    provs = {m: Registrador(m) for m in {b.modelo for b in bracos}}
    original = run_pipeline.criar_provedor
    run_pipeline.criar_provedor = lambda modelo: provs[modelo]
    try:
        os.makedirs(dir_rodada, exist_ok=True)
        executar_matriz(casos, bracos, str(dir_rodada), catalogo=catalogo)
    finally:
        run_pipeline.criar_provedor = original
    return feitas


def test_uniao_das_particoes_e_o_que_o_sincrono_faria(tmp_path, catalogo,
                                                      simbolico_dublado):
    casos = [caso(f"c{i}", cwe=("CWE-327" if i % 2 else "CWE-89"))
             for i in range(15)]
    sincronas = _requisicoes_sincronas(casos, BRACOS, tmp_path / "s", catalogo)

    servidor = ServidorFalso()
    # Teto minúsculo: força várias partições.
    pequeno = LimitesLote(tokens_enfileirados=2_000, bytes_por_lote=10**9,
                          margem=1.0)
    prov = ProvedorLoteFalso(GEMINI, servidor, limites=pequeno)
    _rodar_lote(casos, BRACOS, tmp_path / "l", catalogo, {GEMINI: prov})

    assert len(servidor.lotes) > 1
    submetidas = [(k, p) for lote in servidor.lotes.values()
                  for k, p in lote["prompts"].items()]
    chaves = [k for k, _ in submetidas]
    assert len(chaves) == len(set(chaves))               # sem repetição
    assert sorted(p for _, p in submetidas) == sorted(sincronas)   # nem omissão
    assert set(chaves) == {chave_lote(c.id, b.modelo, b.prompt)
                           for c in casos for b in BRACOS}
    # E as partições foram submetidas uma de cada vez.
    assert prov.submissoes == sorted(servidor.lotes)


def test_particao_sobre_a_populacao_real_da_rodada_4():
    """A população real: as requisições da Rodada 4, sob um teto que as parte
    em vários lotes, voltam inteiras, uma vez cada, na ordem original."""
    reqs = _requisicoes_rodada_4()
    tokens = dict(reqs)
    itens = [(k, "") for k, _ in reqs]
    particoes = particionar(itens, LimitesLote(500_000, 10**12),
                            lambda k, _: (tokens[k], 1))
    assert len(particoes) >= 7
    uniao = [k for p in particoes for k, _ in p]
    assert uniao == [k for k, _ in itens]
    assert len(set(uniao)) == len(uniao) == len(reqs)


def test_particao_recusa_chave_repetida_e_requisicao_que_nao_cabe():
    lim = LimitesLote(100, 10**9, margem=1.0)
    with pytest.raises(ValueError):
        particionar([("a", "x"), ("a", "y")], lim, lambda k, p: (1, 1))
    with pytest.raises(ErroLote):
        particionar([("a", "x")], lim, lambda k, p: (101, 1))


def test_particao_respeita_teto_de_bytes_e_de_requisicoes():
    por_bytes = particionar([(str(i), "") for i in range(10)],
                            LimitesLote(10**9, 300, margem=1.0),
                            lambda k, p: (1, 100))
    assert [len(p) for p in por_bytes] == [3, 3, 3, 1]
    por_req = particionar([(str(i), "") for i in range(5)],
                          LimitesLote(10**9, 10**9, requisicoes_por_lote=2),
                          lambda k, p: (1, 1))
    assert [len(p) for p in por_req] == [2, 2, 1]


# ---------------------------------------------------------------------------
# 4.2 / 4.3 / 4.4 O eixo no runner
# ---------------------------------------------------------------------------

def test_modo_envio_da_rodada_le_o_manifesto(tmp_path, catalogo):
    from datetime import datetime, timezone
    assert modo_envio_da_rodada(str(tmp_path)) is None
    agora = datetime.now(timezone.utc)
    gravar_manifesto(str(tmp_path), "r", BRACOS, {"FP": 1}, 1, agora, agora,
                     catalogo, False, True, "cmd")
    assert modo_envio_da_rodada(str(tmp_path)) == MODO_SINCRONO
    # Manifesto anterior ao campo é de rodada síncrona.
    m = json.load(open(tmp_path / "manifesto.json", encoding="utf-8"))
    del m["modo"]["envio"]
    (tmp_path / "manifesto.json").write_text(json.dumps(m), encoding="utf-8")
    assert modo_envio_da_rodada(str(tmp_path)) == MODO_SINCRONO


def test_retomar_rodada_sincrona_em_lote_e_recusado_antes_de_chamar(
        tmp_path, catalogo, monkeypatch, capsys):
    from datetime import datetime, timezone
    results = tmp_path / "results"
    dir_rodada = results / "rodada-x"
    dir_rodada.mkdir(parents=True)
    agora = datetime.now(timezone.utc)
    gravar_manifesto(str(dir_rodada), "rodada-x", BRACOS, {"FP": 1}, 1, agora,
                     agora, catalogo, False, True, "cmd")
    monkeypatch.setattr(run_pipeline, "RESULTS_DIR", str(results))

    def _explode(*a, **k):
        raise AssertionError("executou antes da recusa")
    monkeypatch.setattr(run_pipeline, "executar_matriz", _explode)
    monkeypatch.setattr(run_pipeline, "gravar_manifesto", _explode)
    monkeypatch.setattr(sys, "argv", ["run_pipeline.py", "--amostra", "1",
                                      "--modelo", GEMINI, "--run-id", "rodada-x",
                                      "--modo-envio", "lote"])
    with pytest.raises(SystemExit) as e:
        run_pipeline.main()
    assert e.value.code == 2
    assert "modo de envio 'sincrono'" in capsys.readouterr().err


def test_cli_recusa_sem_llm_em_lote(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["run_pipeline.py", "--amostra", "1",
                                      "--sem-llm", "--modo-envio", "lote"])
    with pytest.raises(SystemExit):
        run_pipeline.main()
    assert "--sem-llm" in capsys.readouterr().err


def test_executar_matriz_recusa_modo_desconhecido(tmp_path, catalogo):
    with pytest.raises(ValueError):
        executar_matriz([], BRACOS, str(tmp_path), catalogo=catalogo,
                        modo_envio="assincrono")


def test_manifesto_de_rodada_em_lote_registra_a_procedencia(tmp_path, catalogo,
                                                            simbolico_dublado):
    from datetime import datetime, timezone
    dir_rodada = tmp_path / "r"
    _rodar_lote([caso("c1")], BRACOS, dir_rodada, catalogo,
                {GEMINI: ProvedorLoteFalso(GEMINI, ServidorFalso())})
    agora = datetime.now(timezone.utc)
    destino = gravar_manifesto(str(dir_rodada), "rodada-teste", BRACOS,
                               {"FP": 1}, 1, agora, agora, catalogo, False,
                               True, "cmd", modo_envio=MODO_LOTE)
    m = json.load(open(destino, encoding="utf-8"))
    assert m["modo"]["envio"] == "lote"
    assert len(m["lotes"]) == 1
    lote = m["lotes"][0]
    assert lote["fornecedor"] == "gemini"
    assert lote["id_lote"] == "batches/falso-0"
    assert lote["modelo"] == GEMINI
    # O desconto aparece aqui, e não no CSV (que fica a preço de tabela).
    assert lote["custo_estimado_usd"] == pytest.approx(lote["custo_tabela_usd"] * 0.5)
    assert "chaves" not in lote


def test_nao_detectado_nao_entra_no_lote_no_modo_filtro(tmp_path, catalogo,
                                                        simbolico_dublado):
    simbolico_dublado["detectado"] = False
    servidor = ServidorFalso()
    prov = ProvedorLoteFalso(GEMINI, servidor)
    dir_rodada = tmp_path / "r"
    _rodar_lote([caso("c1"), caso("c2", gabarito="vulneravel")], BRACOS,
                dir_rodada, catalogo, {GEMINI: prov})
    assert prov.submissoes == [] and servidor.lotes == {}
    for braco in BRACOS:
        assert {ln["Status_Semgrep"] for ln in _linhas(dir_rodada, braco)} == \
            {"NAO_DETECTADO"}


def test_ja_processado_nao_entra_no_lote(tmp_path, catalogo, simbolico_dublado):
    """O checkpoint vale igual nos dois modos: o que já tem veredito válido
    não é montado, nem pago de novo."""
    dir_rodada = tmp_path / "r"
    servidor = ServidorFalso()
    _rodar_lote([caso("c1")], BRACOS, dir_rodada, catalogo,
                {GEMINI: ProvedorLoteFalso(GEMINI, servidor)})
    de_novo = ProvedorLoteFalso(GEMINI, servidor)
    _rodar_lote([caso("c1"), caso("c2")], BRACOS, dir_rodada, catalogo,
                {GEMINI: de_novo})
    assert len(de_novo.submissoes) == 1
    novo = servidor.lotes[de_novo.submissoes[0]]["prompts"]
    assert {ler_chave(k)[0] for k in novo} == {"c2"}


# ---------------------------------------------------------------------------
# Gravação interrompida e reenvio deliberado
# ---------------------------------------------------------------------------

def test_queda_no_meio_da_gravacao_nao_duplica_linha(tmp_path, catalogo,
                                                     simbolico_dublado,
                                                     monkeypatch):
    """Resultado lido, metade gravada, processo morto: a retomada lê o lote de
    novo (não custa) e grava só o que faltou."""
    servidor = ServidorFalso()
    dir_rodada = tmp_path / "r"
    casos = [caso("c1"), caso("c2")]
    original = run_pipeline.registrar_resultado
    gravadas = []

    def _cai_na_terceira(*a, **k):
        if len(gravadas) == 2:
            raise Queda()
        gravadas.append(a[1])
        return original(*a, **k)

    monkeypatch.setattr(run_pipeline, "registrar_resultado", _cai_na_terceira)
    with pytest.raises(Queda):
        _rodar_lote(casos, BRACOS, dir_rodada, catalogo,
                    {GEMINI: ProvedorLoteFalso(GEMINI, servidor,
                                               vereditos={"c1": VP})})
    assert _registro(dir_rodada).particoes[0]["estado"] == "GRAVANDO"

    monkeypatch.setattr(run_pipeline, "registrar_resultado", original)
    retomada = ProvedorLoteFalso(GEMINI, servidor, vereditos={"c1": VP})
    _rodar_lote(casos, BRACOS, dir_rodada, catalogo, {GEMINI: retomada})
    assert retomada.submissoes == []
    for braco in BRACOS:
        ids = [ln["ID_Caso"] for ln in _linhas(dir_rodada, braco)]
        assert sorted(ids) == ["c1", "c2"]           # nem falta, nem duplica


def test_reenvio_deliberado_de_expirado_grava_o_resultado_novo(
        tmp_path, catalogo, simbolico_dublado):
    """O procedimento de `docs/SCRIPTS.md`: remover a partição recuperada do
    `lote.json` e retomar reenvia só o que não tem veredito válido."""
    servidor = ServidorFalso()
    dir_rodada = tmp_path / "r"
    _rodar_lote([caso("c1")], BRACOS, dir_rodada, catalogo,
                {GEMINI: ProvedorLoteFalso(GEMINI, servidor,
                                           estado_final=LOTE_EXPIRADO)})
    registro = _registro(dir_rodada)
    assert registro.particoes[0]["estado"] == "RECUPERADA"
    registro.dados["particoes"] = []
    registro.salvar()

    reenvio = ProvedorLoteFalso(GEMINI, servidor, vereditos={"c1": VP})
    _rodar_lote([caso("c1")], BRACOS, dir_rodada, catalogo, {GEMINI: reenvio})
    assert len(reenvio.submissoes) == 1
    for braco in BRACOS:
        assert [ln["Veredito_LLM"] for ln in _linhas(dir_rodada, braco)] == \
            [EXPIRADO, VP]


# ---------------------------------------------------------------------------
# Métricas: custo de tabela e custo faturado
# ---------------------------------------------------------------------------

def _rodada_em_lote_com_manifesto(tmp_path, catalogo):
    from datetime import datetime, timezone
    dir_rodada = tmp_path / "r"
    _rodar_lote([caso("c1"), caso("c2")], BRACOS, dir_rodada, catalogo,
                {GEMINI: ProvedorLoteFalso(GEMINI, ServidorFalso())})
    agora = datetime.now(timezone.utc)
    gravar_manifesto(str(dir_rodada), "rodada-teste", BRACOS, {"FP": 2}, 2,
                     agora, agora, catalogo, False, True, "cmd",
                     modo_envio=MODO_LOTE)
    return dir_rodada


def test_metricas_mostram_o_custo_faturado_da_rodada_em_lote(
        tmp_path, catalogo, simbolico_dublado):
    from src import metricas
    dir_rodada = _rodada_em_lote_com_manifesto(tmp_path, catalogo)

    bracos = metricas.carregar(str(dir_rodada))
    for br in bracos:
        assert br.desconto_lote == 0.5
        # 2 linhas x US$ 0,00012 no CSV, a preço de tabela
        assert br.custo_total() == pytest.approx(0.00024)
        assert br.custo_faturado() == pytest.approx(0.00012)

    cabecalho, linhas = metricas.tabela_bracos(bracos)
    assert cabecalho[-2:] == ["Custo tabela USD", "Custo faturado USD"]
    assert "Custo USD" not in cabecalho
    assert [ln[-2:] for ln in linhas] == [["0.0002", "0.0001"]] * 2

    assert any("MODO DE ENVIO LOTE" in a and "50%" in a
               for a in metricas.avisos(bracos))

    # A tabela LaTeX sai com as duas colunas também.
    metricas.exportar_latex(bracos, [], str(dir_rodada))
    tex = open(dir_rodada / "tabela_bracos.tex", encoding="utf-8").read()
    assert "Custo faturado USD" in tex


def test_csv_avulso_de_rodada_em_lote_tambem_recebe_o_desconto(
        tmp_path, catalogo, simbolico_dublado):
    from src import metricas
    dir_rodada = _rodada_em_lote_com_manifesto(tmp_path, catalogo)
    csv_avulso = dir_rodada / f"{BRACOS[0].rotulo}.csv"
    [br] = metricas.carregar(str(csv_avulso))
    assert br.custo_faturado() == pytest.approx(br.custo_total() / 2)


def test_rodada_sincrona_mantem_uma_coluna_de_custo_e_nenhum_aviso(
        tmp_path, catalogo, simbolico_dublado):
    from datetime import datetime, timezone

    from src import metricas
    dir_rodada = tmp_path / "s"
    _requisicoes_sincronas([caso("c1")], BRACOS, dir_rodada, catalogo)
    agora = datetime.now(timezone.utc)
    gravar_manifesto(str(dir_rodada), "s", BRACOS, {"FP": 1}, 1, agora, agora,
                     catalogo, False, True, "cmd")
    bracos = metricas.carregar(str(dir_rodada))
    assert all(br.desconto_lote is None for br in bracos)
    assert all(br.custo_faturado() == br.custo_total() for br in bracos)
    cabecalho, _ = metricas.tabela_bracos(bracos)
    assert cabecalho[-1] == "Custo USD"
    assert not any("LOTE" in a for a in metricas.avisos(bracos))


def test_descontos_divergentes_nao_sao_inventados(tmp_path):
    from src import metricas
    (tmp_path / "manifesto.json").write_text(json.dumps({
        "modo": {"envio": "lote"},
        "lotes": [{"modelo": GEMINI, "desconto": 0.5},
                  {"modelo": GEMINI, "desconto": 0.4},
                  {"modelo": "gemini-2.5-flash", "desconto": 0.5}]}),
        encoding="utf-8")
    assert metricas.descontos_de_lote(str(tmp_path)) == {"gemini-2.5-flash": 0.5}
