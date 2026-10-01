"""Testes do provedor de lote da OpenAI e do ajuste de raciocínio do síncrono.

Nenhum teste toca a rede: as respostas seguem o formato documentado em
`developers.openai.com/api/docs/guides/batch` (docstring de
`src/provedores/openai_lote.py`).
"""
import json

import pytest

from src.provedores import (
    ERROR,
    EXPIRADO,
    FP,
    VP,
    ProvedorOpenAI,
    ProvedorOpenAILote,
    criar_provedor_lote,
)
from src.provedores.lote import (
    CANCELADO,
    CONCLUIDO,
    FALHOU,
    LOTE_EXPIRADO,
    NAO_ENCONTRADO,
    PENDENTE,
    ErroLote,
    correlacionar,
)
from src.provedores.openai_lote import limites_do_modelo, normalizar_estado
from src.provedores.precos import TABELA, custo_usd, tabela_para_manifesto
from tests.test_provedores import JSON_FP, JSON_VP, SessaoFalsa, resposta_openai

LUNA = "gpt-6-luna"


def k(caso, prompt="baseline"):
    return f"{caso}|{LUNA}|{prompt}"


def linha_ok(chave, texto, t_in=1000, t_out=40):
    return {"id": f"batch_req_{chave}", "custom_id": chave, "error": None,
            "response": {"status_code": 200, "request_id": "req",
                         "body": resposta_openai(texto, t_in, t_out)._dados}}


class Resp:
    def __init__(self, status_code=200, dados=None, texto=None):
        self.status_code = status_code
        self._dados = dados
        self.headers = {}
        self.text = texto if texto is not None else json.dumps(dados or {})

    def json(self):
        return self._dados


class FornecedorFalso:
    """Sessão `requests` dublada, com o estado de um fornecedor OpenAI."""

    def __init__(self):
        self.arquivos = {}
        self.lotes = {}
        self.posts = []

    def post(self, url, headers=None, timeout=None, data=None, files=None,
             json=None):
        self.posts.append({"url": url, "headers": headers, "data": data,
                           "files": files, "json": json})
        if url.endswith("/files"):
            fid = f"file-{len(self.arquivos)}"
            self.arquivos[fid] = files["file"][1].decode("utf-8")
            return Resp(dados={"id": fid, "purpose": data["purpose"]})
        if url.endswith("/batches"):
            bid = f"batch_{len(self.lotes)}"
            self.lotes[bid] = {"id": bid, "status": "validating",
                               "metadata": json["metadata"],
                               "input_file_id": json["input_file_id"]}
            return Resp(dados=self.lotes[bid])
        raise AssertionError(url)

    def concluir(self, bid, linhas_saida, linhas_erro=(), status="completed"):
        lote = self.lotes[bid]
        lote["status"] = status
        if linhas_saida:
            self.arquivos["out-" + bid] = "\n".join(map(_json_dumps, linhas_saida))
            lote["output_file_id"] = "out-" + bid
        if linhas_erro:
            self.arquivos["err-" + bid] = "\n".join(map(_json_dumps, linhas_erro))
            lote["error_file_id"] = "err-" + bid

    def get(self, url, headers=None, params=None, timeout=None):
        if url.endswith("/content"):
            fid = url.split("/files/")[1][:-len("/content")]
            return Resp(texto=self.arquivos[fid])
        if url.endswith("/batches"):
            return Resp(dados={"data": list(self.lotes.values())[::-1],
                               "has_more": False})
        bid = url.rsplit("/", 1)[-1]
        if bid not in self.lotes:
            return Resp(404, {"error": {"message": "not found"}})
        return Resp(dados=self.lotes[bid])


def _json_dumps(x):
    return json.dumps(x)


# --- Síncrono: raciocínio desligado e preço -----------------------------------

def test_luna_vai_sem_raciocinio_e_com_temperatura_zero():
    payload = ProvedorOpenAI(modelo=LUNA, api_key="k")._payload("p")
    assert payload["reasoning_effort"] == "none"
    assert payload["temperature"] == 0.0
    assert payload["response_format"] == {"type": "json_object"}


def test_modelo_sem_raciocinio_nao_recebe_o_parametro():
    """O `gpt-4o-mini` não conhece `reasoning_effort`: mandar seria erro 400."""
    assert "reasoning_effort" not in ProvedorOpenAI(api_key="k")._payload("p")


def test_luna_tem_preco_tabelado_com_data_propria():
    assert TABELA[LUNA].entrada_por_1m == 0.10
    assert TABELA[LUNA].saida_por_1m == 0.50
    assert custo_usd(LUNA, 1_000_000, 1_000_000) == pytest.approx(0.60)
    m = tabela_para_manifesto([LUNA, "gpt-4o-mini"])
    assert m["modelos_sem_preco"] == []
    assert m["data_consulta_por_modelo"] == {LUNA: "2026-09-30"}


def test_variante_com_raciocinio_manda_o_nome_base_e_o_esforco():
    """`gpt-6-luna@low`: a API recebe o modelo base, o esforço pedido e nenhuma
    temperatura — com raciocínio ligado, a API recusa `temperature`."""
    payload = ProvedorOpenAI(modelo=f"{LUNA}@low", api_key="k")._payload("p")
    assert payload["model"] == LUNA
    assert payload["reasoning_effort"] == "low"
    assert "temperature" not in payload
    assert payload["response_format"] == {"type": "json_object"}


@pytest.mark.parametrize("modelo", [f"{LUNA}@turbo", "gpt-4o-mini@low", f"{LUNA}@"])
def test_variante_invalida_e_recusada_antes_de_qualquer_chamada(modelo):
    with pytest.raises(ValueError):
        ProvedorOpenAI(modelo=modelo, api_key="k")


def test_variante_custa_e_enfileira_como_o_modelo_base():
    variante = f"{LUNA}@low"
    assert custo_usd(variante, 1_000_000, 1_000_000) == pytest.approx(0.60)
    m = tabela_para_manifesto([variante])
    assert m["modelos_sem_preco"] == []
    assert m["data_consulta_por_modelo"] == {variante: "2026-09-30"}
    assert limites_do_modelo(variante) == limites_do_modelo(LUNA)


def test_variante_em_lote_leva_o_mesmo_corpo_do_sincrono():
    variante = f"{LUNA}@low"
    p = criar_provedor_lote(variante, api_key="k")
    corpo = json.loads(p.linha(f"c1|{variante}|baseline", "prompt"))["body"]
    assert corpo == ProvedorOpenAI(modelo=variante, api_key="k")._payload("prompt")
    assert corpo["model"] == LUNA


def test_luna_sincrono_de_ponta_a_ponta():
    sessao = SessaoFalsa(resposta_openai(JSON_VP))
    r = ProvedorOpenAI(modelo=LUNA, api_key="k", sessao=sessao).avaliar("p")
    assert r.veredito == VP
    assert sessao.chamadas[0]["payload"]["reasoning_effort"] == "none"


# --- Lote: formato ------------------------------------------------------------

def test_linha_do_jsonl_segue_o_formato_e_o_corpo_do_sincrono():
    p = ProvedorOpenAILote(modelo=LUNA, api_key="k")
    linha = json.loads(p.linha(k("c1"), "prompt"))
    assert linha == {"custom_id": k("c1"), "method": "POST",
                     "url": "/v1/chat/completions",
                     "body": ProvedorOpenAI(modelo=LUNA, api_key="k")._payload("prompt")}
    assert p.jsonl({k("c1"): "a", k("c2"): "b"}).decode().count("\n") == 2


def test_limites_por_modelo_e_sobrescrita(monkeypatch):
    monkeypatch.delenv("OPENAI_LOTE_TOKENS_ENFILEIRADOS", raising=False)
    lim = limites_do_modelo(LUNA)
    assert lim.tokens_enfileirados == 5_000_000
    assert lim.requisicoes_por_lote == 50_000
    assert lim.bytes_por_lote == 200_000_000
    monkeypatch.setenv("OPENAI_LOTE_TOKENS_ENFILEIRADOS", "20000000")
    assert limites_do_modelo(LUNA).tokens_enfileirados == 20_000_000


@pytest.mark.parametrize("status,esperado", [
    ("validating", PENDENTE), ("in_progress", PENDENTE),
    ("finalizing", PENDENTE), ("cancelling", PENDENTE),
    ("completed", CONCLUIDO), ("expired", LOTE_EXPIRADO),
    ("failed", FALHOU), ("cancelled", CANCELADO),
])
def test_estados_do_fornecedor(status, esperado):
    assert normalizar_estado({"status": status}) == esperado


# --- Lote: ciclo contra o fornecedor dublado ----------------------------------

def test_submeter_sobe_o_arquivo_e_cria_o_lote_com_o_rotulo():
    f = FornecedorFalso()
    p = ProvedorOpenAILote(modelo=LUNA, api_key="sk-SEGREDO", sessao=f)
    bid = p.submeter({k("c1"): "a", k("c2"): "b"}, "rodada-p0-abc")
    assert bid == "batch_0"
    upload, criacao = f.posts
    assert upload["data"] == {"purpose": "batch"}
    assert upload["headers"] == {"Authorization": "Bearer sk-SEGREDO"}
    assert "sk-SEGREDO" not in upload["url"] + criacao["url"]
    assert [json.loads(x)["custom_id"] for x in f.arquivos["file-0"].splitlines()] \
        == [k("c1"), k("c2")]
    assert criacao["json"] == {"input_file_id": "file-0",
                               "endpoint": "/v1/chat/completions",
                               "completion_window": "24h",
                               "metadata": {"rotulo": "rodada-p0-abc"}}
    assert p.localizar("rodada-p0-abc") == "batch_0"
    assert p.localizar("outro") is None
    assert p.estado("batch_0") == PENDENTE
    assert p.estado("batch_inexistente") == NAO_ENCONTRADO


def test_recuperar_le_saida_e_erros_por_chave_fora_de_ordem():
    f = FornecedorFalso()
    p = ProvedorOpenAILote(modelo=LUNA, api_key="k", sessao=f)
    chaves = [k(f"c{i}") for i in range(5)]
    bid = p.submeter({c: "x" for c in chaves}, "r")
    f.concluir(bid, [
        linha_ok(chaves[3], JSON_FP),
        linha_ok(chaves[0], JSON_VP),
        linha_ok(chaves[4], '{"verdict": "TALVEZ", "reasoning": "x"}'),
    ], [
        {"custom_id": chaves[2], "response": None,
         "error": {"code": "batch_expired",
                   "message": "This request could not be executed before the "
                              "completion window expired."}},
        {"custom_id": chaves[1], "error": None,
         "response": {"status_code": 400,
                      "body": {"error": {"message": "Unsupported parameter"}}}},
    ])
    r = p.recuperar(bid)
    assert r[chaves[0]].veredito == VP
    assert r[chaves[3]].veredito == FP
    assert r[chaves[4]].veredito == ERROR           # fora do domínio: nunca FP
    assert r[chaves[2]].veredito == EXPIRADO
    assert r[chaves[2]].custo_usd == 0.0
    assert r[chaves[1]].veredito == ERROR
    assert "Unsupported parameter" in r[chaves[1]].justificativa


def test_lote_expirado_parcial_correlaciona_sem_cobrar_o_expirado():
    f = FornecedorFalso()
    p = ProvedorOpenAILote(modelo=LUNA, api_key="k", sessao=f)
    chaves = [k("c1"), k("c2")]
    bid = p.submeter({c: "x" for c in chaves}, "r")
    f.concluir(bid, [linha_ok(chaves[0], JSON_VP)], [], status="expired")
    assert p.estado(bid) == LOTE_EXPIRADO
    respostas, _ = correlacionar(chaves, p.recuperar(bid), LOTE_EXPIRADO, LUNA,
                                 p.cobra_expirada)
    assert respostas[chaves[0]].veredito == VP
    assert respostas[chaves[1]].veredito == EXPIRADO
    assert respostas[chaves[1]].custo_usd == 0.0


@pytest.mark.parametrize("texto", [
    JSON_VP, JSON_FP, '{"verdict": "TALVEZ", "reasoning": "x"}', "não é JSON",
])
def test_mesma_resposta_bruta_mesmo_resultado_nos_dois_modos(texto):
    bruta = resposta_openai(texto, 1234, 56)
    sinc = ProvedorOpenAI(modelo=LUNA, api_key="k",
                          sessao=SessaoFalsa(bruta)).avaliar("p")
    lote = ProvedorOpenAILote(modelo=LUNA, api_key="k").converter(
        {"custom_id": "x", "error": None,
         "response": {"status_code": 200, "body": bruta._dados}})
    assert lote == sinc
    assert lote.custo_usd > 0


def test_sem_chave_para_antes_de_tocar_a_rede():
    p = ProvedorOpenAILote(modelo=LUNA, api_key="", sessao=FornecedorFalso())
    with pytest.raises(ErroLote, match="OPENAI_API_KEY"):
        p.submeter({k("c1"): "a"}, "r")


def test_criacao_recusada_vira_erro_de_lote():
    class Recusa(FornecedorFalso):
        def post(self, url, **kw):
            if url.endswith("/batches"):
                return Resp(400, {"error": {"message": "billing"}})
            return super().post(url, **kw)
    p = ProvedorOpenAILote(modelo=LUNA, api_key="k", sessao=Recusa())
    with pytest.raises(ErroLote, match="HTTP 400"):
        p.submeter({k("c1"): "a"}, "r")


def test_fabrica_devolve_o_provedor_de_lote_da_openai():
    p = criar_provedor_lote(LUNA, api_key="k")
    assert isinstance(p, ProvedorOpenAILote)
    assert p.limites.tokens_enfileirados == 5_000_000


# --- Integração: a rodada inteira pelo provedor da OpenAI ----------------------

def test_rodada_em_lote_pela_openai_de_ponta_a_ponta(tmp_path, monkeypatch):
    """Runner real, prompts reais, fornecedor dublado que responde lendo o
    JSONL que recebeu — a ida e volta do `custom_id` inteira."""
    import csv
    import os

    import run_pipeline
    from run_pipeline import Braco, ResultadoSimbolico, executar_matriz
    from src.catalogo import Catalogo
    from tests.test_matriz import CONTEXTO, caso

    class Responde(FornecedorFalso):
        def get(self, url, **kw):
            bid = url.rsplit("/", 1)[-1]
            if bid in self.lotes and self.lotes[bid]["status"] == "validating":
                pedidos = [json.loads(x) for x in
                           self.arquivos[self.lotes[bid]["input_file_id"]].splitlines()]
                assert all(p["body"]["reasoning_effort"] == "none" for p in pedidos)
                # Veredito VP só para c2, e em ordem inversa.
                self.concluir(bid, [linha_ok(
                    p["custom_id"], JSON_VP if p["custom_id"].startswith("c2|")
                    else JSON_FP) for p in reversed(pedidos)])
            return super().get(url, **kw)

    monkeypatch.setattr(run_pipeline, "resolver_simbolico", lambda c, cache=None:
                        ResultadoSimbolico("DETECTADO", {"start": {"line": 1}},
                                           CONTEXTO))
    provedor = ProvedorOpenAILote(modelo=LUNA, api_key="k", sessao=Responde())
    monkeypatch.setattr(run_pipeline, "criar_provedor_lote", lambda m: provedor)
    bracos = [Braco(LUNA, "baseline"), Braco(LUNA, "especialista")]
    executar_matriz([caso("c1"), caso("c2"), caso("c3")], bracos, str(tmp_path),
                    catalogo=Catalogo.carregar(), modo_envio="lote",
                    run_id="r", dormir=lambda s: None)
    for b in bracos:
        with open(os.path.join(tmp_path, f"{b.rotulo}.csv"), encoding="utf-8") as f:
            linhas = list(csv.DictReader(f))
        assert [(ln["ID_Caso"], ln["Veredito_LLM"]) for ln in linhas] == \
            [("c1", FP), ("c2", VP), ("c3", FP)]
        assert all(float(ln["Custo_USD"]) > 0 for ln in linhas)
